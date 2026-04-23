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
    TurnEndEvent,
    TurnStartEvent,
    TokenEvent,
)


logger = get_logger("modes.debate")

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

        # 检查并注入工具
        tools = None
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
                tool_desc = "\n".join(
                    f"- {t['function']['name']}: {t['function']['description']}"
                    for t in tools
                )
                system += (
                    f"\n\n【工具说明】你可以使用以下工具辅助思考：\n{tool_desc}\n"
                    "需要时请调用工具并等待结果。"
                )

        messages = [{"role": "system", "content": system}] + session.get_history()

        logger.info(f"Role speak: {role_key}, model={participant['model']}, history={len(messages)}")
        yield TurnStartEvent(
            role_key=role_key,
            role_name=participant["name"],
            color=participant.get("color", ""),
        )

        full_reply = ""
        async for token in call_llm(session, participant["model"], messages, cfg, tools=tools):
            yield TokenEvent(role_key=role_key, token=token)
            full_reply += token

        logger.info(f"Role end: {role_key}, content_len={len(full_reply)}")
        yield TurnEndEvent(role_key=role_key, full_content=full_reply)
