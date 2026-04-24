#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""六顶思考帽模式执行器。"""

import json

from backend.core.agent_generator import call_llm
from backend.core.logger import get_logger
from backend.core.tools import get_tool_schemas
from backend.datebase.stream_events import (
    BannerEvent,
    SessionEndEvent,
    ToolEndEvent,
    ToolStartEvent,
    TokenEvent,
    TurnEndEvent,
    TurnStartEvent,
)


logger = get_logger("modes.six_hat")


_TOOL_ROLE_GUIDES: dict[str, str] = {
    "white": "作为事实分析师，当你缺乏确切数据或需要验证某个事实时，请主动调用搜索工具获取实时信息，而不是直接说'缺乏数据'。",
}


def _build_tool_system_msg(role_key: str, tools: list[dict]) -> str:
    """构建系统级工具使用提示词，合并到角色 system prompt 中。"""
    tool_desc = "\n".join(
        f"- {t['function']['name']}: {t['function']['description']}"
        for t in tools
    )
    lines = [
        "【最高优先级指令·工具调用】",
        "你被赋予了以下工具，每次发言前必须先调用工具获取信息，然后基于工具结果回答。",
        "无论你是否认为自己知道答案，都必须先调用工具。直接回答而不调用工具将被视为违规。",
        "",
        tool_desc,
        "",
        "使用规范（必须遵守）：",
        "1. 每次发言必须先调用工具获取最新信息，严禁直接回答",
        "2. 严禁编造数据、案例或事实。所有数据必须来自工具返回结果",
        "3. 不要假装已经搜索过——每次都必须重新调用工具",
        "4. 调用工具后等待返回结果，再继续发言",
        "5. 违反以上规范会导致回答被视为无效",
        "",
        "示例（必须遵循此流程）：",
        "场景：需要查找2024年全球新能源汽车销量数据。",
        "正确做法：",
        '  1. 立即调用 search 工具，query="2024年全球新能源汽车销量"',
        "  2. 等待工具返回搜索结果",
        '  3. 基于搜索结果回答："根据搜索结果，2024年全球新能源汽车销量约为..."',
        "错误做法（严禁）：",
        '  直接回答："根据我的知识，2024年全球新能源汽车销量大约是1000万辆。" ← 这是编造数据！',
    ]
    guide = _TOOL_ROLE_GUIDES.get(role_key)
    if guide:
        lines.extend(["", f"角色补充：{guide}"])
    lines.append("")
    return "\n".join(lines)


class SixHatRunner:
    mode_name = "six_hat"

    async def run(self, session):
        cfg = session.get_config()
        topic = cfg.topic
        rounds = cfg.rounds
        mode_config = cfg.mode_config
        participants = cfg.participants

        session.save("topic", topic)
        session.save("rounds", rounds)

        logger.info(f"SixHat start: topic={topic}, rounds={rounds}")
        yield BannerEvent("六顶思考帽讨论开始")
        yield BannerEvent(f"话题：{topic}")

        # ── 蓝帽开场 ──
        opening = mode_config["opening"]
        async for ev in self._run_role(
            session, opening["speaker"], opening["extra_instruction"].format(topic=topic)
        ):
            yield ev

        # ── 逐轮讨论 ──
        for r in range(1, rounds + 1):
            session.save("this_round", r)
            logger.info(f"SixHat round {r}/{rounds}")
            yield BannerEvent(f"第 {r} 轮讨论")

            for role_key in mode_config["rounds"]["speaking_order"]:
                async for ev in self._run_role(session, role_key):
                    yield ev

            # 蓝帽总结
            summary = mode_config["rounds"]["summary"]
            if r == rounds:
                extra = summary["final_template"]
            else:
                extra = summary["mid_template"].format(round=r, next_round=r + 1)
            async for ev in self._run_role(session, summary["speaker"], extra):
                yield ev

        logger.info("SixHat complete")
        yield BannerEvent("讨论结束")
        yield SessionEndEvent()

    async def _run_role(self, session, role_key: str, extra_instruction: str = ""):
        cfg = session.get_config()
        participant = cfg.participants[role_key]
        system = cfg.prompts[role_key]
        if extra_instruction:
            system += f"\n\n【本次额外指示】{extra_instruction}"

        # ── 注入附件摘要 ──
        from backend.datebase.engine import AsyncSessionLocal
        from backend.datebase.crud import get_attachments_by_session
        try:
            async with AsyncSessionLocal() as db:
                attachments = await get_attachments_by_session(db, session.session_id)
                if attachments:
                    parts = ["\n\n【背景资料】\n以下是从用户上传文件中提取的摘要，请在讨论中充分参考："]
                    for att in attachments:
                        if att.summary:
                            parts.append(f"\n[文件: {att.filename}]\n{att.summary}")
                    system += "\n".join(parts)
        except Exception as e:
            logger.warning(f"Failed to load attachments: {e}")

        # 检查并注入工具（系统级提示词放在角色定义之前，获得更高优先级）
        tools = None
        tool_system_msg = ""
        tools_enabled_str = participant.get("tools_enabled")
        if tools_enabled_str:
            try:
                enabled_names = json.loads(tools_enabled_str)
            except json.JSONDecodeError:
                logger.warning(f"Invalid tools_enabled JSON for {role_key}: {tools_enabled_str}")
                enabled_names = []
            if enabled_names:
                tools = get_tool_schemas(enabled_names)
                logger.info(f"Tools enabled for {role_key}: {enabled_names}")
                tool_system_msg = _build_tool_system_msg(role_key, tools)

        # 合并工具指令和角色 system prompt 为一条，避免优先级竞争
        if tool_system_msg:
            system = tool_system_msg + "\n\n" + system
        messages = [{"role": "system", "content": system}]
        messages.extend(session.get_history())

        logger.info(f"Role speak: {role_key}, model={participant['model']}, history={len(messages)}")
        yield TurnStartEvent(
            role_key=role_key,
            role_name=participant["name"],
            color=participant.get("color", ""),
        )

        full_reply = ""
        async for item in call_llm(session, participant["model"], messages, cfg, tools=tools, role_key=role_key):
            if isinstance(item, str):
                yield TokenEvent(role_key=role_key, token=item)
                full_reply += item
            else:
                yield item

        logger.info(f"Role end: {role_key}, content_len={len(full_reply)}")
        yield TurnEndEvent(role_key=role_key, full_content=full_reply)
