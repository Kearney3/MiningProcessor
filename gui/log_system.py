"""
日志系统模块
封装日志队列、消费者线程、UI 刷新逻辑，从 main.py 中独立出来 (M5)。
"""
import bisect
import inspect
import flet as ft
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

from .components.common import _last_directory, _update_last_directory

from func.logger import QueueHandler, DEFAULT_FORMAT

MAX_LOG_RECORDS = 5000
MIN_LOG_HEIGHT = 140
MAX_LOG_HEIGHT = 520

# 第三方库 DEBUG 日志噪音，通过 root logger filter 从源头拦截
_NOISY_LOGGERS = frozenset({
    "flet", "flet_controls", "flet_object_patch",
    "flet_transport", "flet_components",
    "watchfiles", "uvicorn",
})


def _suppress_noisy_loggers():
    """将第三方库的 logger 级别设为 INFO，从源头阻止 DEBUG 记录产生。"""
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)


class _SuppressNoisyFilter(logging.Filter):
    """挂在 root logger 上，拦截第三方库的 DEBUG 日志，项目自身日志正常放行。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.INFO:
            name = record.name or ""
            if name in _NOISY_LOGGERS:
                return False
            for prefix in _NOISY_LOGGERS:
                if name.startswith(prefix + "."):
                    return False
        return True


class LogSystem:
    """封装日志队列、消费者线程、UI 刷新逻辑。"""

    def __init__(self, page: ft.Page, log_refs: dict):
        self._page = page
        self._log_list = log_refs["log_list"]
        self._log_height_container = log_refs["list_container"]
        self._level_filter = log_refs["level_filter"]
        self._export_button = log_refs["export_button"]
        self._resize_handle = log_refs["resize_handle"]
        self._clear_button = log_refs["clear_button"]
        self._scroll_bottom_button = log_refs["scroll_bottom_button"]

        # 日志队列与 Handler
        self._log_queue: queue.Queue = queue.Queue()
        self._queue_handler = QueueHandler(self._log_queue)
        self._queue_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
        self._root_logger = logging.getLogger()

        for h in list(self._root_logger.handlers):
            if isinstance(h, QueueHandler):
                self._root_logger.removeHandler(h)
        self._root_logger.addHandler(self._queue_handler)
        # root logger 始终 DEBUG，确保所有级别日志都能被采集到；
        # 前端/控制台的级别筛选只控制显示，不控制采集。
        self._root_logger.setLevel(logging.DEBUG)
        # 全局 filter 挂 root logger，拦截第三方库噪音（任何 handler 都受控）
        _suppress_noisy_loggers()
        if not any(isinstance(f, _SuppressNoisyFilter) for f in self._root_logger.filters):
            self._root_logger.addFilter(_SuppressNoisyFilter())

        # 状态
        self._log_records: list[dict[str, object]] = []
        self._log_records_lock = threading.Lock()
        self._log_view_height = int(self._log_height_container.height or 400)
        self._shutdown_event = threading.Event()
        self._pending_records: list[dict[str, object]] = []
        self._pending_lock = threading.Lock()
        self._flush_timer: threading.Timer | None = None
        self._last_flush_time: float = time.monotonic()
        self.FLUSH_INTERVAL = 0.15
        self.FALLBACK_FLUSH_TIMEOUT = 1.0

        self._consumer_thread: threading.Thread | None = None
        self._log_export_picker = ft.FilePicker()
        page.services.append(self._log_export_picker)

    # ── 公开接口 ──

    def start(self):
        """启动消费者线程并绑定 UI 控件。"""
        self._bind_controls()
        self._consumer_thread = threading.Thread(target=self._consume_logs, daemon=True)
        self._consumer_thread.start()

    def shutdown(self):
        """优雅关闭消费者线程。"""
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()
        self._root_logger.removeHandler(self._queue_handler)
        with self._pending_lock:
            if self._flush_timer is not None:
                self._flush_timer.cancel()
                self._flush_timer = None
        try:
            while True:
                self._log_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._log_queue.put_nowait(None)
        except queue.Full:
            pass

    # ── 内部方法 ──

    def _bind_controls(self):
        self._clear_button.on_click = self._clear_logs
        self._scroll_bottom_button.on_click = self._scroll_to_bottom
        self._level_filter.on_select = self._apply_filters
        self._export_button.on_click = self._export_logs
        self._resize_handle.on_vertical_drag_start = lambda e: None
        self._resize_handle.on_vertical_drag_update = self._on_vertical_drag_update
        self._page.window.on_resize = self._on_page_resize
        self._page.on_disconnect = lambda e: self.shutdown()
        self._page.on_close = lambda e: self.shutdown()

    def _level_color(self, levelno: int):
        # 保留接口以兼容导出等功能，但 TextField 不支持逐行着色
        if levelno >= logging.ERROR:
            return ft.Colors.RED
        if levelno >= logging.WARNING:
            return ft.Colors.ORANGE
        return None

    _LEVEL_THRESHOLD = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def _get_selected_level(self) -> str:
        raw_value = getattr(self._level_filter, "value", "INFO")
        if raw_value is None:
            return "INFO"
        return str(raw_value).strip() or "INFO"

    def _pass_level_filter(self, record: dict[str, object]) -> bool:
        """判断记录是否通过当前级别筛选（选中级别及以上）。"""
        selected = self._get_selected_level()
        threshold = self._LEVEL_THRESHOLD.get(selected, logging.INFO)
        return int(record.get("levelno", 0)) >= threshold

    def _get_filtered_log_records(self) -> list[dict[str, object]]:
        with self._log_records_lock:
            return [r for r in self._log_records if self._pass_level_filter(r)]

    async def _flush_pending_to_ui(self):
        """将待显示记录追加到 ListView。

        必须在事件循环线程上运行（通过 run_task 调度），
        避免与 Flet 的 ObjectPatch.from_diff 并发修改 controls。
        run_thread 会在线程池中执行，与事件循环线程并发导致 IndexError。
        """
        with self._pending_lock:
            batch = self._pending_records[:]
            self._pending_records.clear()
        if not batch or self._shutdown_event.is_set():
            return
        batch.sort(key=lambda r: r.get("seq", 0))
        new_controls = list(self._log_list.controls)
        for record in batch:
            if not self._pass_level_filter(record):
                continue
            new_controls.append(
                ft.Text(
                    str(record["message"]),
                    size=13,
                    selectable=True,
                )
            )
        if len(new_controls) > MAX_LOG_RECORDS:
            new_controls = new_controls[-MAX_LOG_RECORDS:]
        self._log_list.controls = new_controls
        try:
            self._log_list.update()
        except Exception as ex:
            logging.getLogger(__name__).debug("flush_update 异常: %s", ex)
        try:
            scroll_result = self._log_list.scroll_to(offset=-1)
            if inspect.isawaitable(scroll_result):
                await scroll_result
        except (RuntimeError, AttributeError):
            pass
        self._last_flush_time = time.monotonic()

    def _schedule_flush(self):
        with self._pending_lock:
            if self._flush_timer is None:
                self._flush_timer = threading.Timer(self.FLUSH_INTERVAL, self._run_flush_on_page)
                self._flush_timer.daemon = True
                self._flush_timer.start()

    def _run_flush_on_page(self):
        with self._pending_lock:
            self._flush_timer = None
        try:
            self._page.run_task(self._flush_pending_to_ui)
        except Exception:
            logging.getLogger(__name__).debug("page.run_task 失败（页面可能已关闭）")

    def _append_log_record(self, log_item: dict[str, object]):
        raw_msg = str(log_item["message"])
        # ERROR 级别且含 traceback 时，只保留第一行（用户友好的异常消息）
        # 后端日志已通过 logger.exception 记录完整 traceback，此处仅影响 GUI 显示
        levelno = int(log_item["levelno"])
        if levelno >= logging.ERROR and "\nTraceback " in raw_msg:
            raw_msg = raw_msg.split("\n", 1)[0].rstrip()
        record = {
            "timestamp": str(log_item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "created": float(log_item.get("created", 0)),
            "seq": int(log_item.get("seq", 0)),
            "levelno": levelno,
            "levelname": str(log_item["levelname"]),
            "message": raw_msg,
        }
        with self._log_records_lock:
            if not self._log_records or record["seq"] >= self._log_records[-1]["seq"]:
                self._log_records.append(record)
            else:
                keys = [r["seq"] for r in self._log_records]
                idx = bisect.bisect_right(keys, record["seq"])
                self._log_records.insert(idx, record)
            if len(self._log_records) > MAX_LOG_RECORDS:
                del self._log_records[:-MAX_LOG_RECORDS]
        with self._pending_lock:
            self._pending_records.append(record)

    async def _apply_filters(self, _e=None):
        try:
            with self._log_records_lock:
                records = list(self._log_records)
            filtered = [r for r in records if self._pass_level_filter(r)]
            self._log_list.controls = [
                ft.Text(str(r["message"]), size=13, selectable=True)
                for r in filtered
            ]
            self._log_list.update()
        except (RuntimeError, AttributeError, Exception) as ex:
            logging.getLogger(__name__).debug("apply_filters 异常: %s", ex)
        try:
            scroll_result = self._log_list.scroll_to(offset=-1)
            if inspect.isawaitable(scroll_result):
                await scroll_result
        except (RuntimeError, AttributeError):
            pass
        self._last_flush_time = time.monotonic()

    def _clamp_log_height(self, next_height: int) -> int:
        return max(MIN_LOG_HEIGHT, min(MAX_LOG_HEIGHT, next_height))

    def _on_vertical_drag_update(self, e: ft.DragUpdateEvent):
        if self._shutdown_event.is_set():
            return
        self._log_view_height = self._clamp_log_height(self._log_view_height - int(e.primary_delta))
        self._log_height_container.height = self._log_view_height
        try:
            self._log_height_container.update()
        except RuntimeError:
            pass

    def _on_page_resize(self, e):
        self._log_view_height = self._clamp_log_height(self._log_view_height)
        self._log_height_container.height = self._log_view_height
        try:
            self._log_height_container.update()
        except RuntimeError:
            pass

    async def _export_logs(self, _e: ft.ControlEvent):
        path = await self._log_export_picker.save_file(
            dialog_title="导出日志",
            file_name=f"logs-{datetime.now().strftime('%Y-%m-%d')}.txt",
            allowed_extensions=["txt", "log"],
            initial_directory=_last_directory[0] or None,
        )
        if path:
            _update_last_directory(path)
            export_path = Path(path)
            export_path.write_text(
                "\n".join(str(r["message"]) for r in self._get_filtered_log_records()),
                encoding="utf-8",
            )
            logging.getLogger(__name__).info(f"日志已导出: {export_path}")

    async def _clear_logs(self, e=None):
        try:
            self._log_list.controls = []
            with self._log_records_lock:
                self._log_records.clear()
            self._log_list.update()
        except (RuntimeError, AttributeError, Exception) as ex:
            logging.getLogger(__name__).debug("clear_logs 异常: %s", ex)

    async def _scroll_to_bottom(self, e=None):
        try:
            scroll_result = self._log_list.scroll_to(offset=-1)
            if inspect.isawaitable(scroll_result):
                await scroll_result
        except (RuntimeError, AttributeError):
            pass

    def _consume_logs(self):
        while True:
            try:
                log_item = self._log_queue.get(timeout=max(self.FLUSH_INTERVAL * 4, 0.5))
            except queue.Empty:
                with self._pending_lock:
                    pending_count = len(self._pending_records)
                if pending_count > 0:
                    elapsed = time.monotonic() - self._last_flush_time
                    if elapsed > self.FALLBACK_FLUSH_TIMEOUT:
                        try:
                            self._page.run_task(self._flush_pending_to_ui)
                        except Exception:
                            pass
                continue
            except Exception:
                continue
            if log_item is None:
                break
            if self._shutdown_event.is_set():
                continue
            try:
                self._append_log_record(log_item)
                for _ in range(100):
                    try:
                        log_item = self._log_queue.get_nowait()
                    except queue.Empty:
                        break
                    if log_item is None:
                        return
                    if not self._shutdown_event.is_set():
                        self._append_log_record(log_item)
                if not self._shutdown_event.is_set():
                    self._schedule_flush()
                with self._pending_lock:
                    pending_count = len(self._pending_records)
                if pending_count > 0:
                    elapsed = time.monotonic() - self._last_flush_time
                    if elapsed > self.FALLBACK_FLUSH_TIMEOUT:
                        logging.getLogger(__name__).debug(
                            "fallback flush: %d pending records stuck for %.1fs", pending_count, elapsed
                        )
                        try:
                            self._page.run_task(self._flush_pending_to_ui)
                        except Exception:
                            pass
            except Exception as ex:
                import sys
                if hasattr(sys.stderr, 'reconfigure'):
                    try:
                        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
                    except Exception:
                        pass
                print(f"[日志消费线程异常] {ex}", file=sys.stderr)
