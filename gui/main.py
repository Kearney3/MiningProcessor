"""
GUI 主窗口 - Flet 实现
使用模块化结构：components.py（UI组件）+ logic.py（业务逻辑）
"""
import bisect
import flet as ft
import logging
import queue
import threading
from datetime import datetime
from pathlib import Path

from . import components as cmp
from . import logic as logic
from func.logger import setup_logging, QueueHandler, DEFAULT_FORMAT

MAX_LOG_RECORDS = 500
MIN_LOG_HEIGHT = 140
MAX_LOG_HEIGHT = 520
MIN_CONTENT_HEIGHT = 500

def main(page: ft.Page):
    setup_logging()
    page.title = "矿山数据处理工具"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.BLUE_GREY,
        visual_density=ft.VisualDensity.COMPACT,
    )
    page.window.width = 1020
    page.window.height = 1000
    page.window.min_width = 800

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
        tab_content_col.height = max(MIN_CONTENT_HEIGHT, int(page.window.height - TITLE_TAB_BAR_OVERHEAD - log_view_height))
        try:
            log_height_container.update()
            tab_content_col.update()
        except RuntimeError:
            pass

    def _on_vertical_drag_start(e):
        pass

    def _on_vertical_drag_update(e: ft.DragUpdateEvent):
        if shutdown_event.is_set():
            return
        _resize_log_view(e.primary_delta)

    TITLE_TAB_BAR_OVERHEAD = 30

    def _on_page_resize(e):
        nonlocal log_view_height
        available = page.window.height - TITLE_TAB_BAR_OVERHEAD
        log_view_height = _clamp_log_height(int(available))
        log_height_container.height = log_view_height
        tab_content_col.height = max(MIN_CONTENT_HEIGHT, int(available - log_view_height))
        try:
            log_height_container.update()
            tab_content_col.update()
        except RuntimeError:
            pass

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
    resize_handle.on_vertical_drag_start = _on_vertical_drag_start
    resize_handle.on_vertical_drag_update = _on_vertical_drag_update

    def _consume_logs():
        while True:
            log_item = log_queue.get()
            if log_item is None:
                break
            if shutdown_event.is_set():
                continue
            try:
                _append_log_record(log_item)
                # 批量排空队列，避免逐条触发 UI 更新
                try:
                    while True:
                        log_item = log_queue.get_nowait()
                        if log_item is None:
                            return
                        if not shutdown_event.is_set():
                            _append_log_record(log_item)
                except queue.Empty:
                    pass
                page.run_thread(_update_log_view)
            except Exception as ex:
                import sys
                print(f"[日志消费线程异常] {ex}", file=sys.stderr)

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
    page.window.on_resize = _on_page_resize

    def log(msg: str, level: int = logging.INFO):
        """统一通过全局 logger 输出，确保 GUI 与控制台实时同步"""
        logging.getLogger().log(level, msg)

    # ---- 创建各区域 UI ----
    ledger_section, ledger_refs = cmp.create_ledger_section(page, log)
    config_section, config_refs = cmp.create_config_section(page, log)
    modules_section, module_refs = cmp.create_modules_section(page)

    # ---- 绑定处理按钮 ----
    logic.wire_processing_buttons(module_refs, page, log)

    # ---- 标题栏 ----
    title_row = ft.Row(
        [
            ft.Icon(ft.Icons.DATASET, size=28, color=ft.Colors.BLUE_GREY_700),
            ft.Text("矿山数据处理工具", size=22, weight=ft.FontWeight.BOLD),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ---- Tab 切换（自定义实现） ----
    tab_contents = [
        ft.Column([modules_section], scroll=ft.ScrollMode.AUTO, expand=True, spacing=8),
        ft.Column([ledger_section], scroll=ft.ScrollMode.AUTO, expand=True, spacing=8),
        ft.Column([config_section], scroll=ft.ScrollMode.AUTO, expand=True, spacing=8),
    ]
    for c in tab_contents[1:]:
        c.visible = False

    tab_buttons = []
    tab_labels = [
        ("数据处理", ft.Icons.PLAY_ARROW),
        ("设备台账", ft.Icons.INVENTORY_2),
        ("装载量配置", ft.Icons.SETTINGS),
    ]

    def _select_tab(idx):
        def handler(e):
            for i, c in enumerate(tab_contents):
                c.visible = (i == idx)
            for i, btn in enumerate(tab_buttons):
                btn.style = ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY_CONTAINER if i == idx else ft.Colors.TRANSPARENT,
                    color=ft.Colors.ON_PRIMARY_CONTAINER if i == idx else ft.Colors.ON_SURFACE,
                )
                btn.update()
            for c in tab_contents:
                c.update()
        return handler

    for i, (label, icon) in enumerate(tab_labels):
        btn = ft.TextButton(
            label,
            icon=icon,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY_CONTAINER if i == 0 else ft.Colors.TRANSPARENT,
                color=ft.Colors.ON_PRIMARY_CONTAINER if i == 0 else ft.Colors.ON_SURFACE,
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
            ),
            on_click=_select_tab(i),
        )
        tab_buttons.append(btn)

    tab_bar = ft.Container(
        content=ft.Row(tab_buttons, spacing=4),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
    )

    # ---- 组装页面 ----
    tab_content_col = ft.Column(tab_contents, height=400, spacing=0)
    page.add(
        ft.Column(
            [
                ft.Container(content=title_row, padding=ft.padding.only(bottom=4)),
                tab_bar,
                tab_content_col,
                ft.Container(content=log_view),
            ],
            expand=True,
            spacing=0,
        )
    )

    # ---- 初始化日志区域高度 ----
    _on_page_resize(None)

    # ---- 初始化（放在 page.add 之后） ----
    logic.init(config_refs)
    log("已就绪")

