#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Tool schema 定义。"""

from dataclasses import dataclass
from typing import Callable, Awaitable, Any


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., Awaitable[Any]]

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
