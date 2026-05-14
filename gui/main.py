"""
GUI 主窗口 - Flet 实现
深色模式 + 侧边栏导航布局
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

try:
    from . import theme
except ImportError:
    import gui.theme as theme

from func.logger import setup_logging, QueueHandler, DEFAULT_FORMAT

MAX_LOG_RECORDS = 5000
MIN_LOG_HEIGHT = 140
MAX_LOG_HEIGHT = 520
MIN_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
INITIAL_WINDOW_WIDTH = 1000
INITIAL_WINDOW_HEIGHT = 900

def main(page: ft.Page):
    setup_logging()
    page.title = "矿山数据处理工具"
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    page.assets_dir = str(assets_dir)
    page.fonts={
        "MiSans": "fonts/MiSansVF.ttf",
    }
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.CYAN,
        visual_density=ft.VisualDensity.COMPACT,
    )
    page.window.width = INITIAL_WINDOW_WIDTH
    page.window.height = INITIAL_WINDOW_HEIGHT
    page.window.min_width = MIN_WINDOW_WIDTH
    page.window.min_height = MIN_WINDOW_HEIGHT

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

    for h in list(root_logger.handlers):
        if isinstance(h, QueueHandler):
            root_logger.removeHandler(h)
    root_logger.addHandler(queue_handler)

    log_records: list[dict[str, object]] = []
    log_records_lock = threading.Lock()
    log_view_height = int(log_height_container.height or 400)
    shutdown_event = threading.Event()

    _pending_records: list[dict[str, object]] = []
    _pending_lock = threading.Lock()
    _flush_timer: threading.Timer | None = None
    FLUSH_INTERVAL = 0.15  # 150ms 合并窗口

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

    def _flush_pending_to_ui():
        """将待显示记录追加到 ListView，由定时器触发"""
        with _pending_lock:
            batch = _pending_records[:]
            _pending_records.clear()
        if not batch or shutdown_event.is_set():
            return
        selected_level = _get_selected_level()
        for record in batch:
            if selected_level != "ALL" and record.get("levelname") != selected_level:
                continue
            log_list.controls.append(
                ft.Text(
                    str(record["message"]),
                    size=13,
                    selectable=True,
                    color=_level_color(int(record["levelno"])),
                )
            )
        if len(log_list.controls) > MAX_LOG_RECORDS:
            log_list.controls = log_list.controls[-MAX_LOG_RECORDS:]
        try:
            log_list.update()
        except (RuntimeError, AttributeError):
            pass

    def _schedule_flush():
        """安排一次 UI 刷新（150ms 内合并多批）"""
        nonlocal _flush_timer
        with _pending_lock:
            if _flush_timer is None:
                _flush_timer = threading.Timer(FLUSH_INTERVAL, _run_flush_on_page)
                _flush_timer.daemon = True
                _flush_timer.start()

    def _run_flush_on_page():
        """在 Flet 主线程执行刷新"""
        nonlocal _flush_timer
        with _pending_lock:
            _flush_timer = None
        try:
            page.run_thread(_flush_pending_to_ui)
        except Exception:
            pass

    def _update_log_view():
        """消费线程调用：安排刷新"""
        if shutdown_event.is_set():
            return
        _schedule_flush()

    def _append_log_record(log_item: dict[str, object]):
        record = {
            "timestamp": str(log_item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "created": float(log_item.get("created", 0)),
            "seq": int(log_item.get("seq", 0)),
            "levelno": int(log_item["levelno"]),
            "levelname": str(log_item["levelname"]),
            "message": str(log_item["message"]),
        }
        with log_records_lock:
            keys = [r["seq"] for r in log_records]
            idx = bisect.bisect_right(keys, record["seq"])
            log_records.insert(idx, record)
            if len(log_records) > MAX_LOG_RECORDS:
                del log_records[:-MAX_LOG_RECORDS]
        with _pending_lock:
            _pending_records.append(record)

    def _apply_filters(_e=None):
        """过滤器变更时全量重建 ListView"""
        with log_records_lock:
            records = list(log_records)
        selected_level = _get_selected_level()
        log_list.controls = [
            ft.Text(
                str(r["message"]),
                size=13,
                selectable=True,
                color=_level_color(int(r["levelno"])),
            )
            for r in records
            if selected_level == "ALL" or r.get("levelname") == selected_level
        ]
        try:
            log_list.update()
        except (RuntimeError, AttributeError):
            pass

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

    def _on_vertical_drag_start(e):
        pass

    def _on_vertical_drag_update(e: ft.DragUpdateEvent):
        if shutdown_event.is_set():
            return
        _resize_log_view(e.primary_delta)

    def _on_page_resize(e):
        nonlocal log_view_height
        log_view_height = _clamp_log_height(log_view_height)
        log_height_container.height = log_view_height
        try:
            log_height_container.update()
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
            try:
                log_item = log_queue.get()
            except Exception:
                continue
            if log_item is None:
                break
            if shutdown_event.is_set():
                continue
            try:
                _append_log_record(log_item)
                for _ in range(100):
                    try:
                        log_item = log_queue.get_nowait()
                    except queue.Empty:
                        break
                    if log_item is None:
                        return
                    if not shutdown_event.is_set():
                        _append_log_record(log_item)
                _update_log_view()
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
        nonlocal _flush_timer
        with _pending_lock:
            if _flush_timer is not None:
                _flush_timer.cancel()
                _flush_timer = None
        try:
            while True:
                log_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            log_queue.put_nowait(None)
        except queue.Full:
            pass

    page.on_disconnect = _shutdown_log_consumer
    page.on_close = _shutdown_log_consumer
    page.window.on_resize = _on_page_resize

    def log(msg: str, level: int = logging.INFO):
        logging.getLogger().log(level, msg)

    # ---- 创建各区域 UI ----
    ledger_section, ledger_refs = cmp.create_ledger_section(page, log)
    config_section, config_refs = cmp.create_config_section(page, log)
    modules_section, module_refs = cmp.create_modules_section(page)

    # ---- 绑定处理按钮 ----
    logic.wire_processing_buttons(module_refs, page, log)

    # ---- 侧边栏导航 ----
    nav_items_data = [
        ("数据处理", ft.Icons.PLAY_ARROW, "modules"),
        ("设备台账", ft.Icons.INVENTORY_2, "ledger"),
        ("装载量配置", ft.Icons.TUNE, "config"),
    ]

    # Content pages
    pages = {
        "modules": ft.Column([modules_section], expand=True, spacing=8),
        "ledger": ft.Column([ledger_section], expand=True, spacing=8),
        "config": ft.Column([config_section], expand=True, spacing=8),
    }

    current_nav = {"key": "modules"}

    def _select_page(key: str):
        def handler(e):
            current_nav["key"] = key
            content_col.controls = [pages[key]]
            content_col.update()
            _update_sidebar()
        return handler

    # Build sidebar nav items
    sidebar_nav_items = []
    for label, icon, key in nav_items_data:
        item = theme.sidebar_item(label, icon, selected=(key == "modules"))
        item.on_click = _select_page(key)
        sidebar_nav_items.append(item)

    def _update_sidebar():
        for (_, _, key), item in zip(nav_items_data, sidebar_nav_items):
            is_selected = (key == current_nav["key"])
            row = item.content
            icon_ctrl = row.controls[0]
            text_ctrl = row.controls[1]
            item.bgcolor = theme.SIDEBAR_SELECTED if is_selected else "transparent"
            icon_ctrl.color = theme.PRIMARY if is_selected else theme.TEXT_SECONDARY
            text_ctrl.color = theme.PRIMARY if is_selected else theme.TEXT_SECONDARY
            try:
                item.update()
            except (RuntimeError, AttributeError):
                pass

    sidebar = ft.Container(
        content=ft.Column(
            sidebar_nav_items,
            spacing=2,
        ),
        width=theme.SIDEBAR_WIDTH,
        bgcolor=theme.SIDEBAR_BG,
        padding=ft.padding.symmetric(horizontal=8, vertical=12),
    )

    # ---- Header ----
    header = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.DATASET, size=24, color=theme.PRIMARY),
                ft.Text("矿山数据处理工具", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
            ],
            spacing=theme.SPACING_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE,
        padding=ft.padding.symmetric(horizontal=theme.SPACING_LG, vertical=10),
        border=ft.border.only(bottom=ft.BorderSide(1, theme.BORDER)),
    )

    # ---- Content area ----
    content_col = ft.Column(
        [pages["modules"]],
        spacing=0,
        expand=True,
    )

    # Sidebar + content wrapped in a single card container
    unified_body = ft.Container(
        content=ft.Row(
            [sidebar, content_col],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        expand=True,
        bgcolor=theme.SURFACE,
        border=ft.border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    # ---- 组装页面 ----
    page.add(
        ft.Column(
            [
                header,
                unified_body,
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
