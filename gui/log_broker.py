"""进程级 GUI 日志分发。

logging 是进程级基础设施，Flet Page 则是会话级对象。这个模块在两者之间
提供一个稳定边界：root logger 只安装一个 handler，每个页面拥有独立订阅。
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
import threading
from typing import Callable
import weakref

from func.logger import DEFAULT_FORMAT


_NOISY_LOGGERS = frozenset(
    {
        "flet",
        "flet_components",
        "flet_controls",
        "flet_object_patch",
        "flet_transport",
        "asyncio",
        "uvicorn",
        "watchfiles",
    }
)


@dataclass(frozen=True, slots=True)
class LogEntry:
    sequence: int
    created: float
    levelno: int
    levelname: str
    logger_name: str
    message: str


class _GuiNoiseFilter(logging.Filter):
    """只过滤 GUI 输出，不改变第三方 logger 或控制台日志策略。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.INFO:
            return True
        name = record.name or ""
        return not any(name == prefix or name.startswith(prefix + ".") for prefix in _NOISY_LOGGERS)


class LogSubscription:
    """线程安全的有界页面日志邮箱。"""

    def __init__(self, notify: Callable[[], None], capacity: int):
        self._notify = notify
        self._regular_entries: deque[LogEntry] = deque()
        self._important_entries: deque[LogEntry] = deque()
        self._capacity = capacity
        self._dropped = 0
        self._closed = False
        self._lock = threading.Lock()

    def publish(self, entry: LogEntry) -> None:
        with self._lock:
            if self._closed:
                return
            total = len(self._regular_entries) + len(self._important_entries)
            if total >= self._capacity:
                # WARNING/ERROR 在高峰期优先保留。常规日志滚动淘汰自身；
                # 重要日志到达时优先淘汰一条常规日志。
                if self._regular_entries:
                    self._regular_entries.popleft()
                elif entry.levelno < logging.WARNING:
                    self._dropped += 1
                    return
                else:
                    self._important_entries.popleft()
                self._dropped += 1
            target = self._important_entries if entry.levelno >= logging.WARNING else self._regular_entries
            target.append(entry)
        self._notify()

    def drain(self, limit: int = 1000) -> tuple[list[LogEntry], int]:
        with self._lock:
            entries: list[LogEntry] = []
            while len(entries) < limit and (self._regular_entries or self._important_entries):
                if not self._important_entries:
                    entries.append(self._regular_entries.popleft())
                elif not self._regular_entries:
                    entries.append(self._important_entries.popleft())
                elif self._regular_entries[0].sequence < self._important_entries[0].sequence:
                    entries.append(self._regular_entries.popleft())
                else:
                    entries.append(self._important_entries.popleft())
            dropped = self._dropped
            self._dropped = 0
        return entries, dropped

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._regular_entries or self._important_entries) or self._dropped > 0

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._regular_entries.clear()
            self._important_entries.clear()
            self._dropped = 0


class LogBroker:
    """将一条日志广播给所有活跃 Flet 页面。"""

    def __init__(self):
        # 页面应在 on_close/on_disconnect 主动退订；WeakSet 同时保证异常销毁的
        # Page 不会被进程级 broker 永久保活。
        self._subscriptions: weakref.WeakSet[LogSubscription] = weakref.WeakSet()
        self._sequence = 0
        self._lock = threading.Lock()

    @property
    def latest_sequence(self) -> int:
        with self._lock:
            return self._sequence

    def subscribe(self, notify: Callable[[], None], capacity: int = 10_000) -> LogSubscription:
        subscription = LogSubscription(notify, capacity)
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: LogSubscription) -> None:
        with self._lock:
            self._subscriptions.discard(subscription)
        subscription.close()

    def publish_record(self, record: logging.LogRecord, message: str) -> None:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            subscriptions = tuple(self._subscriptions)
        entry = LogEntry(
            sequence=sequence,
            created=record.created,
            levelno=record.levelno,
            levelname=record.levelname,
            logger_name=record.name,
            message=message,
        )
        for subscription in subscriptions:
            subscription.publish(entry)

    def reset_for_testing(self) -> None:
        """关闭所有订阅；仅供测试隔离全局 broker 状态。"""

        with self._lock:
            subscriptions = tuple(self._subscriptions)
            self._subscriptions.clear()
        for subscription in subscriptions:
            subscription.close()


class GuiLogHandler(logging.Handler):
    """进程级 handler，不持有任何 Flet Page 或控件。"""

    def __init__(self, broker: LogBroker):
        super().__init__(level=logging.DEBUG)
        self._broker = broker
        self._miningprocessor_gui_handler = True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._broker.publish_record(record, self.format(record))
        except Exception:
            self.handleError(record)


_broker = LogBroker()
_handler = GuiLogHandler(_broker)
_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
_handler.addFilter(_GuiNoiseFilter())
_install_lock = threading.Lock()


def get_log_broker() -> LogBroker:
    return _broker


def install_gui_log_handler() -> GuiLogHandler:
    """幂等安装 GUI handler。

    root 使用 DEBUG 以允许 GUI 的 DEBUG 筛选；控制台 handler 仍保留自己的
    INFO 阈值。该配置只在应用启动层执行，不由页面实例反复修改。
    """

    root = logging.getLogger()
    with _install_lock:
        # importlib/开发热重载会创建新的模块级 handler 对象。通过稳定标记
        # 清理旧实例，避免仅按对象身份判断造成重复采集。
        for existing in list(root.handlers):
            if existing is not _handler and getattr(existing, "_miningprocessor_gui_handler", False):
                root.removeHandler(existing)
        if _handler not in root.handlers:
            root.addHandler(_handler)
        if root.level == logging.NOTSET or root.level > logging.DEBUG:
            root.setLevel(logging.DEBUG)
    return _handler
