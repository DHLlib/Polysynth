#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
ModeRunner 协议。所有讨论模式必须实现此接口。
"""

from typing import Protocol, AsyncIterator

from backend.datebase.stream_events import StreamEvent
from backend.core.session import Session


class ModeRunner(Protocol):
    mode_name: str

    async def run(self, session: Session) -> AsyncIterator[StreamEvent]:
        ...
