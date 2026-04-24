#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
LLM 调用层。只负责异步流式调用，不处理打印、历史或 session 记录。
"""

import json
import re

from litellm import acompletion

from backend.core.config import Config
from backend.core.logger import get_logger
from backend.core.tools import get_tool_schemas, execute_tool
from backend.datebase.stream_events import ToolStartEvent, ToolEndEvent

logger = get_logger("agent_generator")

# 单次 Session 内缓存 provider 配置，避免重复查库
_provider_cache: dict[str, dict] = {}


def _clean_llm_content(text: str) -> str:
    """统一清洗 LLM 返回的 content，移除 DeepSeek DSML 工具调用标记。

    这是 LLM 输出进入系统内部流动的唯一清洗边界。
    所有从 LLM 获得的 content（无论是 msg.content 还是流式 delta）
    在 yield 给下游或存入上下文前，都必须经过此函数。
    """
    if not text or "<｜DSML｜" not in text:
        return text

    lines = []
    skip_depth = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("<｜DSML｜"):
            skip_depth += 1
            continue
        if stripped.startswith("</｜DSML｜"):
            skip_depth = max(0, skip_depth - 1)
            continue
        if skip_depth <= 0:
            lines.append(line)
    return "\n".join(lines)


def clear_provider_cache() -> None:
    """清除 provider 缓存，在配置更新后调用。"""
    _provider_cache.clear()
    logger.info("Provider cache cleared")


async def _summarize_search_query(
    topic: str,
    history: list[dict],
    original_query: str,
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
) -> str:
    """根据话题和讨论历史，用 AI 优化搜索关键词。"""
    logger.info(f"[SearchQuery·Start] topic='{topic}', original='{original_query}', history={len(history)}")
    recent = history[-5:] if history else []
    history_text = "\n".join(
        f"{m['role']}: {str(m.get('content', ''))[:200]}"
        for m in recent
    )

    summarize_messages = [
        {
            "role": "system",
            "content": (
                "你是搜索关键词优化专家。根据讨论话题、讨论历史和原始搜索意图，"
                "生成最精准、最简洁的搜索关键词。只输出关键词，不要加任何解释、标点或格式。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"话题：{topic}\n\n"
                f"讨论历史：\n{history_text}\n\n"
                f"原始搜索意图：{original_query}\n\n"
                "请生成优化后的搜索关键词（不超过30字）："
            ),
        },
    ]

    llm_kwargs = {
        "model": model,
        "messages": summarize_messages,
        "temperature": 0.3,
        "stream": False,
    }
    if api_key:
        llm_kwargs["api_key"] = api_key
    if api_base:
        llm_kwargs["api_base"] = api_base

    try:
        resp = await acompletion(**llm_kwargs)
        content = _clean_llm_content(resp.choices[0].message.content or "")
        query = content.strip().strip('"\'').strip()
        logger.info(f"[SearchQuery] original='{original_query}' -> optimized='{query}'")
        return query if query else original_query
    except Exception as e:
        logger.warning(f"Search query summarization failed: {e}, fallback to original")
        return original_query


async def _resolve_provider(model: str) -> dict:
    """通过 model 名称从数据库查询对应的 provider 配置。"""
    if model in _provider_cache:
        logger.debug(f"Provider cache hit: {model}")
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
                logger.info(f"Provider resolved: {model} -> {provider.name}")
                return result
    except Exception as e:
        logger.warning(f"Failed to resolve provider for {model}: {e}")

    logger.warning(f"No provider found for {model}, fallback to Config")
    return {}


async def call_llm(session, model: str, messages: list, cfg=None, tools: list[dict] | None = None, role_key: str = ""):
    """
    底层异步流式调用 LLM。

    :param session: Session 对象
    :param model: LiteLLM 模型名
    :param messages: 完整消息列表
    :param cfg: RuntimeConfig 或 Config 实例
    :param tools: OpenAI function schema 列表，传入时启用工具调用
    :param role_key: 角色标识，用于工具事件
    :yield: 每个流式 token (str) 或工具事件对象
    """
    if cfg is None:
        cfg = Config.get()

    tools_enabled = tools is not None and len(tools) > 0
    kwargs = {
        "model": model,
        "temperature": 0.3 if tools_enabled else 0.8,
        "timeout": 180,
    }

    # 从数据库解析 provider 配置
    provider_cfg = await _resolve_provider(model)
    if provider_cfg.get("api_key"):
        kwargs["api_key"] = provider_cfg["api_key"]
    if provider_cfg.get("base_url"):
        kwargs["api_base"] = provider_cfg["base_url"]

    # 兼容旧逻辑
    if "api_key" not in kwargs:
        if "moonshot" in model:
            kwargs["api_key"] = cfg.kimi_api_key
            kwargs["api_base"] = cfg.kimi_base_url
        elif "deepseek" in model:
            kwargs["api_key"] = cfg.deepseek_api_key

    # 修复 messages 格式
    fixed_messages = []
    for msg in messages:
        if msg.get("role") == "assistant" and fixed_messages and fixed_messages[-1].get("role") == "assistant":
            fixed_messages.append({"role": "user", "content": "请继续。"})
        fixed_messages.append(dict(msg))
    if len(fixed_messages) > 1 and fixed_messages[-1].get("role") == "assistant":
        fixed_messages.append({"role": "user", "content": "请继续发言。"})

    # 如果启用了工具，追加一条强引导 user message 确保触发 function calling
    if tools_enabled:
        tool_names = [t["function"]["name"] for t in tools]
        fixed_messages.append({
            "role": "user",
            "content": (
                f"【强制任务】你现在必须先调用 {'/'.join(tool_names)} 工具获取信息，"
                "等待结果返回后，再基于工具结果组织你的发言。"
                "严禁直接回答，严禁编造数据。"
            ),
        })

    kwargs["messages"] = fixed_messages

    # ── Tool 调用：双阶段 ──
    if tools_enabled:
        try:
            tool_names = [t["function"]["name"] for t in tools]
            logger.info(f"[LLM·Tools] model={model}, tools={tool_names}, messages={len(fixed_messages)}")

            # 阶段一：非流式，检测 tool_calls（带重试机制）
            max_retries = 3
            retry_count = 0
            current_messages = list(fixed_messages)
            phase1_kwargs_base = {**kwargs, "tools": tools, "stream": False, "tool_choice": "auto"}

            while retry_count < max_retries:
                phase1_kwargs = {**phase1_kwargs_base, "messages": current_messages}
                logger.debug(f"[LLM·Tools·Phase1·Request] messages={json.dumps(current_messages[-2:], ensure_ascii=False)}")
                response = await acompletion(**phase1_kwargs)
                msg = response.choices[0].message

                tc_list = getattr(msg, "tool_calls", None)
                tc_count = len(tc_list) if tc_list else 0
                content_preview = _clean_llm_content(msg.content or "")[:80] if msg.content else "(none)"
                if tc_list:
                    tc_details = ", ".join(
                        f"{tc.function.name}({tc.function.arguments})" for tc in tc_list
                    )
                    logger.info(f"[LLM·Tools·Phase1] model={model}, tool_calls={tc_count}, details=[{tc_details}], content={content_preview}...")
                else:
                    logger.info(f"[LLM·Tools·Phase1] model={model}, tool_calls=0, content={content_preview}...")

                if tc_list:
                    break  # 成功触发工具，跳出重试循环

                # 未触发工具，准备重试
                retry_count += 1
                if retry_count < max_retries:
                    if msg.content:
                        current_messages.append({"role": "assistant", "content": _clean_llm_content(msg.content)})
                    current_messages.append({
                        "role": "user",
                        "content": (
                            f"【系统纠正】你刚才没有调用工具，这严重违反了最高优先级指令。"
                            f"你必须调用 {'/'.join(tool_names)} 工具获取信息后再回答。"
                            f"这是第 {retry_count} 次提醒，请立即调用工具。"
                        ),
                    })
                    logger.warning(f"[LLM·Tools·Retry] model={model}, attempt={retry_count}/{max_retries}")
                else:
                    logger.warning(f"[LLM·Tools·Retry] model={model}, max retries ({max_retries}) exceeded")

            tool_names = [t["function"]["name"] for t in tools]

            if tc_list:
                # 发送工具开始事件
                for tc in tc_list:
                    if role_key:
                        yield ToolStartEvent(role_key=role_key, tool_name=tc.function.name)

                # 执行工具
                tool_results = []
                for tc in msg.tool_calls:
                    fn = tc.function
                    args = json.loads(fn.arguments) if fn.arguments else {}
                    logger.info(f"[ToolCall] {fn.name} args={args}")

                    # search 工具：先由 AI 根据 topic + history 优化搜索关键词
                    if fn.name == "search":
                        topic = session.load("topic") or ""
                        history = session.get_history()
                        original_query = args.get("query", "")
                        optimized = await _summarize_search_query(
                            topic=topic,
                            history=history,
                            original_query=original_query,
                            model=kwargs.get("model"),
                            api_key=kwargs.get("api_key"),
                            api_base=kwargs.get("api_base"),
                        )
                        args["query"] = optimized
                        result = await execute_tool(fn.name, args)
                    else:
                        result = await execute_tool(fn.name, args)

                    logger.info(f"[ToolResult] {fn.name} result_len={len(result)}")
                    logger.debug(f"[ToolResult·Detail] {result[:500]}...")
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn.name,
                        "content": result,
                    })

                # 发送工具结束事件（带结果预览）
                if role_key:
                    for tr in tool_results:
                        preview = tr["content"][:200] + "..." if len(tr["content"]) > 200 else tr["content"]
                        yield ToolEndEvent(role_key=role_key, tool_name=tr["name"], preview=preview)

                # 把 assistant 的 tool_calls 和 tool results 追加到 messages
                phase1_content = _clean_llm_content(msg.content or "")
                assistant_msg = {
                    "role": "assistant",
                    "content": phase1_content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                }
                phase2_messages = fixed_messages + [assistant_msg] + tool_results

                # 阶段二：流式输出最终答案（创意阶段，恢复高 temperature）
                logger.info(f"[LLM·Tools·Phase2] model={model}, messages={len(phase2_messages)}")
                phase2_kwargs = {**kwargs, "messages": phase2_messages, "stream": True, "tool_choice": "none", "temperature": 0.8}
                response2 = await acompletion(**phase2_kwargs)
                full_reply = ""
                async for chunk in response2:
                    delta = chunk.choices[0].delta.content or ""
                    # 清洗 LLM 输出，过滤 DeepSeek DSML 标记
                    delta = _clean_llm_content(delta)
                    if delta:
                        yield delta
                        full_reply += delta

                # 将工具调用上下文写入 session history，确保后续轮次可见
                tool_summary = "\n\n".join(
                    f"[{tr['name']} 结果]\n{tr['content'][:300]}"
                    for tr in tool_results
                )
                history_entry = f"{full_reply}\n\n【工具调用记录】\n{tool_summary}"
                session.add_history("assistant", history_entry)
                return

            # LLM 直接回答了，没有调用工具——仍然发送工具事件，告知前端"未触发"
            if role_key and tool_names:
                for name in tool_names:
                    yield ToolStartEvent(role_key=role_key, tool_name=name)
                    yield ToolEndEvent(role_key=role_key, tool_name=name, preview="模型未触发工具调用，直接回答")
            logger.info(f"[LLM·Tools] model={model}, no tool_calls, direct reply")
            direct_content = _clean_llm_content(msg.content or "")
            if direct_content:
                for ch in direct_content:
                    yield ch
            return

        except Exception as e:
            logger.exception(f"[LLM·Tools·Error] model={model}, error={e}")
            yield f"[调用失败：{e}]"
            return

    # ── 普通流式调用（无 tools）──
    try:
        kwargs["stream"] = True
        logger.info(f"[LLM] model={model}, messages={len(fixed_messages)}")
        for i, m in enumerate(fixed_messages):
            content_preview = str(m.get("content", ""))[:80].replace("\n", " ")
            logger.debug(f"  msg[{i}] role={m['role']} content={content_preview}...")
        response = await acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            delta = _clean_llm_content(delta)
            if delta:
                yield delta
    except Exception as e:
        logger.exception(f"[LLM·Error] model={model}, error={e}")
        yield f"[调用失败：{e}]"
