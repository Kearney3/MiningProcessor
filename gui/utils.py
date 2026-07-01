"""GUI 通用工具函数。

提供日志适配、控件安全更新等跨组件复用的辅助功能。
"""
from __future__ import annotations

import logging


def _log_message(log, message: str, level: int = logging.INFO):
    """兼容仅接收 message 的旧回调，也支持显式日志级别。"""
    try:
        log(message, level=level)
    except TypeError:
        log(message)
