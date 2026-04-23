#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""DuckDuckGo 免费搜索工具。"""

import asyncio
import warnings

from backend.core.logger import get_logger

logger = get_logger("tools.search")

# 过滤掉 v8.x 的改名警告（虚拟环境已装 duckduckgo-search）
warnings.filterwarnings("ignore", message=".*renamed to `ddgs`.*")
from duckduckgo_search import DDGS


def _search_sync(query: str, max_results: int) -> list[dict]:
    """同步搜索（在线程池中执行，避免阻塞事件循环）。"""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


async def search_web(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 搜索网页。"""
    logger.info(f"Search start: query='{query}', max_results={max_results}")
    try:
        results = await asyncio.to_thread(_search_sync, query, max_results)
        if not results:
            logger.info("Search end: no results")
            return "未找到相关搜索结果。"

        lines = []
        for i, r in enumerate(results, start=1):
            title = r.get("title", "")
            href = r.get("href", "")
            body = r.get("body", "")[:300]
            lines.append(f"[{i}] {title}\n链接: {href}\n摘要: {body}")
        summary = "\n\n".join(lines)
        logger.info(f"Search end: {len(results)} results, total_len={len(summary)}")
        return summary
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"[搜索失败: {e}]"
