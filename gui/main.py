"""GUI 主窗口：浅色桌面工作台与侧边栏导航布局。"""
import flet as ft
import logging
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

try:
    __version__ = version("MiningProcessor")
except PackageNotFoundError:
    __version__ = "dev"

from . import i18n as i18n
from func.config_loader import get_user_config, update_user_config
from func.logger import setup_logging

# 组件模块在导入阶段会创建少量带翻译文本的常量。先读取持久化语言，
# 再导入组件，确保首次启动就使用用户选择的语言，而不是先短暂加载中文。
i18n.init(get_user_config("language", i18n.DEFAULT_LANGUAGE))

from . import components as cmp
from . import logic as logic
from .log_system import LogSystem
from .log_system import MIN_LOG_HEIGHT  # re-exported for test access
from .log_broker import install_gui_log_handler

try:
    from . import theme
except ImportError:
    import gui.theme as theme

MIN_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
INITIAL_WINDOW_WIDTH = 1000
INITIAL_WINDOW_HEIGHT = 1050

_LANG_OPTIONS = i18n.get_language_options()


def _create_lang_switcher(page: ft.Page) -> ft.Container:
    """创建语言切换器 SegmentedButton。"""
    current = i18n.get_language()

    def _on_lang_change(e: ft.ControlEvent):
        selected_key = e.data
        if isinstance(selected_key, list):
            selected_key = selected_key[0] if selected_key else None
        if selected_key and selected_key != i18n.get_language():
            selected_key = i18n.set_language(selected_key)
            update_user_config({"language": selected_key})
            # 弹窗提示用户重启
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text(i18n.t("language:changedTitle")),
                content=ft.Text(i18n.t("language:changedMessage")),
                actions=[
                    ft.TextButton(i18n.t("common:ok"), on_click=lambda _: setattr(dlg, "open", False) or page.update()),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

    buttons = []
    for code, label in _LANG_OPTIONS:
        is_selected = code == current
        buttons.append(
            ft.Segment(
                value=code,
                label=ft.Text(label, size=11, weight=ft.FontWeight.W_600),
            ),
        )

    switcher = ft.SegmentedButton(
        selected=[current],
        segments=buttons,
        on_change=_on_lang_change,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            shape=ft.RoundedRectangleBorder(radius=6),
        ),
        show_selected_icon=False,
    )

    return ft.Container(
        content=switcher,
        margin=ft.Margin.only(left=8, right=0, top=0, bottom=0),
    )


