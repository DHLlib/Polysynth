#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""辩论赛模式执行器。四轮制：开篇立论→深化论点→攻辩驳论→总结陈词。"""

from backend.core.agent_generator import call_llm
from backend.datebase.stream_events import (
    BannerEvent,
    SessionEndEvent,
    TurnEndEvent,
    TurnStartEvent,
    TokenEvent,
)


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

        yield BannerEvent("辩论结束")
        yield SessionEndEvent()

    async def _run_role(self, session, role_key: str, extra_instruction: str = ""):
        cfg = session.get_config()
        participant = cfg.participants[role_key]
        system = cfg.prompts[role_key]
        if extra_instruction:
            system += f"\n\n【额外指示】{extra_instruction}"

        messages = [{"role": "system", "content": system}] + session.get_history()

        yield TurnStartEvent(
            role_key=role_key,
            role_name=participant["name"],
            color=participant.get("color", ""),
        )

        full_reply = ""
        async for token in call_llm(session, participant["model"], messages, cfg):
            yield TokenEvent(role_key=role_key, token=token)
            full_reply += token

        yield TurnEndEvent(role_key=role_key, full_content=full_reply)
