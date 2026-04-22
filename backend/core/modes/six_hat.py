#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""六顶思考帽模式执行器。"""

from backend.core.agent_generator import call_llm
from backend.datebase.stream_events import (
    BannerEvent,
    SessionEndEvent,
    TurnEndEvent,
    TurnStartEvent,
    TokenEvent,
)


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

        yield BannerEvent("讨论结束")
        yield SessionEndEvent()

    async def _run_role(self, session, role_key: str, extra_instruction: str = ""):
        cfg = session.get_config()
        participant = cfg.participants[role_key]
        system = cfg.prompts[role_key]
        if extra_instruction:
            system += f"\n\n【本次额外指示】{extra_instruction}"

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
