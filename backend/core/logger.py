#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""统一日志配置。"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

_handler_console = logging.StreamHandler(sys.stdout)
_handler_console.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))

_handler_file = TimedRotatingFileHandler(
    _LOG_DIR / "app.log",
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
)
_handler_file.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器。支持 LOG_LEVEL 环境变量调整级别。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler_console)
        logger.addHandler(_handler_file)
    logger.setLevel(_LOG_LEVEL)
    return logger
