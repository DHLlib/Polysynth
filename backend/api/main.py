#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import config, modes, sessions
from backend.core.logger import get_logger, restore_loggers
from backend.datebase.crud import seed_db_from_files
from backend.datebase.engine import AsyncSessionLocal, init_db

logger = get_logger("api.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    restore_loggers()
    logger.info("API startup: initializing database")
    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_db_from_files(db)
    logger.info("API startup: seed complete")
    yield
    logger.info("API shutdown")


app = FastAPI(title="Polysynth API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(modes.router, prefix="/api/modes", tags=["modes"])
