#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""CLI 入口：支持子命令、交互式提示、配置管理、历史操作。"""

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from backend.core.logger import get_logger
from backend.core.session import Session, SESSION_DIR
from backend.core.output_handlers import TerminalOutputHandler
from backend.core.runtime_config import RuntimeConfig
from backend.datebase.engine import init_db, AsyncSessionLocal
from backend.datebase import crud
from backend.core.config import Config

logger = get_logger("cli")


# ── 辅助函数 ──


def _prompt(text: str, default: str = "") -> str:
    """同步交互式提示。"""
    prompt_text = f"{text}"
    if default:
        prompt_text += f" [{default}]"
    prompt_text += ": "
    result = input(prompt_text).strip()
    return result if result else default


async def _ensure_db_and_seed():
    """确保数据库已初始化，空库时自动 seed。"""
    await init_db()
    async with AsyncSessionLocal() as db:
        modes = await crud.get_mode_configs(db)
        if not modes:
            logger.info("数据库为空，执行 seed...")
            await crud.seed_db_from_files(db)


async def _get_runtime_config(mode: str, topic: str, rounds: int | None = None):
    """从数据库构建 RuntimeConfig，用于 CLI 模式。"""
    async with AsyncSessionLocal() as db:
        cfg = await crud.get_mode_config(db, mode)
        if cfg is None:
            raise ValueError(f"模式未找到: {mode}")
        if rounds is None:
            rounds = cfg.default_rounds
        return await RuntimeConfig.from_db(db, mode, topic)


def _print_message(name: str, content: str, color: str = ""):
    """终端格式化打印单条消息。"""
    reset = "\033[0m"
    bold = "\033[1m"
    c = color if color else ""
    print(f"\n{c}{bold}{name}{reset}")
    print(content)
    print()


# ── 子命令实现 ──


async def cmd_run(args):
    """运行新 session。"""
    await _ensure_db_and_seed()

    mode = args.mode
    topic = args.topic
    rounds = args.rounds

    async with AsyncSessionLocal() as db:
        modes = await crud.get_mode_configs(db)
        mode_names = [m.name for m in modes]

    # 交互式提示
    if not mode:
        print(f"可用模式: {', '.join(mode_names)}")
        mode = _prompt("请选择模式", Config.get().default_mode)

    if mode not in mode_names:
        print(f"错误: 未知模式 '{mode}'。可用: {', '.join(mode_names)}")
        sys.exit(1)

    if not topic:
        default_topic = Config.get().topic if mode == Config.get().default_mode else ""
        topic = _prompt("请输入讨论话题", default_topic)
        if not topic:
            print("话题不能为空")
            sys.exit(1)

    if rounds is None:
        async with AsyncSessionLocal() as db:
            cfg = await crud.get_mode_config(db, mode)
            default_rounds = cfg.default_rounds if cfg else 3
        rounds_str = _prompt("请输入轮次", str(default_rounds))
        rounds = int(rounds_str) if rounds_str.isdigit() else default_rounds

    session_id = uuid.uuid4().hex

    # 创建 DB 记录
    async with AsyncSessionLocal() as db:
        await crud.create_session_record(db, session_id, mode, topic, rounds)

    # 构建 RuntimeConfig
    runtime_cfg = await _get_runtime_config(mode, topic, rounds)

    print(f"\n启动 Session: {session_id}")
    print(f"模式: {mode} | 话题: {topic} | 轮次: {rounds}\n")

    session = Session(session_id, runtime_config=runtime_cfg)
    session.register_output_handler(TerminalOutputHandler())

    try:
        async for _event in session.run():
            pass
    except Exception as e:
        logger.exception(f"Session 运行失败: {e}")
        async with AsyncSessionLocal() as db:
            await crud.update_session_status(db, session_id, "error")
        raise

    # 更新状态
    async with AsyncSessionLocal() as db:
        await crud.update_session_status(db, session_id, "completed")

    print(f"\nSession 完成: {session_id}")


async def cmd_list(args):
    """列出历史 session。"""
    await _ensure_db_and_seed()
    limit = args.limit

    async with AsyncSessionLocal() as db:
        records = await crud.list_session_records(db, limit=limit)

    if not records:
        print("暂无历史 session")
        return

    print(f"{'ID':<34} {'模式':<10} {'轮次':<6} {'状态':<10} {'话题':<30} {'创建时间'}")
    print("-" * 100)
    for r in records:
        topic = (r.topic[:28] + "..") if len(r.topic) > 30 else r.topic
        created = (
            r.created_at.strftime("%Y-%m-%d %H:%M")
            if isinstance(r.created_at, datetime)
            else str(r.created_at)[:16]
        )
        print(
            f"{r.id:<34} {r.mode:<10} {r.rounds:<6} {r.status:<10} {topic:<30} {created}"
        )


