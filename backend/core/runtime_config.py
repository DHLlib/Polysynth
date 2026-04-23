#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
运行时配置对象（非单例、非 frozen）。
用于 FastAPI/WebSocket 场景，从数据库动态加载，替代文件单例 Config。
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RuntimeConfig:
    topic: str
    rounds: int
    default_mode: str
    participants: dict[str, dict]
    mode_config: dict[str, Any]
    secrets: dict[str, str]
    prompts: dict[str, str]

    @property
    def deepseek_api_key(self) -> str:
        return self.secrets.get("deepseek_api_key", "")

    @property
    def kimi_api_key(self) -> str:
        return self.secrets.get("kimi_api_key", "")

    @property
    def kimi_base_url(self) -> str:
        return self.secrets.get("kimi_base_url", "")

    @classmethod
    async def from_db(
        cls, db: AsyncSession, mode_name: str, topic: str
    ) -> "RuntimeConfig":
        """从数据库构建 RuntimeConfig。"""
        from backend.datebase.crud import get_mode_config, get_participants_by_mode, get_global_host
        from backend.core.config import Config

        cfg = await get_mode_config(db, mode_name)
        if cfg is None:
            raise ValueError(f"Mode not found in DB: {mode_name}")

        participants_db = await get_participants_by_mode(db, mode_name)
        participants: dict[str, dict] = {}
        prompts: dict[str, str] = {}
        for p in participants_db:
            participants[p.role_key] = {
                "model": p.model,
                "name": p.name,
                "color": p.color or "",
                "tools_enabled": p.tools_enabled,
            }
            prompts[p.role_key] = p.system_prompt

        # 注入全局主持人配置，覆盖模式中的 host 角色
        host = await get_global_host(db)
        host_keys = set()
        if cfg.mode_json.get("opening", {}).get("speaker"):
            host_keys.add(cfg.mode_json["opening"]["speaker"])
        if cfg.mode_json.get("rounds", {}).get("summary", {}).get("speaker"):
            host_keys.add(cfg.mode_json["rounds"]["summary"]["speaker"])
        for rk in host_keys:
            if rk in participants:
                original = participants[rk]
                participants[rk] = {
                    "model": host.model,
                    "name": host.name,
                    "color": host.color,
                    "tools_enabled": original.get("tools_enabled"),
                }
                # system_prompt 保留各模式自己的，不覆盖

        return cls(
            topic=topic,
            rounds=cfg.default_rounds,
            default_mode=mode_name,
            participants=participants,
            mode_config=cfg.mode_json,
            secrets=Config.get().secrets,
            prompts=prompts,
        )
