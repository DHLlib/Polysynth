#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
LLM 调用层。只负责异步流式调用，不处理打印、历史或 session 记录。
"""

from litellm import completion

from backend.core.config import Config

# 单次 Session 内缓存 provider 配置，避免重复查库
_provider_cache: dict[str, dict] = {}


def clear_provider_cache() -> None:
    """清除 provider 缓存，在配置更新后调用。"""
    _provider_cache.clear()


async def _resolve_provider(model: str) -> dict:
    """通过 model 名称从数据库查询对应的 provider 配置。"""
    if model in _provider_cache:
        return _provider_cache[model]

    try:
        from backend.datebase.engine import AsyncSessionLocal
        from backend.datebase.crud import get_provider_by_model

        async with AsyncSessionLocal() as db:
            provider = await get_provider_by_model(db, model)
            if provider:
                result = {
                    "api_key": provider.api_key,
                    "base_url": provider.base_url,
                }
                _provider_cache[model] = result
                return result
    except Exception:
        pass

    return {}


async def call_llm(session, model: str, messages: list, cfg=None):
    """
    底层异步流式调用 LLM。

    :param session: Session 对象（保留用于未来扩展：按 session 限流、追踪等）
    :param model: LiteLLM 模型名
    :param messages: 完整消息列表
    :param cfg: RuntimeConfig 或 Config 实例；为空则 fallback 到 Config 单例
    :yield: 每个流式 token
    """
    if cfg is None:
        cfg = Config.get()

    kwargs = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.8,
        "timeout": 180,
    }

    # 从数据库解析 provider 配置
    provider_cfg = await _resolve_provider(model)
    if provider_cfg.get("api_key"):
        kwargs["api_key"] = provider_cfg["api_key"]
    if provider_cfg.get("base_url"):
        kwargs["api_base"] = provider_cfg["base_url"]

    # 兼容旧逻辑：如果数据库未找到，回退到 Config 的硬编码密钥
    if "api_key" not in kwargs:
        if "moonshot" in model:
            kwargs["api_key"] = cfg.kimi_api_key
            kwargs["api_base"] = cfg.kimi_base_url
        elif "deepseek" in model:
            kwargs["api_key"] = cfg.deepseek_api_key

    # 修复 messages 格式：DeepSeek 等 API 要求严格交替，且最后一条不能是 assistant
    fixed_messages = []
    for msg in messages:
        if msg.get("role") == "assistant" and fixed_messages and fixed_messages[-1].get("role") == "assistant":
            fixed_messages.append({"role": "user", "content": "请继续。"})
        fixed_messages.append(dict(msg))
    if len(fixed_messages) > 1 and fixed_messages[-1].get("role") == "assistant":
        fixed_messages.append({"role": "user", "content": "请继续发言。"})

    kwargs["messages"] = fixed_messages

    try:
        print(f"[LLM 调用] model={model}, messages_len={len(fixed_messages)}")
        for i, m in enumerate(fixed_messages):
            print(f"  msg[{i}] role={m['role']} content={m['content'][:50]}...")
        response = completion(**kwargs)
        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            yield delta
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[LLM 调用错误] model={model}, error={e}")
        print(error_detail)
        yield f"[调用失败：{e}]"
