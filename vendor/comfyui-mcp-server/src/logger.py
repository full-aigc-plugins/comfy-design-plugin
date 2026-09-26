"""
Centralised Logger / 统一日志器

Provides the project-wide `logger` singleton via loguru. All application
modules should import `logger` exclusively from this module to ensure
consistent formatting and destination routing.

通过 loguru 提供项目全局 `logger` 单例。
所有应用模块应仅从此模块导入 `logger`，
以确保一致的格式化和输出目标路由。

Configured via environment variables / 通过环境变量配置:
  LOG_LEVEL  — Minimum log level (DEBUG / INFO / WARNING / ERROR). Default: INFO
  LOG_FILE   — Optional path for file output. Default: (disabled)
  LOG_ROTATE — File rotation size trigger. Default: "10 MB"
  LOG_RETAIN — Number of rotated files to keep. Default: 7
"""

import os
import sys
from loguru import logger

# ---------------------------------------------------------------------------
# Unified logger for the project. Import `logger` from here; do NOT create
# separate loggers elsewhere. Configuration via LOG_LEVEL / LOG_FILE /
# LOG_ROTATE / LOG_RETAIN env vars (see module docstring for details).
# 项目统一日志器。所有模块从此处导入 `logger`，禁止在别处另建日志器。
# 通过 LOG_LEVEL / LOG_FILE / LOG_ROTATE / LOG_RETAIN 环境变量配置（详见模块文档字符串）。
# ---------------------------------------------------------------------------


_STDERR_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

_FILE_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
    "{name}:{function}:{line} - {message}"
)

# Read configuration from env (dotenv is loaded earlier in config.py,
# but logger.py does its own os.getenv calls to stay dependency-free).
_level   = os.getenv("LOG_LEVEL",  "INFO").strip().upper()
_file    = os.getenv("LOG_FILE",   "").strip()
_rotate  = os.getenv("LOG_ROTATE", "10 MB").strip()
_retain  = os.getenv("LOG_RETAIN", "7").strip()

# MCP server communicates with the host over stdout (JSON-RPC).
# Logs MUST go to stderr to avoid corrupting the protocol stream.
# MCP 服务器通过 stdout 与客户端通信（JSON-RPC）。
# 日志必须写入 stderr——否则会破坏协议流。
logger.remove()
logger.add(
    sys.stderr,
    format=_STDERR_FMT,
    level=_level,
    colorize=True,
)

# Optional file sink — enabled only when LOG_FILE is set.
# 可选文件输出——仅当 LOG_FILE 已配置时启用。
if _file:
    try:
        logger.add(
            _file,
            format=_FILE_FMT,
            level=_level,
            rotation=_rotate,
            retention=int(_retain),
            encoding="utf-8",
            enqueue=True,   # thread-safe non-blocking writes / 线程安全的非阻塞异步写入
        )
        logger.info(f"File logging enabled: {_file} (level={_level}, rotate={_rotate}, retain={_retain})")
    except Exception as e:
        logger.warning(f"Failed to configure file logging ({_file}): {e}")
