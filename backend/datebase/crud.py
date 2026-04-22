#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""数据库 CRUD 操作与初始化 seed。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.datebase.models import (
    ModeConfig,
    Participant,
    SessionRecord,
    Message,
    Provider,
    ProviderModel,
    GlobalHost,
)

_CONFIG_DIR = Path(__file__).parent.parent / "config"


# ── Provider / ProviderModel ──

async def get_providers(db: AsyncSession) -> list[Provider]:
    result = await db.execute(
        select(Provider)
        .order_by(Provider.id)
        .options(selectinload(Provider.models))
    )
    return list(result.scalars().all())


async def get_provider(db: AsyncSession, provider_id: int) -> Provider | None:
    result = await db.execute(
        select(Provider)
        .where(Provider.id == provider_id)
        .options(selectinload(Provider.models))
    )
    return result.scalar_one_or_none()


async def get_provider_by_model(db: AsyncSession, model_name: str) -> Provider | None:
    result = await db.execute(
        select(Provider)
        .join(ProviderModel, Provider.id == ProviderModel.provider_id)
        .where(ProviderModel.model_name == model_name)
    )
    return result.scalar_one_or_none()


async def create_provider(
    db: AsyncSession, name: str, api_key: str, base_url: str | None = None
) -> Provider:
    p = Provider(name=name, api_key=api_key, base_url=base_url)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_provider(
    db: AsyncSession, provider_id: int, **kwargs: Any
) -> Provider | None:
    p = await get_provider(db, provider_id)
    if p is None:
        return None
    for k, v in kwargs.items():
        if hasattr(p, k):
            setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


async def delete_provider(db: AsyncSession, provider_id: int) -> bool:
    p = await get_provider(db, provider_id)
    if p is None:
        return False
    await db.delete(p)
    await db.commit()
    return True