async def cmd_replay(args):
    """重放指定 session。优先从数据库读取，fallback 到 jsonl 文件。"""
    session_id = args.session_id

    async with AsyncSessionLocal() as db:
        rec = await crud.get_session_record(db, session_id)

    if rec and rec.messages:
        print(f"重放 Session: {session_id} (来自数据库)\n")
        for msg in rec.messages:
            color = ""
            async with AsyncSessionLocal() as db:
                participants = await crud.get_participants_by_mode(db, rec.mode)
                for p in participants:
                    if p.role_key == msg.role_key:
                        color = p.color or ""
                        break
            _print_message(msg.name, msg.content, color)
        return

    # fallback 到 jsonl
    jsonl_path = SESSION_DIR / f"{session_id}.jsonl"
    if not jsonl_path.exists():
        print(f"未找到 session: {session_id}")
        sys.exit(1)

    print(f"重放 Session: {session_id} (来自文件)\n")
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            _print_message(
                entry.get("name", ""),
                entry.get("content", ""),
                entry.get("color", ""),
            )


async def cmd_status(args):
    """查看当前配置状态。"""
    await _ensure_db_and_seed()

    print("=" * 60)
    print("全局主持人配置")
    print("=" * 60)
    async with AsyncSessionLocal() as db:
        host = await crud.get_global_host(db)
        print(f"  名称: {host.name}")
        print(f"  模型: {host.model}")
        print()

        print("=" * 60)
        print("可用模式")
        print("=" * 60)
        modes = await crud.get_mode_configs(db)
        for m in modes:
            print(f"\n  [{m.name}] {m.display_name}")
            print(f"  默认轮次: {m.default_rounds}")
            print(f"  描述: {m.description or '无'}")
            participants = await crud.get_participants_by_mode(db, m.name)
            for p in participants:
                print(f"    - {p.role_key}: {p.name} ({p.model})")

        print("\n" + "=" * 60)
        print("供应商配置")
        print("=" * 60)
        providers = await crud.get_providers(db)
        for p in providers:
            models = ", ".join(m.model_name for m in p.models) or "无"
            key_display = (
                f"{p.api_key[:3]}****{p.api_key[-4:]}"
                if len(p.api_key) > 4
                else "****"
            )
            print(f"\n  [{p.name}]")
            print(f"    API Key: {key_display}")
            print(f"    Base URL: {p.base_url or '默认'}")
            print(f"    模型: {models}")


async def cmd_config(args):
    """配置管理子命令分发。"""
    await _ensure_db_and_seed()

    sub = args.config_subcommand

    if sub == "host":
        await _config_host(args)
    elif sub == "participants":
        await _config_participants(args)
    elif sub == "providers":
        await _config_providers(args)
    else:
        print("配置子命令: host | participants <mode> | providers")
        print("\n示例:")
        print('  python backend/main.py config host --set-name "主持人"')
        print('  python backend/main.py config participants six_hat --role-key white --set-model "deepseek/deepseek-chat"')
        print('  python backend/main.py config providers --provider deepseek --set-key "sk-xxx"')
        sys.exit(1)


async def _config_host(args):
    """查看/修改全局主持人。"""
    async with AsyncSessionLocal() as db:
        host = await crud.get_global_host(db)

        if args.set_name or args.set_model:
            kwargs = {}
            if args.set_name:
                kwargs["name"] = args.set_name
            if args.set_model:
                kwargs["model"] = args.set_model
            await crud.update_global_host(db, **kwargs)
            print("全局主持人已更新")
        else:
            print(f"名称: {host.name}")
            print(f"模型: {host.model}")
            print(f"颜色: {host.color} (固定不可修改)")


async def _config_participants(args):
    """查看/修改某模式的参与者。"""
    mode = args.mode_name
    if not mode:
        print("请指定模式名")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        participants = await crud.get_participants_by_mode(db, mode)
        if not participants:
            print(f"模式 '{mode}' 未找到或无参与者")
            sys.exit(1)

        if args.set_model or args.set_name:
            role_key = args.role_key
            if not role_key:
                print("修改参与者需要指定 --role-key")
                sys.exit(1)

            p = None
            for part in participants:
                if part.role_key == role_key:
                    p = part
                    break

            if not p:
                print(f"角色 '{role_key}' 未找到")
                sys.exit(1)

            kwargs = {}
            if args.set_model:
                kwargs["model"] = args.set_model
            if args.set_name:
                kwargs["name"] = args.set_name

            await crud.update_participant(db, p.id, **kwargs)
            print(f"参与者 '{role_key}' 已更新")
        else:
            print(f"模式 '{mode}' 的参与者:")
            for p in participants:
                print(f"  [{p.role_key}] {p.name} ({p.model})")


