#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
向后兼容的薄封装，委托给 backend.core.config.Config 单例。
新项目代码建议直接使用：from backend.core.config import Config; cfg = Config.get()
"""

from backend.core.config import Config


def load_runtime() -> dict:
    cfg = Config.get()
    return {
        "topic": cfg.topic,
        "rounds": cfg.rounds,
        "participants": cfg.participants,
        "mode": cfg.default_mode,
    }


def load_secrets() -> dict:
    return Config.get().secrets
