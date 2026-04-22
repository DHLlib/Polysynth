#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Session 管理器：驱动中心。
- 每个 session 对应一个 .jsonl（消息日志）和一个 .state.json（运行时状态）。
- 拥有 discussion_history（LLM 消息列表）。
- 根据 default_mode 调度 ModeRunner。
- 通过 session_stream 统一输出事件给注册的处理程序。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Awaitable
from datetime import datetime
from pathlib import Path
from typing import Any

SESSION_DIR = Path(__file__).parent.parent.parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)


async def session_create(
        session_id: str,
        handlers: list[Callable[[Any], Awaitable[None]]] | None = None,
) -> Session:
    """
    创建 Session，注册输出处理器，启动并运行完整讨论流程。

    :param session_id: 会话唯一标识
    :param handlers: 自定义输出处理器列表；为空则自动注册 TerminalOutputHandler
    :return: 运行结束后的 Session 对象（可读取历史、状态等）
    """
    session = Session(session_id)

    if handlers:
        for handler in handlers:
            session.register_output_handler(handler)
    else:
        from backend.core.output_handlers import TerminalOutputHandler
        session.register_output_handler(TerminalOutputHandler())

    async for _event in session.run():
        pass  # 输出处理器负责所有终端输出

    return session


class Session:
    def __init__(
        self,
        session_id: str,
        runtime_config=None,
        db_callback: Callable[[dict], Awaitable[None]] | None = None,
    ):
        self.session_id = session_id
        self._runtime_config = runtime_config
        self._db_callback = db_callback
        self._state: dict = {}
        self._history: list[dict] = []  # LLM 消息格式: [{"role": "user|assistant", "content": "..."}, ...]
        self._handlers: list[Callable[[Any], Awaitable[None]]] = []
        self._jsonl_path = SESSION_DIR / f"{session_id}.jsonl"
        self._state_path = SESSION_DIR / f"{session_id}.state.json"
        self._load_state()

    # ── 状态读写（持久化到 .state.json） ──
    def _load_state(self):
        if self._state_path.exists():
            with open(self._state_path, "r", encoding="utf-8") as f:
                self._state = json.load(f)

    def _persist_state(self):
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def load(self, key: str):
        return self._state.get(key)

    def save(self, key: str, value):
        self._state[key] = value
        self._persist_state()

    # ── 讨论历史（LLM 消息列表，内存中） ──
    def add_history(self, role: str, content: str):
        """追加一条 LLM 消息到内存历史。"""
        self._history.append({"role": role, "content": content})

    def get_history(self) -> list[dict]:
        """返回 LLM 可用的 {role, content} 列表副本。"""
        return list(self._history)

    # ── 配置获取（优先运行时配置，fallback 文件单例） ──
    def get_config(self):
        if self._runtime_config is not None:
            return self._runtime_config
        from backend.core.config import Config
        return Config.get()

    # ── 输出处理器注册 ──
    def register_output_handler(self, handler: Callable[[Any], Awaitable[None]]):
        """注册一个异步事件处理器，接收 StreamEvent。"""
        self._handlers.append(handler)

    # ── 消息日志（追加到 .jsonl） ──
    def append_message(self, entry: dict):
        entry["ts"] = datetime.now().isoformat()
        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_messages(self) -> list[dict]:
        """返回 LLM 可用的 {role, content} 列表（从 jsonl 读取）。"""
        messages = []
        if not self._jsonl_path.exists():
            return messages
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                messages.append({
                    "role"   : entry.get("role", "assistant"),
                    "content": entry["content"],
                })
        return messages

    def get_full_history(self) -> list[dict]:
        """返回带完整元数据的原始 jsonl 列表。"""
        history = []
        if not self._jsonl_path.exists():
            return history
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                history.append(json.loads(line))
        return history

    # ── 主驱动循环 ──
    async def run(self):
        """
        根据 Config.default_mode 调度对应 ModeRunner，
        yield StreamEvent，并自动管理历史和持久化。
        """
        from backend.core.modes.registry import get_runner
        from backend.datebase.stream_events import TurnEndEvent

        cfg = self.get_config()
        runner = get_runner(cfg.default_mode)

        async for event in runner.run(self):
            # 转发给所有注册的处理程序
            for handler in self._handlers:
                await handler(event)

            # 发言结束时：更新内存历史 + 持久化到 jsonl + 可选 DB 回调
            if isinstance(event, TurnEndEvent):
                role = "assistant" if len(self._history) % 2 == 0 else "user"
                self.add_history(role, event.full_content)
                entry = {
                    "role_key": event.role_key,
                    "role"    : role,
                    "name"    : cfg.participants[event.role_key]["name"],
                    "content" : event.full_content,
                    "model"   : cfg.participants[event.role_key]["model"],
                }
                self.append_message(entry)
                if self._db_callback is not None:
                    await self._db_callback(entry)

            yield event
