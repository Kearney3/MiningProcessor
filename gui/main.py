"""
GUI 主窗口 - Flet 实现
使用模块化结构：components.py（UI组件）+ logic.py（业务逻辑）
"""
import flet as ft
import logging
import os
import queue
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gui.components as cmp
import gui.logic as logic
from func.logger import setup_logging, QueueHandler, DEFAULT_FORMAT


def main(page: ft.Page):
    setup_logging()
    page.title = "矿山数据处理工具"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1020
    page.window_height = 850

    # ---- 滚动容器 ----
    scroll_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    # ---- 日志视图 ----
    log_view = cmp.create_log_view()
    log_list = log_view.content

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

    log_lines: list[str] = []
    shutdown_event = threading.Event()

    def _update_log_view(log_item: dict[str, object]):
        if shutdown_event.is_set():
            return
        msg = str(log_item["message"])
        levelno = int(log_item["levelno"])
        if levelno >= logging.ERROR:
            color = ft.Colors.RED
        elif levelno >= logging.WARNING:
            color = ft.Colors.ORANGE
        else:
            color = None
        log_lines.append(msg)
        if len(log_lines) > 500:
            log_lines.pop(0)
            if log_list.controls:
                log_list.controls.pop(0)
        log_list.controls.append(ft.Text(msg, size=13, selectable=True, color=color))
        try:
            log_view.update()
        except RuntimeError:
            pass

    def _consume_logs():
        while True:
            log_item = log_queue.get()
            if log_item is None:
                break
            if shutdown_event.is_set():
                continue
            try:
                page.run_thread(_update_log_view, log_item)
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

    def log(msg: str):
        """统一通过全局 logger 输出，确保 GUI 与控制台实时同步"""
        logging.getLogger().info(msg)

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
