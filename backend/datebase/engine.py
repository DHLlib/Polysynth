#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""数据库引擎与会话工厂。"""

from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.datebase.models import Base

_DB_PATH = Path(__file__).parent.parent.parent / "polysynth.db"
DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """创建所有表（如果不存在）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
