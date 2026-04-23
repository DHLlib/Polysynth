#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Session 路由：REST CRUD + WebSocket 实时流。"""

import asyncio
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.api.schemas import AttachmentOut, SessionOut, SessionDetailOut
from backend.core.file_parser import extract_text, get_file_extension, is_allowed_file
from backend.core.logger import get_logger
from backend.core.output_handlers import WebSocketOutputHandler
from backend.core.runtime_config import RuntimeConfig
from backend.core.session import Session as DiscussionSession
from backend.core.summarizer import summarize_text
from backend.datebase.crud import (
    append_message,
    create_attachment,
    create_session_record,
    get_attachments_by_session,
    get_mode_config,
    get_session_record,
    list_session_records,
    update_session_status,
)
from backend.datebase.engine import AsyncSessionLocal

UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_FILES = 5

logger = get_logger("api.sessions")

router = APIRouter()


@router.post("", response_model=SessionOut, status_code=201)
async def create_new_session(
    mode: str = Form(...),
    topic: str = Form(...),
    rounds: Optional[int] = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    # 校验文件数量和大小
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"最多上传 {MAX_FILES} 个文件")

    for f in files:
        if f.size and f.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"文件 {f.filename} 超过 20MB 限制")
        if not is_allowed_file(f.filename):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {f.filename}。支持: txt, md, pdf, docx, xlsx, pptx",
            )

    session_id = uuid.uuid4().hex
    logger.info(f"Create session: {session_id}, mode={mode}, topic={topic}, files={len(files)}")

    mode_cfg = await get_mode_config(db, mode)
    default_rounds = mode_cfg.default_rounds if mode_cfg else 3

    # 根据模式配置判断是否允许前端自定义轮次
    rounds_val = default_rounds
    if mode_cfg and rounds is not None:
        is_configurable = mode_cfg.mode_json.get("rounds", {}).get("configurable", False)
        if is_configurable:
            min_r = mode_cfg.mode_json.get("rounds", {}).get("min", 1)
            max_r = mode_cfg.mode_json.get("rounds", {}).get("max", 10)
            rounds_val = max(min_r, min(max_r, rounds))

    rec = await create_session_record(db, session_id, mode, topic, rounds_val)

    # 处理文件上传
    if files:
        session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_upload_dir, exist_ok=True)

        for upload_file in files:
            file_path = os.path.join(session_upload_dir, upload_file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)

            # 提取文本
            text = await extract_text(file_path, upload_file.filename)

            # 生成摘要（使用默认模型）
            summary = ""
            if text:
                summary = await summarize_text(text, "deepseek/deepseek-chat")

            await create_attachment(
                db,
                session_id=session_id,
                filename=upload_file.filename,
                file_type=get_file_extension(upload_file.filename),
                file_size=upload_file.size or 0,
                storage_path=file_path,
                summary=summary or None,
            )

    await db.commit()
    logger.info(f"Session record created: {session_id}, rounds={rounds_val}")
    return rec


@router.get("", response_model=list[SessionOut])
async def get_sessions(
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)
):
    return await list_session_records(db, limit, offset)


@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session_detail(session_id: str, db: AsyncSession = Depends(get_db)):
    rec = await get_session_record(db, session_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found")
    return rec


@router.websocket("/ws/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    logger.info(f"WebSocket connect: {session_id}")
    await websocket.accept()

    # 加载 session
    async with AsyncSessionLocal() as db:
        db_session = await get_session_record(db, session_id)
        if not db_session:
            await websocket.send_json(
                {"type": "error", "payload": {"message": "Session not found"}}
            )
            await websocket.close()
            return

        if db_session.status == "running":
            logger.warning(f"WebSocket rejected: {session_id} already running")
            await websocket.send_json(
                {"type": "error", "payload": {"message": "Session already running"}}
            )
            await websocket.close()
            return

        await update_session_status(db, session_id, "running")
        await db.commit()

    # 构建 RuntimeConfig
    async with AsyncSessionLocal() as db:
        cfg = await RuntimeConfig.from_db(db, db_session.mode, db_session.topic)

    # DB 持久化回调
    async def db_callback(entry: dict):
        async with AsyncSessionLocal() as db:
            await append_message(
                db,
                session_id,
                entry["role_key"],
                entry["role"],
                entry["name"],
                entry["content"],
                entry.get("model"),
            )

    # 创建讨论 Session
    disc_session = DiscussionSession(
        session_id=session_id,
        runtime_config=cfg,
        db_callback=db_callback,
    )
    handler = WebSocketOutputHandler(websocket)
    disc_session.register_output_handler(handler)

    # 后台运行讨论
    task = asyncio.create_task(_run_discussion(disc_session, session_id))

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnect: {session_id}")
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _run_discussion(disc_session: DiscussionSession, session_id: str):
    try:
        async for _event in disc_session.run():
            pass
    except Exception as e:
        logger.exception(f"Discussion error: {session_id}, error={e}")
        async with AsyncSessionLocal() as db:
            await update_session_status(db, session_id, "error")
            await db.commit()
    else:
        logger.info(f"Discussion complete: {session_id}")
        async with AsyncSessionLocal() as db:
            await update_session_status(db, session_id, "completed")
            await db.commit()


@router.get("/{session_id}/attachments", response_model=list[AttachmentOut])
async def get_session_attachments(session_id: str, db: AsyncSession = Depends(get_db)):
    return await get_attachments_by_session(db, session_id)
