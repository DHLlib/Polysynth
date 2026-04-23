#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""AI 文件摘要生成模块。"""

from litellm import acompletion

from backend.core.config import Config
from backend.core.logger import get_logger

logger = get_logger("summarizer")

_SUMMARY_PROMPT = """你是文件摘要专家。请对以下文件内容生成结构化摘要，要求：
1. 字数控制在 500~1000 字
2. 包含核心观点、关键数据和重要结论
3. 使用客观陈述，不要加入评价
4. 如果内容涉及数据，请保留关键数字
5. 如果文件是表格数据，请总结主要趋势和异常值

文件内容：
{text}

请生成摘要："""


async def summarize_text(text: str, model: str) -> str:
    """调用 LLM 生成文本摘要。"""
    if not text or not text.strip():
        return ""

    # 截断过长文本，避免超限
    max_input = 15000  # 约 5000 tokens
    if len(text) > max_input:
        text = text[:max_input] + "\n...[内容已截断]"

    messages = [
        {"role": "system", "content": "你是专业的文件摘要生成助手。"},
        {"role": "user", "content": _SUMMARY_PROMPT.format(text=text)},
    ]

    cfg = Config.get()
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "stream": False,
        "timeout": 120,
    }

    # 模型路由（兼容旧逻辑）
    if "moonshot" in model:
        kwargs["api_key"] = cfg.kimi_api_key
        kwargs["api_base"] = cfg.kimi_base_url
    elif "deepseek" in model:
        kwargs["api_key"] = cfg.deepseek_api_key

    try:
        resp = await acompletion(**kwargs)
        summary = resp.choices[0].message.content or ""
        summary = summary.strip()
        logger.info(f"Summary generated: model={model}, input_len={len(text)}, output_len={len(summary)}")
        return summary
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return ""
