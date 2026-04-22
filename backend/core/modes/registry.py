#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
模式注册表。mode_name -> ModeRunner 类。
"""

from backend.core.modes.base import ModeRunner
from backend.core.modes.six_hat import SixHatRunner
from backend.core.modes.debate import DebateRunner

_REGISTRY: dict[str, type[ModeRunner]] = {
    "six_hat": SixHatRunner,
    "debate": DebateRunner,
}


def get_runner(mode_name: str) -> ModeRunner:
    """根据模式名获取对应的 ModeRunner 实例。"""
    cls = _REGISTRY.get(mode_name)
    if cls is None:
        raise ValueError(f"未知模式: {mode_name}。可用模式: {list(_REGISTRY.keys())}")
    return cls()


def register_mode(mode_name: str, runner_cls: type[ModeRunner]) -> None:
    """注册新的模式执行器（供插件扩展）。"""
    _REGISTRY[mode_name] = runner_cls