async def create_provider_model(
    db: AsyncSession, provider_id: int, model_name: str
) -> ProviderModel:
    m = ProviderModel(provider_id=provider_id, model_name=model_name)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def delete_provider_model(db: AsyncSession, model_id: int) -> bool:
    result = await db.execute(
        select(ProviderModel).where(ProviderModel.id == model_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        return False
    await db.delete(m)
    await db.commit()
    return True


# ── GlobalHost ──

async def get_global_host(db: AsyncSession) -> GlobalHost:
    result = await db.execute(select(GlobalHost).order_by(GlobalHost.id))
    host = result.scalar_one_or_none()
    if host is None:
        host = GlobalHost()
        db.add(host)
        await db.commit()
        await db.refresh(host)
    return host


async def update_global_host(
    db: AsyncSession, **kwargs: Any
) -> GlobalHost:
    host = await get_global_host(db)
    for k, v in kwargs.items():
        if hasattr(host, k) and k != "color":  # 颜色不允许修改
            setattr(host, k, v)
    await db.commit()
    await db.refresh(host)
    return host


# ── ModeConfig / Participant ──

async def get_mode_config(db: AsyncSession, name: str) -> ModeConfig | None:
    result = await db.execute(
        select(ModeConfig)
        .where(ModeConfig.name == name)
        .options(selectinload(ModeConfig.participants))
    )
    return result.scalar_one_or_none()


async def get_mode_configs(db: AsyncSession) -> list[ModeConfig]:
    result = await db.execute(
        select(ModeConfig)
        .order_by(ModeConfig.id)
        .options(selectinload(ModeConfig.participants))
    )
    return list(result.scalars().all())


async def update_mode_config(
    db: AsyncSession, name: str, **kwargs: Any
) -> ModeConfig | None:
    cfg = await get_mode_config(db, name)
    if cfg is None:
        return None
    for k, v in kwargs.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    cfg.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def upsert_mode_config(
    db: AsyncSession,
    name: str,
    display_name: str,
    mode_json: dict,
    default_rounds: int = 3,
    description: str | None = None,
) -> ModeConfig:
    cfg = await get_mode_config(db, name)
    if cfg is None:
        cfg = ModeConfig(
            name=name,
            display_name=display_name,
            description=description,
            mode_json=mode_json,
            default_rounds=default_rounds,
        )
        db.add(cfg)
    else:
        cfg.display_name = display_name
        cfg.description = description
        cfg.mode_json = mode_json
        cfg.default_rounds = default_rounds
        cfg.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(cfg)
    return cfg


async def get_participants_by_mode(
    db: AsyncSession, mode_name: str
) -> list[Participant]:
    result = await db.execute(
        select(Participant).where(Participant.mode_name == mode_name)
    )
    return list(result.scalars().all())


async def upsert_participant(
    db: AsyncSession,
    mode_name: str,
    role_key: str,
    name: str,
    model: str,
    color: str | None = None,
    system_prompt: str = "",
    sort_order: int = 0,
) -> Participant:
    result = await db.execute(
        select(Participant).where(
            Participant.mode_name == mode_name,
            Participant.role_key == role_key,
        )
    )
    p = result.scalar_one_or_none()
    if p is None:
        p = Participant(
            mode_name=mode_name,
            role_key=role_key,
            name=name,
            model=model,
            color=color,
            system_prompt=system_prompt,
            sort_order=sort_order,
        )
        db.add(p)
    else:
        p.name = name
        p.model = model
        p.color = color
        p.system_prompt = system_prompt
        p.sort_order = sort_order
    await db.flush()
    await db.refresh(p)
    return p


async def update_participant(
    db: AsyncSession, participant_id: int, **kwargs: Any
) -> Participant | None:
    result = await db.execute(
        select(Participant).where(Participant.id == participant_id)
    )
    p = result.scalar_one_or_none()
    if p is None:
        return None
    for k, v in kwargs.items():
        if hasattr(p, k):
            setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


# ── Session / Message ──

async def create_session_record(
    db: AsyncSession,
    session_id: str,
    mode: str,
    topic: str,
    rounds: int = 3,
) -> SessionRecord:
    rec = SessionRecord(
        id=session_id,
        mode=mode,
        topic=topic,
        rounds=rounds,
        status="pending",
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def get_session_record(
    db: AsyncSession, session_id: str
) -> SessionRecord | None:
    result = await db.execute(
        select(SessionRecord)
        .where(SessionRecord.id == session_id)
        .options(selectinload(SessionRecord.messages))
    )
    return result.scalar_one_or_none()


async def list_session_records(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[SessionRecord]:
    result = await db.execute(
        select(SessionRecord)
        .order_by(SessionRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_session_status(
    db: AsyncSession, session_id: str, status: str
) -> None:
    rec = await get_session_record(db, session_id)
    if rec is None:
        return
    rec.status = status
    if status in ("completed", "error"):
        rec.completed_at = datetime.utcnow()
    await db.commit()


async def append_message(
    db: AsyncSession,
    session_id: str,
    role_key: str,
    role: str,
    name: str,
    content: str,
    model: str | None = None,
) -> Message:
    msg = Message(
        session_id=session_id,
        role_key=role_key,
        role=role,
        name=name,
        content=content,
        model=model,
        ts=datetime.utcnow(),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


# ── Seed ──

async def seed_db_from_files(db: AsyncSession) -> None:
    """从 JSON 配置文件初始化数据库（幂等）。"""
    from backend.Prompts import SYSTEM_PROMPTS

    with open(_CONFIG_DIR / "models.json", encoding="utf-8") as f:
        models_data = json.load(f)

    for mode_file in sorted((_CONFIG_DIR / "modes").glob("*.json")):
        with open(mode_file, encoding="utf-8") as f:
            mode_data = json.load(f)

        mode_name = mode_data["name"]
        display_name = mode_data.get("display_name", mode_name)
        description = mode_data.get("description")
        default_rounds = mode_data.get("default_rounds", 3)

        cfg = await upsert_mode_config(
            db=db,
            name=mode_name,
            display_name=display_name,
            mode_json=mode_data,
            default_rounds=default_rounds,
            description=description,
        )

        # upsert participants
        participants_data = models_data.get(mode_name, {})
        prompts_data = SYSTEM_PROMPTS.get(mode_name, {})
        speaking_order = (
            mode_data.get("rounds", {}).get("speaking_order", [])
        )
        opening_speaker = mode_data.get("opening", {}).get("speaker")
        summary_speaker = mode_data.get("rounds", {}).get("summary", {}).get("speaker")

        all_roles = set(participants_data.keys())
        # 按发言顺序 + 开场/总结角色排序
        order_map = {}
        if opening_speaker:
            order_map[opening_speaker] = 0
        for idx, rk in enumerate(speaking_order, start=1):
            order_map[rk] = idx
        if summary_speaker:
            order_map[summary_speaker] = max(order_map.values()) + 1 if order_map else 0

        for role_key, meta in participants_data.items():
            await upsert_participant(
                db=db,
                mode_name=mode_name,
                role_key=role_key,
                name=meta["name"],
                model=meta["model"],
                color=meta.get("color"),
                system_prompt=prompts_data.get(role_key, ""),
                sort_order=order_map.get(role_key, 99),
            )

        # 删除该模式中已不存在于配置文件的参与者
        existing_parts = await get_participants_by_mode(db, mode_name)
        config_role_keys = set(participants_data.keys())
        for p in existing_parts:
            if p.role_key not in config_role_keys:
                await db.delete(p)

    # ── Seed providers from secrets.json ──
    secrets_path = _CONFIG_DIR / "secrets.json"
    if secrets_path.exists():
        with open(secrets_path, encoding="utf-8") as f:
            secrets = json.load(f)

        # DeepSeek
        ds_key = secrets.get("deepseek_api_key")
        if ds_key:
            ds = await db.execute(select(Provider).where(Provider.name == "deepseek"))
            ds_provider = ds.scalar_one_or_none()
            if ds_provider is None:
                ds_provider = Provider(name="deepseek", api_key=ds_key)
                db.add(ds_provider)
                await db.flush()
                db.add_all([
                    ProviderModel(provider_id=ds_provider.id, model_name="deepseek/deepseek-chat"),
                    ProviderModel(provider_id=ds_provider.id, model_name="deepseek/deepseek-reasoner"),
                ])
            else:
                ds_provider.api_key = ds_key

        # Kimi
        km_key = secrets.get("kimi_api_key")
        km_base = secrets.get("kimi_base_url")
        if km_key:
            km = await db.execute(select(Provider).where(Provider.name == "kimi"))
            km_provider = km.scalar_one_or_none()
            if km_provider is None:
                km_provider = Provider(name="kimi", api_key=km_key, base_url=km_base)
                db.add(km_provider)
                await db.flush()
                db.add(
                    ProviderModel(provider_id=km_provider.id, model_name="openai/moonshot-v1-8k")
                )
            else:
                km_provider.api_key = km_key
                if km_base:
                    km_provider.base_url = km_base

    # ── Seed / sync global host ──
    host = await get_global_host(db)
    # 同步所有模式中的 host 角色
    for mode_name in ("six_hat", "debate"):
        mode_cfg = await get_mode_config(db, mode_name)
        if mode_cfg is None:
            continue
        host_keys = set()
        if mode_cfg.mode_json.get("opening", {}).get("speaker"):
            host_keys.add(mode_cfg.mode_json["opening"]["speaker"])
        if mode_cfg.mode_json.get("rounds", {}).get("summary", {}).get("speaker"):
            host_keys.add(mode_cfg.mode_json["rounds"]["summary"]["speaker"])
        for rk in host_keys:
            result = await db.execute(
                select(Participant).where(
                    Participant.mode_name == mode_name,
                    Participant.role_key == rk,
                )
            )
            p = result.scalar_one_or_none()
            if p:
                p.name = host.name
                p.model = host.model
                p.color = host.color
    await db.commit()