async def _config_providers(args):
    """查看/修改供应商配置。"""
    async with AsyncSessionLocal() as db:
        providers = await crud.get_providers(db)

        if args.set_key or args.set_base_url or args.add_model:
            provider_name = args.provider_name
            if not provider_name:
                print("请指定供应商名 --provider")
                sys.exit(1)

            provider = None
            for p in providers:
                if p.name == provider_name:
                    provider = p
                    break

            if not provider:
                print(f"供应商 '{provider_name}' 未找到")
                sys.exit(1)

            kwargs = {}
            if args.set_key:
                kwargs["api_key"] = args.set_key
            if args.set_base_url:
                kwargs["base_url"] = args.set_base_url

            if kwargs:
                from backend.core.agent_generator import _sanitize_str, clear_provider_cache

                if "api_key" in kwargs:
                    kwargs["api_key"] = _sanitize_str(kwargs["api_key"]) or ""
                if "base_url" in kwargs:
                    kwargs["base_url"] = _sanitize_str(kwargs["base_url"])
                await crud.update_provider(db, provider.id, **kwargs)
                clear_provider_cache()
                print(f"供应商 '{provider_name}' 已更新")

            if args.add_model:
                await crud.create_provider_model(db, provider.id, args.add_model)
                from backend.core.agent_generator import clear_provider_cache
                clear_provider_cache()
                print(f"模型 '{args.add_model}' 已添加到 '{provider_name}'")
        else:
            print("供应商配置:")
            for p in providers:
                models = ", ".join(m.model_name for m in p.models) or "无"
                key_display = (
                    f"{p.api_key[:3]}****{p.api_key[-4:]}"
                    if len(p.api_key) > 4
                    else "****"
                )
                print(f"\n  [{p.name}]")
                print(f"    API Key: {key_display}")
                print(f"    Base URL: {p.base_url or '默认'}")
                print(f"    模型: {models}")


# ── 参数解析 ──


def _build_parser():
    """构建 argparse 解析器。"""
    parser = argparse.ArgumentParser(
        description="Polysynth CLI - 多 LLM Agent 讨论模拟器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 直接运行（向后兼容）
  python backend/main.py
  python backend/main.py --mode six_hat --topic "AI的未来" --rounds 3

  # 子命令
  python backend/main.py run --mode six_hat --topic "AI的未来"
  python backend/main.py list
  python backend/main.py replay <session_id>
  python backend/main.py status
  python backend/main.py config host --set-name "主持人"
  python backend/main.py config participants six_hat --role-key white --set-model "deepseek/deepseek-chat"
  python backend/main.py config providers --provider deepseek --set-key "sk-xxx"
        """,
    )

    # 为向后兼容，顶层也接受 run 的参数
    parser.add_argument("--mode", "-m", help="讨论模式 (six_hat/debate)")
    parser.add_argument("--topic", "-t", help="讨论话题")
    parser.add_argument("--rounds", "-r", type=int, help="轮次")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run
    run_parser = subparsers.add_parser("run", help="运行新 session")
    run_parser.add_argument("--mode", "-m", help="讨论模式")
    run_parser.add_argument("--topic", "-t", help="讨论话题")
    run_parser.add_argument("--rounds", "-r", type=int, help="轮次")

    # list
    list_parser = subparsers.add_parser("list", help="列出历史 session")
    list_parser.add_argument("--limit", "-n", type=int, default=20, help="数量限制")

    # replay
    replay_parser = subparsers.add_parser("replay", help="重放指定 session")
    replay_parser.add_argument("session_id", help="Session ID")

    # status
    subparsers.add_parser("status", help="查看当前配置状态")

    # config
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_sub = config_parser.add_subparsers(
        dest="config_subcommand", help="配置子命令"
    )

    # config host
    host_parser = config_sub.add_parser("host", help="全局主持人配置")
    host_parser.add_argument("--set-name", help="设置名称")
    host_parser.add_argument("--set-model", help="设置模型")

    # config participants
    part_parser = config_sub.add_parser("participants", help="参与者配置")
    part_parser.add_argument("mode_name", nargs="?", help="模式名")
    part_parser.add_argument("--role-key", help="角色 key")
    part_parser.add_argument("--set-model", help="设置模型")
    part_parser.add_argument("--set-name", help="设置名称")

    # config providers
    prov_parser = config_sub.add_parser("providers", help="供应商配置")
    prov_parser.add_argument("--provider", help="供应商名")
    prov_parser.add_argument("--set-key", help="设置 API Key")
    prov_parser.add_argument("--set-base-url", help="设置 Base URL")
    prov_parser.add_argument("--add-model", help="添加模型")

    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    # 判断是否有显式子命令
    # argparse 在有子命令时会把 command 设为子命令名，否则为 None
    if args.command is None:
        # 没有子命令：向后兼容，默认执行 run
        # 但如果用户只输入了 --help，argparse 已经处理了
        args.command = "run"

    asyncio.run(_async_main(args))


async def _async_main(args):
    command = args.command
    if command == "run":
        await cmd_run(args)
    elif command == "list":
        await cmd_list(args)
    elif command == "replay":
        await cmd_replay(args)
    elif command == "status":
        await cmd_status(args)
    elif command == "config":
        await cmd_config(args)
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
