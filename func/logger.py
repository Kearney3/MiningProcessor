"""
通用日志管理模块
提供跨脚本和 GUI 的统一日志接口
"""
import logging
import sys
from datetime import datetime

# 默认日志格式“[日志级别]时间戳(秒级)｜文件名｜消息内容”
DEFAULT_FORMAT = "[%(levelname)s]%(asctime)s | %(filename)s | %(message)s"


class QueueHandler(logging.Handler):
    """将日志记录推送到队列的 Handler，支持 asyncio.Queue 与 queue.Queue，跨线程实时输出"""

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            msg = self.format(record)
            payload = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
                "levelno": record.levelno,
                "levelname": record.levelname,
                "message": msg,
            }
            if hasattr(self.queue, "put_nowait"):
                self.queue.put_nowait(payload)
            else:
                self.queue.put(payload, block=False)
        except Exception:
            self.handleError(record)


def setup_logging(level=logging.INFO):
    """设置默认的控制台日志输出（命令行直接运行脚本时使用）"""
    root = logging.getLogger()
    root.setLevel(level)

    # 避免重复添加（例如 GUI 和脚本同时初始化时）
    for h in list(root.handlers):
        if isinstance(h, logging.StreamHandler) and not isinstance(h, QueueHandler):
            root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)


def get_logger(name: str | None = None) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)
