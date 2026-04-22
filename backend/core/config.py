#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
统一配置管理（dataclass + 单例）。
职责：集中加载 app.json / models.json / secrets.json / modes/*.json / Prompts.py，
根据 app.json 的 default_mode 提取当前模式的 participants 和 prompts。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.Prompts import SYSTEM_PROMPTS

_CONFIG_DIR = Path(__file__).parent.parent / "config"


@dataclass(frozen=True)
class Config:
    """只读配置对象，通过 Config.get() 获取单例。
    所有参与者、prompts 均已按 default_mode 过滤，直接使用即可。"""

    topic: str
    rounds: int
    default_mode: str
    participants: dict[str, dict]          # 当前模式的所有角色（原 hats）
    mode_config: dict[str, Any]            # 当前模式的规则（modes/*.json）
    secrets: dict[str, str]
    prompts: dict[str, str]                # 当前模式的 SYSTEM_PROMPTS

    # ── 快捷属性 ──
    @property
    def deepseek_api_key(self) -> str:
        return self.secrets["deepseek_api_key"]

    @property
    def kimi_api_key(self) -> str:
        return self.secrets["kimi_api_key"]

    @property
    def kimi_base_url(self) -> str:
        return self.secrets["kimi_base_url"]

    # ── 单例 ──
    _instance: "Config | None" = field(default=None, repr=False, compare=False)

    @classmethod
    def get(cls) -> "Config":
        if cls._instance is None:
            cls._instance = cls._load()
        return cls._instance

    @classmethod
    def _load(cls) -> "Config":
        with open(_CONFIG_DIR / "app.json", encoding="utf-8") as f:
            app = json.load(f)
        with open(_CONFIG_DIR / "models.json", encoding="utf-8") as f:
            models = json.load(f)
        with open(_CONFIG_DIR / "secrets.json", encoding="utf-8") as f:
            secrets = json.load(f)

        mode_name = app["default_mode"]

        with open(_CONFIG_DIR / "modes" / f"{mode_name}.json", encoding="utf-8") as f:
            mode_config = json.load(f)

        # 按当前模式提取 participants 和 prompts
        participants = models.get(mode_name, {})
        prompts = SYSTEM_PROMPTS.get(mode_name, {})

        return cls(
            topic=app["topic"],
            rounds=app["rounds"],
            default_mode=mode_name,
            participants=participants,
            mode_config=mode_config,
            secrets=secrets,
            prompts=prompts,
        )

    @classmethod
    def reload(cls) -> "Config":
        """强制重新读取配置文件（热更新场景）。"""
        cls._instance = cls._load()
        return cls._instance
