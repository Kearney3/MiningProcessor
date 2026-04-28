"""
GUI 主窗口 - Flet 实现
使用模块化结构：components.py（UI组件）+ logic.py（业务逻辑）
"""
import bisect
import flet as ft
import logging
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gui.components as cmp
import gui.logic as logic
from func.logger import setup_logging, QueueHandler, DEFAULT_FORMAT

MAX_LOG_RECORDS = 500
MIN_LOG_HEIGHT = 140
MAX_LOG_HEIGHT = 520


def main(page: ft.Page):
    setup_logging()
    page.title = "矿山数据处理工具"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1020
    page.window_height = 850

    # ---- 滚动容器 ----
    scroll_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    # ---- 日志视图 ----
    log_view, log_refs = cmp.create_log_view()
    log_list = log_refs["log_list"]
    log_height_container = log_refs["list_container"]
    level_filter = log_refs["level_filter"]
    export_button = log_refs["export_button"]
    resize_handle = log_refs["resize_handle"]

    # ---- 全局日志队列与 Handler ----
    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger = logging.getLogger()

    # 避免重复添加 QueueHandler
    for h in list(root_logger.handlers):
        if isinstance(h, QueueHandler):
            root_logger.removeHandler(h)
    root_logger.addHandler(queue_handler)

    log_records: list[dict[str, object]] = []
    log_records_lock = threading.Lock()
    log_view_height = int(log_height_container.height or 200)
    shutdown_event = threading.Event()

    def _level_color(levelno: int):
        if levelno >= logging.ERROR:
            return ft.Colors.RED
        if levelno >= logging.WARNING:
            return ft.Colors.ORANGE
        return None

    def _get_selected_level() -> str:
        raw_value = getattr(level_filter, "value", "ALL")
        if raw_value is None:
            return "ALL"
        return str(raw_value).strip() or "ALL"

    def _get_filtered_log_records() -> list[dict[str, object]]:
        selected_level = _get_selected_level()
        with log_records_lock:
            if selected_level == "ALL":
                return list(log_records)
            filtered = []
            for record in log_records:
                record_level = str(record.get("levelname", ""))
                if record_level != selected_level:
                    continue
                filtered.append(record)
            return filtered

    def _render_log_records():
        if shutdown_event.is_set():
            return
        visible_records = _get_filtered_log_records()
        log_list.controls = [
            ft.Text(
                str(record["message"]),
                size=13,
                selectable=True,
                color=_level_color(int(record["levelno"])),
            )
            for record in visible_records
        ]
        try:
            log_list.update()
        except (RuntimeError, AttributeError):
            pass
        try:
            log_view.update()
        except RuntimeError:
            pass

    def _append_log_record(log_item: dict[str, object]):
        record = {
            "timestamp": str(log_item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "created": float(log_item.get("created", 0)),
            "levelno": int(log_item["levelno"]),
            "levelname": str(log_item["levelname"]),
            "message": str(log_item["message"]),
        }
        with log_records_lock:
            # 使用 bisect 保持有序，避免整表排序
            keys = [r["created"] for r in log_records]
            idx = bisect.bisect_right(keys, record["created"])
            log_records.insert(idx, record)
            if len(log_records) > MAX_LOG_RECORDS:
                del log_records[:-MAX_LOG_RECORDS]

    def _update_log_view():
        if shutdown_event.is_set():
            return
        _render_log_records()

    def _apply_filters(_e=None):
        _render_log_records()

    def _clamp_log_height(next_height: int) -> int:
        return max(MIN_LOG_HEIGHT, min(MAX_LOG_HEIGHT, next_height))

    def _resize_log_view(delta_y: float):
        nonlocal log_view_height
        log_view_height = _clamp_log_height(log_view_height - int(delta_y))
        log_height_container.height = log_view_height
        try:
            log_height_container.update()
        except RuntimeError:
            pass

    def _on_vertical_drag_update(e: ft.DragUpdateEvent):
        if shutdown_event.is_set():
            return
        delta = e.primary_delta
        if delta is None:
            local_delta = getattr(e, "local_delta", None)
            delta = getattr(local_delta, "y", 0) if local_delta is not None else 0
        _resize_log_view(delta)

    def _build_export_text() -> str:
        return "\n".join(str(record["message"]) for record in _get_filtered_log_records())

    def _export_logs_to_path(path):
        if not path:
            return
        export_path = Path(path)
        export_path.write_text(_build_export_text(), encoding="utf-8")
        log(f"日志已导出: {export_path}")

    async def _export_logs(_e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title="导出日志",
            file_name=f"logs-{datetime.now().strftime('%Y-%m-%d')}.txt",
            allowed_extensions=["txt", "log"],
        )
        _export_logs_to_path(path)

    level_filter.on_select = _apply_filters
    export_button.on_click = _export_logs
    resize_handle.on_vertical_drag_update = _on_vertical_drag_update

    def _consume_logs():
        while True:
            log_item = log_queue.get()
            if log_item is None:
                break
            if shutdown_event.is_set():
                continue
            _append_log_record(log_item)
            try:
                page.run_thread(_update_log_view)
            except RuntimeError:
                break

    consumer_thread = threading.Thread(target=_consume_logs, daemon=True)
    consumer_thread.start()

    def _shutdown_log_consumer(_e=None):
        if shutdown_event.is_set():
            return
        shutdown_event.set()
        root_logger.removeHandler(queue_handler)
        try:
            log_queue.put_nowait(None)
        except queue.Full:
            pass

    page.on_disconnect = _shutdown_log_consumer
    page.on_close = _shutdown_log_consumer

    def log(msg: str, level: int = logging.INFO):
        """统一通过全局 logger 输出，确保 GUI 与控制台实时同步"""
        logging.getLogger().log(level, msg)

    # ---- 创建各区域 UI ----
    ledger_section, ledger_refs = cmp.create_ledger_section(page, log)
    config_section, config_refs = cmp.create_config_section(page, log)
    modules_section, module_refs = cmp.create_modules_section(page)

    # ---- 绑定处理按钮 ----
    logic.wire_processing_buttons(module_refs, page, log)

    # ---- 组装页面 ----
    scroll_col.controls.append(ft.Text("矿山数据处理工具", size=24, weight=ft.FontWeight.BOLD))
    scroll_col.controls.append(ledger_section)
    scroll_col.controls.append(config_section)
    scroll_col.controls.append(modules_section)
    scroll_col.controls.append(log_view)
    page.add(scroll_col)

    # ---- 初始化（放在 page.add 之后） ----
    logic.init(config_refs)
    log("已就绪")


if __name__ == "__main__":
    ft.run(main)
