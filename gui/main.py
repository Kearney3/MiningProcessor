"""
GUI 主窗口 - Flet 实现
深色模式 + 侧边栏导航布局
使用模块化结构：components.py（UI组件）+ logic.py（业务逻辑）
"""
import flet as ft
import logging
from pathlib import Path

from . import components as cmp
from . import logic as logic
from .log_system import LogSystem
from .log_system import MIN_LOG_HEIGHT  # re-exported for test access

try:
    from . import theme
except ImportError:
    import gui.theme as theme

from func.logger import setup_logging

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
    _icon_path = Path(__file__).resolve().parent.parent / "assets" / "app_icon.png"
    if _icon_path.exists():
        page.window.icon = str(_icon_path)

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
    maint_config_section, maint_config_refs = cmp.create_maint_config_section(page, log)
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
            ("维修分类配置", ft.Icons.CATEGORY, "maint_config"),
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
        "maint_config": ft.Column([maint_config_section], expand=True, spacing=8),
        "user_config": ft.Column([user_config_section], expand=True, spacing=8),
    }

    current_nav = {"key": "modules"}
    _prev_nav_key = ["modules"]  # mutable container for closure

    def _select_page(key: str):
        def handler(e):
            old_key = _prev_nav_key[0]
            _prev_nav_key[0] = key
            current_nav["key"] = key
            content_col.controls = [pages[key]]
            content_col.update()
            _update_sidebar(old_key, key)
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

    def _update_sidebar(old_key: str, new_key: str):
        for key in (old_key, new_key):
            item = _nav_item_map.get(key)
            if item is None:
                continue
            is_selected = (key == new_key)
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
                ft.Text("v1.2.0", size=12, color=theme.TEXT_SECONDARY),
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
