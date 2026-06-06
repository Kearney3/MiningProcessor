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
import time
from datetime import datetime
from pathlib import Path

from . import components as cmp
from . import logic as logic
from .components.common import _last_directory, _update_last_directory

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
    _is_at_bottom = log_refs["_is_at_bottom"]

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
    _last_flush_time: float = time.monotonic()  # 上次成功 flush 的时间戳
    FLUSH_INTERVAL = 0.15  # 150ms 合并窗口
    FALLBACK_FLUSH_TIMEOUT = 1.0  # pending 超过此秒数未被 flush 时，从 consumer 线程直接 flush

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
        """将待显示记录追加到 ListView，由定时器触发或 fallback 直接调用"""
        nonlocal _last_flush_time
        with _pending_lock:
            batch = _pending_records[:]
            _pending_records.clear()
        if not batch or shutdown_event.is_set():
            return
        batch.sort(key=lambda r: r.get("seq", 0))
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
            if _is_at_bottom[0]:
                page.run_task(log_list.scroll_to, offset=-1)
        except (RuntimeError, AttributeError):
            pass
        _last_flush_time = time.monotonic()

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
            logging.getLogger(__name__).debug("page.run_thread 失败（页面可能已关闭）")
            # 异常时也更新时间戳，避免 fallback 立即触发
            # 下次 _schedule_flush 会重新创建 timer

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
            # 快路径：consumer 线程基本按 seq 递增处理，直接追加 O(1)
            if not log_records or record["seq"] >= log_records[-1]["seq"]:
                log_records.append(record)
            else:
                # 慢路径：乱序时用 bisect 插入
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
        # 先筛选出匹配的记录（轻量操作），再在锁外构建 Text 控件
        filtered = [
            r for r in records
            if selected_level == "ALL" or r.get("levelname") == selected_level
        ]
        log_list.controls = [
            ft.Text(
                str(r["message"]),
                size=13,
                selectable=True,
                color=_level_color(int(r["levelno"])),
            )
            for r in filtered
        ]
        try:
            log_list.update()
            if _is_at_bottom[0]:
                page.run_task(log_list.scroll_to, offset=-1)
        except (RuntimeError, AttributeError):
            pass
        _last_flush_time = time.monotonic()

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

    _log_export_picker = ft.FilePicker()
    page.services.append(_log_export_picker)

    def _build_export_text() -> str:
        return "\n".join(str(record["message"]) for record in _get_filtered_log_records())

    def _export_logs_to_path(path):
        if not path:
            return
        export_path = Path(path)
        export_path.write_text(_build_export_text(), encoding="utf-8")
        log(f"日志已导出: {export_path}")

    async def _export_logs(_e: ft.ControlEvent):
        path = await _log_export_picker.save_file(
            dialog_title="导出日志",
            file_name=f"logs-{datetime.now().strftime('%Y-%m-%d')}.txt",
            allowed_extensions=["txt", "log"],
            initial_directory=_last_directory[0] or None,
        )
        if path:
            _update_last_directory(path)
        _export_logs_to_path(path)

    clear_button = log_refs["clear_button"]
    scroll_bottom_button = log_refs["scroll_bottom_button"]

    def _clear_logs(e=None):
        log_list.controls.clear()
        with log_records_lock:
            log_records.clear()
        try:
            log_list.update()
        except (RuntimeError, AttributeError):
            pass

    def _scroll_to_bottom(e=None):
        try:
            page.run_task(log_list.scroll_to, offset=-1)
        except (RuntimeError, AttributeError):
            pass

    clear_button.on_click = _clear_logs
    scroll_bottom_button.on_click = _scroll_to_bottom
    level_filter.on_select = _apply_filters
    export_button.on_click = _export_logs
    resize_handle.on_vertical_drag_start = _on_vertical_drag_start
    resize_handle.on_vertical_drag_update = _on_vertical_drag_update

    def _consume_logs():
        while True:
            try:
                log_item = log_queue.get(timeout=max(FLUSH_INTERVAL * 4, 0.5))
            except queue.Empty:
                # 定期检查：pending 记录是否长时间未被 flush
                with _pending_lock:
                    pending_count = len(_pending_records)
                if pending_count > 0:
                    elapsed = time.monotonic() - _last_flush_time
                    if elapsed > FALLBACK_FLUSH_TIMEOUT:
                        _flush_pending_to_ui()
                continue
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
                # Fallback：如果 pending 记录长时间未被 page.run_thread flush，
                # 从 consumer 线程直接 flush（绕过 page.run_thread）。
                # 不检查 _flush_timer 状态，因为即使 timer 存在，
                # page.run_thread 也可能静默失败导致回调不执行。
                with _pending_lock:
                    pending_count = len(_pending_records)
                if pending_count > 0:
                    elapsed = time.monotonic() - _last_flush_time
                    if elapsed > FALLBACK_FLUSH_TIMEOUT:
                        logging.getLogger(__name__).debug(
                            "fallback flush: %d pending records stuck for %.1fs", pending_count, elapsed
                        )
                        _flush_pending_to_ui()
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
    oil_ledger_section, oil_ledger_refs = cmp.create_oil_ledger_section(page, log)
    config_section, config_refs = cmp.create_config_section(page, log)
    user_config_section, user_config_refs = cmp.create_user_config_section(page, log)
    modules_section, module_refs = cmp.create_modules_section(page)
    batch_section, batch_refs = cmp.create_batch_section(page)
    module_refs["batch"] = batch_refs
    ledger_match_section, ledger_match_refs = cmp.create_ledger_match_section(page, log, ledger_refs, oil_ledger_refs)
    sync_section, sync_refs = cmp.create_sync_section(page)

    # ---- 绑定处理按钮 ----
    logic.wire_processing_buttons(module_refs, page, log, ledger_refs, oil_ledger_refs)
    logic.wire_sync_button(sync_refs, page, log)

    # ---- 侧边栏导航（分组） ----
    nav_groups = [
        ("工作区", [
            ("数据处理", ft.Icons.PLAY_ARROW, "modules"),
            ("批量处理", ft.Icons.BOLT, "batch"),
            ("数据同步", ft.Icons.CLOUD_SYNC, "sync"),
            ("台账匹配", ft.Icons.MANAGE_SEARCH, "ledger_match"),
        ]),
        ("管理", [
            ("设备台账", ft.Icons.INVENTORY_2, "ledger"),
            ("油品台账", ft.Icons.OIL_BARREL, "oil_ledger"),
            ("装载量配置", ft.Icons.TUNE, "config"),
            ("用户配置", ft.Icons.SETTINGS, "user_config"),
        ]),
    ]
    nav_items_data = [item for _, items in nav_groups for item in items]

    # Content pages
    pages = {
        "modules": ft.Column([modules_section], expand=True, spacing=8),
        "batch": ft.Column([batch_section], expand=True, spacing=8),
        "sync": ft.Column([sync_section], expand=True, spacing=8),
        "ledger_match": ft.Column([ledger_match_section], expand=True, spacing=8),
        "ledger": ft.Column([ledger_section], expand=True, spacing=8),
        "oil_ledger": ft.Column([oil_ledger_section], expand=True, spacing=8),
        "config": ft.Column([config_section], expand=True, spacing=8),
        "user_config": ft.Column([user_config_section], expand=True, spacing=8),
    }

    current_nav = {"key": "modules"}

    def _select_page(key: str):
        def handler(e):
            current_nav["key"] = key
            content_col.controls = [pages[key]]
            content_col.update()
            _update_sidebar()
        return handler

    # Build sidebar nav items with group labels
    sidebar_nav_items = []
    _nav_item_map: dict[str, ft.Container] = {}
    for group_label, items in nav_groups:
        sidebar_nav_items.append(theme.sidebar_group_label(group_label))
        for label, icon, key in items:
            item = theme.sidebar_item(label, icon, selected=(key == "modules"))
            item.on_click = _select_page(key)
            sidebar_nav_items.append(item)
            _nav_item_map[key] = item

    def _update_sidebar():
        for key, item in _nav_item_map.items():
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
        padding=ft.Padding.symmetric(horizontal=8, vertical=12),
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
        padding=ft.Padding.symmetric(horizontal=theme.SPACING_LG, vertical=10),
        border=ft.Border.only(bottom=ft.BorderSide(1, theme.BORDER)),
    )

    # ---- Content area ----
    content_col = ft.ListView(
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
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    # ---- 组装页面 ----
    log_header = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.TERMINAL, size=16, color=theme.TEXT_SECONDARY),
                ft.Text("日志", size=13, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.only(left=8, top=4, bottom=2),
    )

    page.add(
        ft.Column(
            [
                header,
                unified_body,
                ft.Container(
                    content=ft.Column([log_header, log_view], spacing=0),
                    border=ft.Border.only(top=ft.BorderSide(1, theme.BORDER)),
                ),
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
