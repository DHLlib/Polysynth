#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""配置路由：模式、参与者与供应商管理。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.core.agent_generator import clear_provider_cache

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
    return cfg


@router.patch("/participants/{participant_id}")
async def patch_participant(
    participant_id: int, body: dict, db: AsyncSession = Depends(get_db)
):
    p = await update_participant(db, participant_id, **body)
    if p is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    return p


# ── Provider CRUD ──

@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    return await get_providers(db)


@router.post("/providers", response_model=ProviderOut, status_code=201)
async def add_provider(body: ProviderCreate, db: AsyncSession = Depends(get_db)):
    clear_provider_cache()
    return await create_provider(db, body.name, body.api_key, body.base_url)


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def patch_provider(
    provider_id: int, body: ProviderUpdate, db: AsyncSession = Depends(get_db)
):
    kwargs = body.model_dump(exclude_unset=True)
    p = await update_provider(db, provider_id, **kwargs)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    clear_provider_cache()
    return p


@router.delete("/providers/{provider_id}", status_code=204)
async def remove_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_provider(db, provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    clear_provider_cache()
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
    return None


# ── Global Host ──

@router.get("/host", response_model=GlobalHostOut)
async def read_global_host(db: AsyncSession = Depends(get_db)):
    return await get_global_host(db)


@router.put("/host", response_model=GlobalHostOut)
async def set_global_host(body: GlobalHostUpdate, db: AsyncSession = Depends(get_db)):
    kwargs = body.model_dump(exclude_unset=True)
    host = await update_global_host(db, **kwargs)
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
