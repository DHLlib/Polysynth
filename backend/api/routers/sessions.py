#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Session 路由：REST CRUD + WebSocket 实时流。"""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.api.schemas import SessionCreate, SessionOut, SessionDetailOut, ModeConfigUpdate
from backend.core.output_handlers import WebSocketOutputHandler
from backend.core.runtime_config import RuntimeConfig
from backend.core.session import Session as DiscussionSession
from backend.datebase.crud import (
    append_message,
    create_session_record,
    get_mode_config,
    get_session_record,
    list_session_records,
    update_session_status,
)
from backend.datebase.engine import AsyncSessionLocal

router = APIRouter()


@router.post("", response_model=SessionOut, status_code=201)
async def create_new_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db)
):
    session_id = uuid.uuid4().hex
    mode_cfg = await get_mode_config(db, body.mode)
    default_rounds = mode_cfg.default_rounds if mode_cfg else 3

    # 根据模式配置判断是否允许前端自定义轮次
    rounds = default_rounds
    if mode_cfg and body.rounds is not None:
        is_configurable = mode_cfg.mode_json.get("rounds", {}).get("configurable", False)
        if is_configurable:
            min_r = mode_cfg.mode_json.get("rounds", {}).get("min", 1)
            max_r = mode_cfg.mode_json.get("rounds", {}).get("max", 10)
            rounds = max(min_r, min(max_r, body.rounds))

    rec = await create_session_record(db, session_id, body.mode, body.topic, rounds)
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
        pass
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
    except Exception:
        async with AsyncSessionLocal() as db:
            await update_session_status(db, session_id, "error")
            await db.commit()
    else:
        async with AsyncSessionLocal() as db:
            await update_session_status(db, session_id, "completed")
            await db.commit()
