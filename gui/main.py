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


class LogSystem:
    """封装日志队列、消费者线程、UI 刷新逻辑。"""

    def __init__(self, page: ft.Page, log_refs: dict):
        self._page = page
        self._log_list = log_refs["log_list"]
        self._log_height_container = log_refs["list_container"]
        self._level_filter = log_refs["level_filter"]
        self._export_button = log_refs["export_button"]
        self._resize_handle = log_refs["resize_handle"]
        self._is_at_bottom = log_refs["_is_at_bottom"]
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
        if levelno >= logging.ERROR:
            return ft.Colors.RED
        if levelno >= logging.WARNING:
            return ft.Colors.ORANGE
        return None

    def _get_selected_level(self) -> str:
        raw_value = getattr(self._level_filter, "value", "ALL")
        if raw_value is None:
            return "ALL"
        return str(raw_value).strip() or "ALL"

    def _get_filtered_log_records(self) -> list[dict[str, object]]:
        selected_level = self._get_selected_level()
        with self._log_records_lock:
            if selected_level == "ALL":
                return list(self._log_records)
            return [r for r in self._log_records if str(r.get("levelname", "")) == selected_level]

    def _flush_pending_to_ui(self):
        """将待显示记录追加到 ListView。"""
        with self._pending_lock:
            batch = self._pending_records[:]
            self._pending_records.clear()
        if not batch or self._shutdown_event.is_set():
            return
        batch.sort(key=lambda r: r.get("seq", 0))
        selected_level = self._get_selected_level()
        for record in batch:
            if selected_level != "ALL" and record.get("levelname") != selected_level:
                continue
            self._log_list.controls.append(
                ft.Text(
                    str(record["message"]),
                    size=13,
                    selectable=True,
                    color=self._level_color(int(record["levelno"])),
                )
            )
        if len(self._log_list.controls) > MAX_LOG_RECORDS:
            self._log_list.controls = self._log_list.controls[-MAX_LOG_RECORDS:]
        try:
            self._log_list.update()
            if self._is_at_bottom[0]:
                self._page.run_task(self._log_list.scroll_to, offset=-1)
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
            self._page.run_thread(self._flush_pending_to_ui)
        except Exception:
            logging.getLogger(__name__).debug("page.run_thread 失败（页面可能已关闭）")

    def _append_log_record(self, log_item: dict[str, object]):
        record = {
            "timestamp": str(log_item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "created": float(log_item.get("created", 0)),
            "seq": int(log_item.get("seq", 0)),
            "levelno": int(log_item["levelno"]),
            "levelname": str(log_item["levelname"]),
            "message": str(log_item["message"]),
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

    def _apply_filters(self, _e=None):
        with self._log_records_lock:
            records = list(self._log_records)
        selected_level = self._get_selected_level()
        filtered = [
            r for r in records
            if selected_level == "ALL" or r.get("levelname") == selected_level
        ]
        self._log_list.controls = [
            ft.Text(
                str(r["message"]),
                size=13,
                selectable=True,
                color=self._level_color(int(r["levelno"])),
            )
            for r in filtered
        ]
        try:
            self._log_list.update()
            if self._is_at_bottom[0]:
                self._page.run_task(self._log_list.scroll_to, offset=-1)
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

    def _clear_logs(self, e=None):
        self._log_list.controls.clear()
        with self._log_records_lock:
            self._log_records.clear()
        try:
            self._log_list.update()
        except (RuntimeError, AttributeError):
            pass

    def _scroll_to_bottom(self, e=None):
        try:
            self._page.run_task(self._log_list.scroll_to, offset=-1)
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
                        self._flush_pending_to_ui()
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
                        self._flush_pending_to_ui()
            except Exception as ex:
                import sys
                print(f"[日志消费线程异常] {ex}", file=sys.stderr)


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

    # ---- 日志系统 ----
    log_system = LogSystem(page, log_refs)
    log_system.start()

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
    logic.wire_test_db_button(user_config_refs, page, log)
    logic.wire_test_api_button(user_config_refs, page, log)

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

    # ---- 初始化（放在 page.add 之后） ----
    logic.init(config_refs)
    log("已就绪")
