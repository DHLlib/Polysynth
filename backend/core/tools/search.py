#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""DuckDuckGo 免费搜索工具（使用 ddgs 包）。"""

import asyncio
import os
import socket

from ddgs import DDGS

from backend.core.logger import get_logger

logger = get_logger("tools.search")

# 代理检测缓存
_detected_proxy: str | None = None


def _is_port_open(port: int) -> bool:
    """检查本地端口是否开放（TCP 连接）。"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _is_socks5_proxy(port: int) -> bool:
    """检测端口是否为 SOCKS5 代理（协议握手验证）。"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3) as sock:
            # SOCKS5 握手请求：版本 5, 1 个认证方法, 无认证(0x00)
            sock.sendall(b"\x05\x01\x00")
            resp = sock.recv(2)
            # 期望回复：版本 5, 方法 0x00(无认证)
            return resp == b"\x05\x00"
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def detect_proxy() -> str | None:
    """公共接口：主动触发代理检测（用于提前探测，如 session 创建时）。"""
    return _detect_local_proxy()


def _detect_local_proxy() -> str | None:
    """自动检测本地代理服务（HTTP / SOCKS5）。

    扫描常见代理端口，优先返回 HTTP 代理，其次是 SOCKS5。
    """
    global _detected_proxy
    if _detected_proxy is not None:
        return _detected_proxy if _detected_proxy else None

    # 常见 HTTP 代理端口（Mixed Port 同时支持 HTTP/HTTPS）
    http_ports = [7890, 7897, 6152, 9910, 10809]
    for port in http_ports:
        if _is_port_open(port):
            _detected_proxy = f"http://127.0.0.1:{port}"
            logger.info(f"Auto-detected local HTTP proxy: {_detected_proxy}")
            return _detected_proxy

    # 常见 SOCKS5 代理端口
    socks_ports = [7891, 1080, 10808]
    for port in socks_ports:
        if _is_socks5_proxy(port):
            _detected_proxy = f"socks5://127.0.0.1:{port}"
            logger.info(f"Auto-detected local SOCKS5 proxy: {_detected_proxy}")
            return _detected_proxy

    _detected_proxy = ""
    return None


def _get_proxy() -> str | None:
    """读取代理配置。优先级：环境变量 > 自动检测本地代理。"""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.getenv(key)
        if val:
            return val
    return _detect_local_proxy()


def _search_sync(query: str, max_results: int, backend: str = "api") -> list[dict]:
    """同步搜索（在线程池中执行，避免阻塞事件循环）。

    backend: "api" 或 "html"，api 失效时回退到 html。
    """
    proxy = _get_proxy()
    try:
        with DDGS(proxy=proxy) as ddgs:
            return list(ddgs.text(query, max_results=max_results, backend=backend))
    except Exception:
        # 当前 backend 失败时尝试另一个 backend
        if backend != "html":
            logger.warning(f"Search backend '{backend}' failed, fallback to 'html'")
            with DDGS(proxy=proxy) as ddgs:
                return list(ddgs.text(query, max_results=max_results, backend="html"))
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
