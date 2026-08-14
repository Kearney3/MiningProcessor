"""Flet 页面级日志控制器。

页面只订阅进程级 LogBroker。日志、筛选和清空请求会合并到同一个异步
flush 中，因此只有一个入口会修改 Flet 日志控件。
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
from pathlib import Path
import sys
import threading

import flet as ft

from . import theme
from .components.common import _last_directory, _update_last_directory
from .log_broker import LogEntry, LogSubscription, get_log_broker
from func.time_utils import local_datetime_from_timestamp, local_now
from gui.i18n import t


MAX_LOG_RECORDS = 5000
MAX_RENDERED_RECORDS = 1000
MIN_LOG_HEIGHT = 140
MAX_LOG_HEIGHT = 520
DEFAULT_LOG_HEIGHT_RATIO = 1 / 3
FLUSH_INTERVAL = 0.08
SCROLL_BOTTOM_THRESHOLD = 48


def _diagnose(message: str, ex: BaseException | None = None) -> None:
    """日志基础设施的故障直接写 stderr，避免重新进入 GUI 日志管道。"""

    suffix = f": {ex}" if ex is not None else ""
    try:
        print(t("logSystem:message", message=message, suffix=suffix), file=sys.__stderr__)
    except Exception:
        pass


class LogSystem:
    """管理一个 Flet 页面的日志状态和渲染。"""

    _LEVEL_THRESHOLD = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def __init__(self, page: ft.Page, log_refs: dict):
        self._page = page
        self._log_list = log_refs["log_list"]
        self._log_height_container = log_refs["list_container"]
        self._level_filter = log_refs["level_filter"]
        self._export_button = log_refs["export_button"]
        self._resize_handle = log_refs["resize_handle"]
        self._clear_button = log_refs["clear_button"]
        self._scroll_bottom_button = log_refs["scroll_bottom_button"]
        self._follow_status = log_refs["follow_status"]
        self._count_text = log_refs.get("count_text")

        self._broker = get_log_broker()
        self._subscription: LogSubscription | None = None
        self._log_records: list[LogEntry] = []
        self._selected_level = self._read_selected_level()
        self._clear_before_sequence = 0
        self._applied_clear_sequence = 0
        self._full_render_requested = False
        self._follow_tail = True
        self._visible_count = 0

        self._log_view_height = self._recommended_log_height(
            int(self._log_height_container.height or 400)
        )
        self._log_height_container.height = self._log_view_height
        self._log_height_user_set = False
        self._shutdown_event = threading.Event()
        self._schedule_lock = threading.Lock()
        self._flush_scheduled = False
        self._flush_future: concurrent.futures.Future | None = None

        self._log_export_picker = ft.FilePicker()
        page.services.append(self._log_export_picker)

    def start(self) -> None:
        """绑定控件并订阅日志。重复调用不会创建重复订阅。"""

        if self._subscription is not None:
            return
        self._bind_controls()
        self._subscription = self._broker.subscribe(self._request_flush)

    def shutdown(self) -> None:
        """停止当前页面的日志投递，不影响其他页面。"""

        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()
        if self._subscription is not None:
            self._broker.unsubscribe(self._subscription)
            self._subscription = None
        with self._schedule_lock:
            future = self._flush_future
            self._flush_future = None
            self._flush_scheduled = False
        if future is not None and not future.done():
            future.cancel()

    def _bind_controls(self) -> None:
        self._clear_button.on_click = self._clear_logs
        self._scroll_bottom_button.on_click = self._scroll_to_bottom
        self._log_list.on_scroll = self._on_log_scroll
        self._level_filter.on_select = self._apply_filters
        self._export_button.on_click = self._export_logs
        self._resize_handle.on_vertical_drag_start = lambda e: None
        self._resize_handle.on_vertical_drag_update = self._on_vertical_drag_update
        self._page.window.on_resize = self._on_page_resize

    def _read_selected_level(self) -> str:
        value = str(getattr(self._level_filter, "value", "INFO") or "INFO").strip()
        return value if value in self._LEVEL_THRESHOLD else "INFO"

    def _passes_filter(self, entry: LogEntry) -> bool:
        return entry.levelno >= self._LEVEL_THRESHOLD[self._selected_level]

    @staticmethod
    def _display_message(entry: LogEntry) -> str:
        message = entry.message
        if entry.levelno >= logging.ERROR and "\nTraceback " in message:
            return message.split("\n", 1)[0].rstrip()
        return message

    def _request_flush(self) -> None:
        """线程安全地合并 flush 请求。"""

        if self._shutdown_event.is_set():
            return
        with self._schedule_lock:
            if self._flush_scheduled:
                return
            self._flush_scheduled = True
        try:
            future = self._page.run_task(self._flush_to_ui)
        except Exception as ex:
            with self._schedule_lock:
                self._flush_scheduled = False
                self._flush_future = None
            _diagnose(t("logSystem:unableToSchedulePageLogRefresh"), ex)
            return
        with self._schedule_lock:
            if self._flush_scheduled:
                self._flush_future = future

    async def _flush_to_ui(self) -> None:
        """唯一允许修改日志 ListView 的方法。"""

        try:
            await asyncio.sleep(FLUSH_INTERVAL)
            while not self._shutdown_event.is_set():
                subscription = self._subscription
                if subscription is None:
                    break
                entries, dropped = subscription.drain()
                render_all = self._full_render_requested
                self._full_render_requested = False

                if self._clear_before_sequence > self._applied_clear_sequence:
                    cutoff = self._clear_before_sequence
                    self._log_records = [entry for entry in self._log_records if entry.sequence > cutoff]
                    self._applied_clear_sequence = cutoff
                    render_all = True

                visible_new: list[LogEntry] = []
                for entry in entries:
                    if entry.sequence <= self._clear_before_sequence:
                        continue
                    self._log_records.append(entry)
                    if self._passes_filter(entry):
                        visible_new.append(entry)
                if len(self._log_records) > MAX_LOG_RECORDS:
                    self._log_records = self._log_records[-MAX_LOG_RECORDS:]
                    render_all = True

                if dropped:
                    synthetic = LogEntry(
                        sequence=self._broker.latest_sequence,
                        created=0,
                        levelno=logging.WARNING,
                        levelname="WARNING",
                        logger_name=__name__,
                        message=t("logSystem:logThroughputIsHighOmittedItemsearlierRecords", dropped=dropped),
                    )
                    self._log_records.append(synthetic)
                    if self._passes_filter(synthetic):
                        visible_new.append(synthetic)

                changed = render_all or bool(visible_new)
                if render_all:
                    visible = [entry for entry in self._log_records if self._passes_filter(entry)]
                    visible = visible[-MAX_RENDERED_RECORDS:]
                    self._log_list.controls = [self._make_text(entry) for entry in visible]
                    self._visible_count = sum(
                        1 for entry in self._log_records
                        if self._passes_filter(entry)
                    )
                elif visible_new:
                    controls = [*self._log_list.controls, *(self._make_text(entry) for entry in visible_new)]
                    self._log_list.controls = controls[-MAX_RENDERED_RECORDS:]
                    self._visible_count += len(visible_new)

                if changed:
                    if self._count_text is not None:
                        self._count_text.value = t("logSystem:items", count=self._visible_count)
                        self._count_text.update()
                    self._log_list.update()
                    if self._follow_tail:
                        scroll_result = self._log_list.scroll_to(offset=-1)
                        if inspect.isawaitable(scroll_result):
                            await scroll_result

                with self._schedule_lock:
                    pending_command = self._full_render_requested or (
                        self._clear_before_sequence > self._applied_clear_sequence
                    )
                    if subscription.has_pending() or pending_command:
                        continue
                    self._flush_scheduled = False
                    self._flush_future = None
                    break
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            _diagnose(t("logSystem:pageLogRefreshFailed"), ex)
        finally:
            should_reschedule = False
            with self._schedule_lock:
                if self._flush_scheduled:
                    self._flush_scheduled = False
                    self._flush_future = None
                    subscription = self._subscription
                    should_reschedule = (
                        not self._shutdown_event.is_set()
                        and subscription is not None
                        and (
                            subscription.has_pending()
                            or self._full_render_requested
                            or self._clear_before_sequence > self._applied_clear_sequence
                        )
                    )
            if should_reschedule:
                self._request_flush()

    def _make_text(self, entry: LogEntry) -> ft.Text:
        timestamp = (
            local_datetime_from_timestamp(entry.created).strftime("%H:%M:%S")
            if entry.created else "--:--:--"
        )
        level = "WARN" if entry.levelname == "WARNING" else entry.levelname
        message = self._display_message(entry)
        formatted_parts = message.split(" | ", 2)
        if len(formatted_parts) == 3 and formatted_parts[0].startswith("["):
            message = formatted_parts[2]
        return ft.Text(
            f"{timestamp}  {level:<5}  {message}",
            size=13,
            selectable=True,
            font_family="monospace",
        )

    async def _apply_filters(self, _e=None) -> None:
        self._selected_level = self._read_selected_level()
        self._full_render_requested = True
        self._request_flush()
        await asyncio.sleep(FLUSH_INTERVAL * 2)

    async def _clear_logs(self, _e=None) -> None:
        self._clear_before_sequence = self._broker.latest_sequence
        self._full_render_requested = True
        self._request_flush()
        await asyncio.sleep(FLUSH_INTERVAL * 2)

    async def _scroll_to_bottom(self, _e=None) -> None:
        self._set_follow_tail(True)
        try:
            result = self._log_list.scroll_to(offset=-1)
            if inspect.isawaitable(result):
                await result
        except (RuntimeError, AttributeError):
            pass

    def _on_log_scroll(self, event: ft.OnScrollEvent) -> None:
        """用户离开底部时暂停自动跟随；回到底部后自动恢复。"""

        pixels = float(getattr(event, "pixels", 0) or 0)
        max_extent = float(getattr(event, "max_scroll_extent", 0) or 0)
        self._set_follow_tail(max_extent - pixels <= SCROLL_BOTTOM_THRESHOLD)

    def _set_follow_tail(self, enabled: bool) -> None:
        if self._follow_tail == enabled:
            return
        self._follow_tail = enabled
        self._follow_status.visible = not enabled
        self._scroll_bottom_button.tooltip = (
            t("logSystem:scrollToBottom") if enabled else t("logSystem:scrollToBottomlog")
        )
        self._scroll_bottom_button.icon_color = (
            theme.TEXT_SECONDARY if enabled else theme.PRIMARY
        )
        try:
            self._follow_status.update()
            self._scroll_bottom_button.update()
        except (RuntimeError, AttributeError):
            pass

    async def _export_logs(self, _e: ft.ControlEvent) -> None:
        path = await self._log_export_picker.save_file(
            dialog_title=t("logSystem:exportLogs"),
            file_name=f"logs-{local_now().strftime('%Y-%m-%d')}.txt",
            allowed_extensions=["txt", "log"],
            initial_directory=_last_directory[0] or None,
        )
        if not path:
            return
        _update_last_directory(path)
        threshold = self._LEVEL_THRESHOLD[self._selected_level]
        snapshot = [entry for entry in self._log_records if entry.levelno >= threshold]
        try:
            Path(path).write_text(
                "\n".join(entry.message for entry in snapshot),
                encoding="utf-8",
            )
        except OSError as ex:
            logging.getLogger(__name__).error(t("logSystem:logExportFailedS"), ex)
            return
        logging.getLogger(__name__).info(t("logSystem:logExportedS"), path)

    def _clamp_log_height(self, next_height: int) -> int:
        return max(MIN_LOG_HEIGHT, min(MAX_LOG_HEIGHT, next_height))

    def _recommended_log_height(self, fallback: int) -> int:
        """按当前窗口高度计算默认日志高度，窗口尺寸不可用时保留组件值。"""

        window_height = getattr(getattr(self._page, "window", None), "height", None)
        page_height = getattr(self._page, "height", None)
        available_height = page_height or window_height
        if not isinstance(available_height, (int, float)) or available_height <= 0:
            return self._clamp_log_height(fallback)
        return self._clamp_log_height(round(available_height * DEFAULT_LOG_HEIGHT_RATIO))

    def _on_vertical_drag_update(self, e: ft.DragUpdateEvent) -> None:
        if self._shutdown_event.is_set():
            return
        self._log_height_user_set = True
        self._log_view_height = self._clamp_log_height(self._log_view_height - int(e.primary_delta))
        self._log_height_container.height = self._log_view_height
        try:
            self._log_height_container.update()
        except RuntimeError:
            pass

    def _on_page_resize(self, _e) -> None:
        if (self._log_height_container.data or {}).get("collapsed"):
            return
        if self._log_height_user_set:
            self._log_view_height = self._clamp_log_height(self._log_view_height)
        else:
            self._log_view_height = self._recommended_log_height(self._log_view_height)
        self._log_height_container.height = self._log_view_height
        try:
            self._log_height_container.update()
        except RuntimeError:
            pass