def main(page: ft.Page):
    setup_logging()
    install_gui_log_handler()

    # 初始化 i18n（在创建任何 UI 之前）
    saved_lang = get_user_config("language", "zh")
    i18n.init(saved_lang)

    page.title = i18n.t("app:矿山数据处理工具_2f4a")
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    page.assets_dir = str(assets_dir)
    page.fonts={
        "MiSans": "fonts/MiSansVF.ttf",
    }
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        font_family="MiSans",
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary=theme.PRIMARY,
            on_primary="#FFFFFF",
            primary_container=theme.PRIMARY_CONTAINER,
            on_primary_container=theme.TEXT_PRIMARY,
            secondary=theme.TEXT_SECONDARY,
            surface=theme.SURFACE,
            on_surface=theme.TEXT_PRIMARY,
            on_surface_variant=theme.TEXT_SECONDARY,
            outline=theme.BORDER_STRONG,
            outline_variant=theme.BORDER,
            error=theme.ERROR,
        ),
        scaffold_bgcolor=theme.BG,
        canvas_color=theme.BG,
        divider_color=theme.BORDER,
        hint_color=theme.TEXT_SECONDARY,
        focus_color=theme.PRIMARY_CONTAINER,
        hover_color=theme.SURFACE_HIGH,
        scrollbar_theme=ft.ScrollbarTheme(
            thickness=6,
            radius=8,
            thumb_color=theme.BORDER_STRONG,
            track_color="transparent",
        ),
        divider_theme=ft.DividerTheme(
            color=theme.BORDER,
            thickness=1,
            space=1,
        ),
        progress_indicator_theme=ft.ProgressIndicatorTheme(
            color=theme.PRIMARY,
            linear_track_color=theme.SURFACE_HIGH,
            linear_min_height=5,
            border_radius=99,
        ),
        tooltip_theme=ft.TooltipTheme(
            text_style=ft.TextStyle(size=12, color="#FFFFFF"),
            wait_duration=450,
            show_duration=1800,
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        ),
        data_table_theme=ft.DataTableTheme(
            heading_row_color=theme.SURFACE_HIGH,
            heading_text_style=ft.TextStyle(
                size=12,
                weight=ft.FontWeight.W_600,
                color=theme.TEXT_PRIMARY,
            ),
            data_text_style=ft.TextStyle(size=12, color=theme.TEXT_PRIMARY),
            divider_thickness=1,
            column_spacing=20,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )
    page.bgcolor = theme.BG
    page.padding = 0
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
    model_ledger_section, model_ledger_refs = cmp.create_model_ledger_section(page, log)
    daily_report_section, daily_report_refs = cmp.create_daily_report_section(
        page, log, ledger_refs, model_ledger_refs
    )
    config_section, config_refs = cmp.create_config_section(page, log)
    user_config_section, user_config_refs = cmp.create_user_config_section(page, log)
    maint_config_section, maint_config_refs = cmp.create_maint_config_section(page, log)
    llm_section, llm_refs = cmp.create_llm_labeling_section(page)
    modules_section, module_refs = cmp.create_modules_section(page)
    batch_section, batch_refs = cmp.create_batch_section(page)
    module_refs["batch"] = batch_refs
    ledger_match_section, ledger_match_refs = cmp.create_ledger_match_section(page, log, ledger_refs, oil_ledger_refs)
    sync_section, sync_refs = cmp.create_sync_section(page)

    # ---- 绑定处理按钮 ----
    logic.wire_processing_buttons(
        module_refs, page, log, ledger_refs, oil_ledger_refs, model_ledger_refs
    )
    logic.wire_sync_button(sync_refs, page, log, module_refs=module_refs)
    logic.wire_test_db_button(user_config_refs, page, log)
    logic.wire_test_api_button(user_config_refs, page, log)

    # ---- 侧边栏导航（分组） ----
    nav_groups = [
        (i18n.t("nav:工作区_4fa8"), [
            (i18n.t("nav:数据处理_cfc0"), ft.Icons.PLAY_ARROW, "modules"),
            (i18n.t("nav:批量处理_ba72"), ft.Icons.BOLT, "batch"),
            (i18n.t("nav:LLM标注_8529"), ft.Icons.SMART_TOY, "llm"),
            (i18n.t("nav:数据同步_9d91"), ft.Icons.CLOUD_SYNC, "sync"),
            (i18n.t("nav:日报导出_4ed9"), getattr(ft.Icons, "SUMMARIZE", ft.Icons.DESCRIPTION), "daily_report"),
            (i18n.t("nav:台账匹配_9897"), ft.Icons.MANAGE_SEARCH, "ledger_match"),
        ]),
        (i18n.t("nav:管理_08b5"), [
            (i18n.t("nav:设备台账_e6a7"), ft.Icons.INVENTORY_2, "ledger"),
            (i18n.t("nav:油品台账_53fa"), ft.Icons.OIL_BARREL, "oil_ledger"),
            (i18n.t("nav:型号台账_3e0b"), getattr(ft.Icons, "ENGINEERING", ft.Icons.INVENTORY_2), "model_ledger"),
            (i18n.t("nav:装载量配置_c389"), ft.Icons.TUNE, "config"),
            (i18n.t("nav:维修分类配置_4ee9"), ft.Icons.CATEGORY, "maint_config"),
            (i18n.t("nav:用户配置_dd1e"), ft.Icons.SETTINGS, "user_config"),
        ]),
    ]
    nav_items_data = [item for _, items in nav_groups for item in items]

    # Content pages
    pages = {
        "modules": ft.Column([modules_section], expand=True, spacing=8),
        "batch": ft.Column([batch_section], expand=True, spacing=8),
        "llm": ft.Column([llm_section], expand=True, spacing=8),
        "sync": ft.Column([sync_section], expand=True, spacing=8),
        "ledger_match": ft.Column([ledger_match_section], expand=True, spacing=8),
        "ledger": ft.Column([ledger_section], expand=True, spacing=8),
        "oil_ledger": ft.Column([oil_ledger_section], expand=True, spacing=8),
        "model_ledger": ft.Column([model_ledger_section], expand=True, spacing=8),
        "daily_report": ft.Column([daily_report_section], expand=True, spacing=8),
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
            icon_ctrl.color = theme.PRIMARY if is_selected else theme.TEXT_TERTIARY
            text_ctrl.color = theme.PRIMARY_HOVER if is_selected else theme.TEXT_SECONDARY
            text_ctrl.weight = (
                ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_500
            )
            try:
                item.update()
            except (RuntimeError, AttributeError):
                pass

    sidebar = ft.Container(
        content=ft.ListView(
            sidebar_nav_items,
            spacing=2,
            expand=True,
            padding=ft.Padding.only(bottom=theme.SPACING_SM),
        ),
        width=theme.SIDEBAR_WIDTH,
        bgcolor=theme.SIDEBAR_BG,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        border=ft.Border.only(right=ft.BorderSide(1, theme.BORDER)),
    )

    # ---- Header ----
    app_mark = ft.Container(
        content=ft.Icon(ft.Icons.DATASET_OUTLINED, size=21, color="#FFFFFF"),
        width=36,
        height=36,
        alignment=ft.Alignment.CENTER,
        bgcolor=theme.PRIMARY,
        border_radius=theme.RADIUS_MD,
    )
    version_badge = ft.Container(
        content=ft.Text(
            f"v{__version__}",
            size=11,
            weight=ft.FontWeight.W_500,
            color=theme.TEXT_SECONDARY,
        ),
        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
        bgcolor=theme.SURFACE_HIGH,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=99,
    )
    header = ft.Container(
        content=ft.Row(
            [
                app_mark,
                ft.Column(
                    [
                        ft.Text(
                            i18n.t("app:矿山数据处理工具_2f4a"),
                            size=17,
                            weight=ft.FontWeight.W_700,
                            color=theme.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            i18n.t("app:报表处理与数据管理_d8e1"),
                            size=11,
                            color=theme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=0,
                ),
                ft.Container(expand=True),
                version_badge,
                _create_lang_switcher(page),
            ],
            spacing=theme.SPACING_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.SURFACE,
        padding=ft.Padding.symmetric(horizontal=theme.SPACING_LG, vertical=12),
        border=ft.Border.only(bottom=ft.BorderSide(1, theme.BORDER)),
    )

    # ---- Content area ----
    content_col = ft.ListView(
        [pages["modules"]],
        spacing=0,
        expand=True,
        padding=theme.SPACING_LG,
    )

    # Sidebar + content wrapped in a single card container
    unified_body = ft.Container(
        content=ft.Row(
            [sidebar, content_col],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        expand=True,
        bgcolor=theme.BG,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        margin=ft.Margin.only(
            left=theme.SPACING_LG,
            right=theme.SPACING_LG,
            top=theme.SPACING_LG,
        ),
    )

    # ---- 组装页面 ----
    log_header = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.TERMINAL, size=16, color=theme.TEXT_SECONDARY),
                ft.Text(
                    i18n.t("app:运行日志_a3c7"),
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=theme.TEXT_PRIMARY,
                ),
                ft.Text(
                    i18n.t("app:处理进度和问题原因会显示在这里_b2f9"),
                    size=11,
                    color=theme.TEXT_SECONDARY,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
    )

    page.add(
        ft.Column(
            [
                header,
                unified_body,
                ft.Container(
                    content=ft.Column([log_header, log_view], spacing=0),
                    margin=ft.Margin.only(
                        left=theme.SPACING_LG,
                        right=theme.SPACING_LG,
                        top=theme.SPACING_SM,
                        bottom=theme.SPACING_LG,
                    ),
                    bgcolor=theme.SURFACE,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_LG,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                ),
            ],
            expand=True,
            spacing=0,
        )
    )

    # ---- 初始化（放在 page.add 之后） ----
    logic.init(config_refs)
    log(i18n.t("app:已就绪_c4d6"))

    # ---- 页面关闭回调：取消所有正在运行的后台任务 ----
    def _on_page_close(e):
        logic.shutdown_tasks()
        log_system.shutdown()

    page.on_disconnect = _on_page_close
    page.on_close = _on_page_close
