#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""工具注册表。"""

from backend.core.logger import get_logger
from backend.core.tools.schema import ToolSchema
from backend.core.tools.search import search_web

logger = get_logger("tools.registry")


_REGISTERED_TOOLS: dict[str, ToolSchema] = {
    "search": ToolSchema(
        name="search",
        description="搜索互联网获取实时信息，适用于查询最新数据、事实验证、补充背景知识等场景。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题",
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量（默认5条）",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=search_web,
    ),
}


def get_tool_schemas(enabled_names: list[str] | None = None) -> list[dict]:
    """获取启用的工具 OpenAI schema 列表。"""
    if enabled_names is None:
        enabled_names = list(_REGISTERED_TOOLS.keys())
    schemas = []
    for name in enabled_names:
        if name in _REGISTERED_TOOLS:
            schemas.append(_REGISTERED_TOOLS[name].to_openai_schema())
        else:
            logger.warning(f"Unknown tool requested: {name}")
    return schemas


async def execute_tool(name: str, arguments: dict) -> str:
    """执行指定工具。"""
    if name not in _REGISTERED_TOOLS:
        return f"[错误：未知工具 '{name}']"
    tool = _REGISTERED_TOOLS[name]
    return await tool.handler(**arguments)
