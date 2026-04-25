#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""配置路由：模式、参与者与供应商管理。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import get_logger

from backend.api.deps import get_db
from backend.api.schemas import (
    ModeConfigOut,
    ModeConfigUpdate,
    ProviderOut,
    ProviderCreate,
    ProviderUpdate,
    ProviderModelCreate,
    GlobalHostOut,
    GlobalHostUpdate,
)
from backend.datebase.crud import (
    get_mode_configs,
    update_mode_config,
    update_participant,
    get_providers,
    get_provider,
    create_provider,
    update_provider,
    delete_provider,
    create_provider_model,
    delete_provider_model,
    get_global_host,
    update_global_host,
)
from backend.core.agent_generator import clear_provider_cache, _sanitize_str

logger = get_logger("api.config")
router = APIRouter()


@router.get("/modes", response_model=list[ModeConfigOut])
async def list_mode_configs(db: AsyncSession = Depends(get_db)):
    return await get_mode_configs(db)


@router.patch("/modes/{mode_name}", response_model=ModeConfigOut)
async def patch_mode_config(
    mode_name: str, body: ModeConfigUpdate, db: AsyncSession = Depends(get_db)
):
    kwargs = body.model_dump(exclude_unset=True)
    cfg = await update_mode_config(db, mode_name, **kwargs)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Mode not found")
    logger.info(f"Mode config updated: {mode_name}, fields={list(kwargs.keys())}")
    return cfg


@router.patch("/participants/{participant_id}")
async def patch_participant(
    participant_id: int, body: dict, db: AsyncSession = Depends(get_db)
):
    p = await update_participant(db, participant_id, **body)
    if p is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    logger.info(f"Participant updated: id={participant_id}, fields={list(body.keys())}")
    return p


# ── Provider CRUD ──

@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    return await get_providers(db)


@router.post("/providers", response_model=ProviderOut, status_code=201)
async def add_provider(body: ProviderCreate, db: AsyncSession = Depends(get_db)):
    api_key = _sanitize_str(body.api_key) or ""
    base_url = _sanitize_str(body.base_url)
    result = await create_provider(db, body.name, api_key, base_url)
    clear_provider_cache()
    logger.info(f"Provider created: {body.name}")
    return result


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def patch_provider(
    provider_id: int, body: ProviderUpdate, db: AsyncSession = Depends(get_db)
):
    kwargs = body.model_dump(exclude_unset=True)
    if "api_key" in kwargs:
        kwargs["api_key"] = _sanitize_str(kwargs["api_key"]) or ""
    if "base_url" in kwargs:
        kwargs["base_url"] = _sanitize_str(kwargs["base_url"])
    p = await update_provider(db, provider_id, **kwargs)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    clear_provider_cache()
    logger.info(f"Provider updated: id={provider_id}, fields={list(kwargs.keys())}")
    return p


@router.delete("/providers/{provider_id}", status_code=204)
async def remove_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_provider(db, provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    clear_provider_cache()
    logger.info(f"Provider deleted: id={provider_id}")
    return None


@router.post("/providers/{provider_id}/models", response_model=ProviderOut)
async def add_provider_model(
    provider_id: int, body: ProviderModelCreate, db: AsyncSession = Depends(get_db)
):
    p = await get_provider(db, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await create_provider_model(db, provider_id, body.model_name)
    clear_provider_cache()
    logger.info(f"Provider model added: provider_id={provider_id}, model={body.model_name}")
    # refresh with models
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from backend.datebase.models import Provider as ProviderModel_cls
    result = await db.execute(
        select(ProviderModel_cls).where(ProviderModel_cls.id == provider_id).options(selectinload(ProviderModel_cls.models))
    )
    return result.scalar_one()


@router.delete("/providers/{provider_id}/models/{model_id}", status_code=204)
async def remove_provider_model(
    provider_id: int, model_id: int, db: AsyncSession = Depends(get_db)
):
    ok = await delete_provider_model(db, model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Model not found")
    clear_provider_cache()
    logger.info(f"Provider model removed: provider_id={provider_id}, model_id={model_id}")
    return None


# ── Global Host ──

@router.get("/host", response_model=GlobalHostOut)
async def read_global_host(db: AsyncSession = Depends(get_db)):
    return await get_global_host(db)


@router.put("/host", response_model=GlobalHostOut)
async def set_global_host(body: GlobalHostUpdate, db: AsyncSession = Depends(get_db)):
    kwargs = body.model_dump(exclude_unset=True)
    host = await update_global_host(db, **kwargs)
    logger.info(f"Global host updated: fields={list(kwargs.keys())}")
    # 同步更新所有模式中的 host 参与者
    from backend.datebase.crud import get_mode_config
    from backend.datebase.models import Participant
    from sqlalchemy import select

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
                if "name" in kwargs:
                    p.name = kwargs["name"]
                if "model" in kwargs:
                    p.model = kwargs["model"]
    await db.commit()
    return host
