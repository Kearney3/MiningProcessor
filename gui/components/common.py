"""GUI 组件共享工具函数与状态"""
import logging
from pathlib import Path

# 共享的文件选择器上次目录，所有模块复用同一份
# 使用列表以便在各模块内原地更新，保证跨模块可见
_last_directory: list[str] = [""]


def _log_message(log, message: str, level: int = logging.INFO):
    """兼容仅接收 message 的旧回调，也支持显式日志级别。"""
    try:
        log(message, level=level)
    except TypeError:
        log(message)


def _update_last_directory(path: str) -> None:
    """统一更新共享的文件选择器目录。"""
    _last_directory[0] = str(Path(path).parent)
