#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""FastAPI 依赖注入。"""

from backend.datebase.engine import AsyncSessionLocal


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
