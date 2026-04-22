#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
输出处理器：将 StreamEvent 转换为终端输出。
"""

from backend.datebase.stream_events import (
    BannerEvent,
    SessionEndEvent,
    TokenEvent,
    TurnEndEvent,
    TurnStartEvent,
)

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"


class TerminalOutputHandler:
    """将事件流渲染到终端，处理颜色、banner、换行。"""

    def __init__(self):
        self._current_color = ""

    async def __call__(self, event):
        match type(event).__name__:
            case "BannerEvent":
                self._print_banner(event.text)
            case "TurnStartEvent":
                self._current_color = event.color
                print(f"\n{event.color}{BOLD}{'─' * 60}{RESET}")
                print(f"{event.color}{BOLD}  {event.role_name}{RESET}")
                print(f"{event.color}{BOLD}{'─' * 60}{RESET}")
                print(event.color, end="", flush=True)
            case "TokenEvent":
                print(self._current_color + event.token, end="", flush=True)
            case "TurnEndEvent":
                print(RESET)
            case "SessionEndEvent":
                print(f"\n完整讨论记录已保存\n")

    def _print_banner(self, text: str):
        print(f"{CYAN}{BOLD}")
        print(r"  _____                  _       _   ______  _____ ")
        print(r" |  __ \                | |     | | |  ____|/ ____|")
        print(r" | |__) |_____   _____ _| |_ ___| | | |__  | (___  ")
        print(r" |  _  // _ \ \ / / _` | __/ _ \ | |  __|  \___ \ ")
        print(r" | | \ \  __/\ V / (_| | ||  __/ | | |____ ____) |")
        print(f"\n{CYAN}{BOLD}{'═' * 60}{RESET}")
        print(f"{CYAN}{BOLD}  {text}{RESET}")
        print(f"{CYAN}{BOLD}{'═' * 60}{RESET}\n")


class WebSocketOutputHandler:
    """将 StreamEvent 序列化为 JSON 并通过 WebSocket 发送。"""

    def __init__(self, websocket):
        self._ws = websocket

    async def __call__(self, event):
        match type(event).__name__:
            case "BannerEvent":
                await self._ws.send_json({
                    "type": "banner",
                    "payload": {"text": event.text},
                })
            case "TurnStartEvent":
                await self._ws.send_json({
                    "type": "turn_start",
                    "payload": {
                        "role_key": event.role_key,
                        "role_name": event.role_name,
                        "color": event.color,
                        "round_num": event.round_num,
                    },
                })
            case "TokenEvent":
                await self._ws.send_json({
                    "type": "token",
                    "payload": {
                        "role_key": event.role_key,
                        "token": event.token,
                    },
                })
            case "TurnEndEvent":
                await self._ws.send_json({
                    "type": "turn_end",
                    "payload": {
                        "role_key": event.role_key,
                        "full_content": event.full_content,
                    },
                })
            case "SessionEndEvent":
                await self._ws.send_json({
                    "type": "session_end",
                    "payload": {},
                })
