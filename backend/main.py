#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""入口文件：创建 Session，注册终端输出处理器，启动讨论。"""

import asyncio
import uuid

from backend.core.session import session_create


async def run():
    session_id = uuid.uuid4().hex
    await session_create(session_id=session_id)


if __name__ == "__main__":
    asyncio.run(run())
