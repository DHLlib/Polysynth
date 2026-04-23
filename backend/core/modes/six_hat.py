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
    TurnEndEvent,
    TurnStartEvent,
    TokenEvent,
)


logger = get_logger("modes.six_hat")


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
                # 根据角色定制工具使用引导
                if role_key == "white":
                    usage_guide = (
                        "当你缺乏确切数据、需要验证某个事实或获取最新统计信息时，"
                        "请主动调用搜索工具获取实时信息，而不是直接说'缺乏数据'。"
                    )
                else:
                    usage_guide = "需要时请调用工具并等待结果。"
                system += (
                    f"\n\n【工具说明】你可以使用以下工具辅助思考：\n{tool_desc}\n"
                    f"{usage_guide}\n"
                    "调用工具后，等待返回结果再继续发言。"
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
