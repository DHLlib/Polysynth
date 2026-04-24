#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""辩论赛模式执行器。四轮制：开篇立论→深化论点→攻辩驳论→总结陈词。"""

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


logger = get_logger("modes.debate")

_TOOL_ROLE_GUIDES: dict[str, str] = {
    "pro_1": "作为正方一辩，当你需要引用具体案例或数据支撑论点时，请主动调用搜索工具获取实时信息，增强论证说服力。",
    "pro_2": "作为正方二辩，当你需要补充数据、案例或理论支撑时，请主动调用搜索工具获取实时信息。",
    "con_1": "作为反方一辩，当你需要引用具体案例或数据支撑论点时，请主动调用搜索工具获取实时信息，增强论证说服力。",
    "con_2": "作为反方二辩，当你需要补充数据、案例或理论支撑时，请主动调用搜索工具获取实时信息。",
}


def _build_tool_system_msg(role_key: str, tools: list[dict]) -> str:
    """构建系统级工具使用提示词，放在角色 system prompt 之前以获得更高指令优先级。"""
    tool_desc = "\n".join(
        f"- {t['function']['name']}: {t['function']['description']}"
        for t in tools
    )
    lines = [
        "【系统指令·工具使用】你被赋予了以下工具的使用权限。",
        "",
        tool_desc,
        "",
        "使用规范（必须遵守）：",
        "1. 当任务需要超出你已有知识的信息时，必须主动调用工具",
        "2. 严禁编造数据、案例或事实。如果你提到'数据显示'、'研究表明'、'根据调查'等表述，必须先调用工具获取真实数据",
        "3. 不要假装已经搜索过或已经知道某些数据——如果你不确定，就必须调用工具",
        "4. 调用工具后等待返回结果，再继续发言",
        "5. 违反以上规范会导致回答被视为无效",
    ]
    guide = _TOOL_ROLE_GUIDES.get(role_key)
    if guide:
        lines.extend(["", f"角色补充：{guide}"])
    lines.append("")
    return "\n".join(lines)


# 四轮阶段定义：(阶段名称, [发言角色列表])
ROUND_STAGES = [
    ("开篇立论", ["pro_1", "con_1"]),
    ("深化论点", ["pro_2", "con_2"]),
    ("攻辩驳论", ["pro_3", "con_3"]),
    ("总结陈词", ["con_4", "pro_4"]),  # 反方先总结是标准规则
]


class DebateRunner:
    mode_name = "debate"

    async def run(self, session):
        cfg = session.get_config()
        topic = cfg.topic
        mode_config = cfg.mode_config

        session.save("topic", topic)
        session.save("rounds", len(ROUND_STAGES))

        logger.info(f"Debate start: topic={topic}")
        yield BannerEvent("辩论赛开始")
        yield BannerEvent(f"辩题：{topic}")

        # ── 主持人开场 ──
        opening = mode_config["opening"]
        async for ev in self._run_role(
            session, opening["speaker"], opening["extra_instruction"].format(topic=topic)
        ):
            yield ev

        # ── 四轮辩论 ──
        summary = mode_config["rounds"]["summary"]

        for r, (stage_name, role_keys) in enumerate(ROUND_STAGES, 1):
            session.save("this_round", r)
            logger.info(f"Debate round {r}/{len(ROUND_STAGES)}: {stage_name}")
            yield BannerEvent(f"第 {r} 轮 {stage_name}")

            for role_key in role_keys:
                async for ev in self._run_role(session, role_key):
                    yield ev

            # 主持人总结
            if r == len(ROUND_STAGES):
                extra = summary["final_template"]
            else:
                extra = summary["mid_template"].format(round=r, next_round=r + 1)
            async for ev in self._run_role(session, summary["speaker"], extra):
                yield ev

        logger.info("Debate complete")
        yield BannerEvent("辩论结束")
        yield SessionEndEvent()

    async def _run_role(self, session, role_key: str, extra_instruction: str = ""):
        cfg = session.get_config()
        participant = cfg.participants[role_key]
        system = cfg.prompts[role_key]
        if extra_instruction:
            system += f"\n\n【额外指示】{extra_instruction}"

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

        messages = [{"role": "system", "content": system}]
        if tool_system_msg:
            messages.insert(0, {"role": "system", "content": tool_system_msg})
        messages.extend(session.get_history())
        # 最后一道防线：在 user message 中明确提醒使用工具
        if tools:
            messages.append({"role": "user", "content": "注意：如果你需要引用数据、事实或最新信息，必须先调用可用工具获取真实信息，严禁编造。"})

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
