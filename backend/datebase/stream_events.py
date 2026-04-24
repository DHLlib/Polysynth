#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Session Stream 事件类型定义。
ModeRunner yield 事件对象，Session 消费并路由给 OutputHandler。
"""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class TurnStartEvent:
    role_key: str
    role_name: str
    color: str
    round_num: int | None = None


@dataclass(frozen=True)
class TokenEvent:
    role_key: str
    token: str


@dataclass(frozen=True)
class TurnEndEvent:
    role_key: str
    full_content: str


@dataclass(frozen=True)
class BannerEvent:
    text: str


@dataclass(frozen=True)
class SessionEndEvent:
    pass


@dataclass(frozen=True)
class ToolStartEvent:
    role_key: str
    tool_name: str


@dataclass(frozen=True)
class ToolEndEvent:
    role_key: str
    tool_name: str
    preview: str


StreamEvent = Union[
    TurnStartEvent,
    TokenEvent,
    TurnEndEvent,
    BannerEvent,
    SessionEndEvent,
    ToolStartEvent,
    ToolEndEvent,
]
