#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""DuckDuckGo 免费搜索工具。"""

import warnings

# 必须在 import duckduckgo_search 之前过滤掉改名警告
warnings.filterwarnings("ignore", message=".*duckduckgo_search.*renamed.*")

import asyncio
import os

from backend.core.logger import get_logger

logger = get_logger("tools.search")

from duckduckgo_search import DDGS


def _get_proxies() -> str | None:
    """从环境变量读取代理配置。"""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.getenv(key)
        if val:
            return val
    return None


def _search_sync(query: str, max_results: int, backend: str = "html") -> list[dict]:
    """同步搜索（在线程池中执行，避免阻塞事件循环）。

    backend: "html" 或 "lite"，在中国大陆网络下可能需要切换。
    """
    proxies = _get_proxies()
    with DDGS(proxies=proxies) as ddgs:
        try:
            return list(ddgs.text(query, max_results=max_results, backend=backend))
        except Exception:
            # 当前 backend 失败时尝试另一个 backend
            if backend != "lite":
                logger.warning(f"Search backend '{backend}' failed, fallback to 'lite'")
                return list(ddgs.text(query, max_results=max_results, backend="lite"))
            raise


async def search_web(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 搜索网页。"""
    max_results = max(1, min(max_results, 20))
    logger.info(f"Search start: query='{query}', max_results={max_results}")
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_search_sync, query, max_results),
            timeout=15.0,
        )
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
        err_str = str(e)
        logger.error(f"Search failed: {e}")
        # 针对中国大陆网络环境的友好提示
        if "bing" in err_str.lower() or "connect" in err_str.lower():
            return (
                "[搜索服务暂不可用：当前网络环境无法访问 DuckDuckGo/Bing 搜索。"
                "请设置 HTTPS_PROXY 环境变量使用代理，或稍后再试。]"
            )
        return f"[搜索失败: {e}]"
