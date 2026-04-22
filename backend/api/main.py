#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import config, modes, sessions
from backend.datebase.crud import seed_db_from_files
from backend.datebase.engine import AsyncSessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_db_from_files(db)
    yield


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
