#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""模式注册表路由。"""

from fastapi import APIRouter

from backend.core.modes.registry import _REGISTRY

router = APIRouter()


@router.get("")
async def list_modes():
    return [
        {"name": name, "description": cls.__doc__ or ""}
        for name, cls in _REGISTRY.items()
    ]
