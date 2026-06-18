"""MineBase 数据同步区域组件"""
from datetime import date, timedelta

import flet as ft

from .common import (
    _get_initial_directory,
    _last_directory,
    _show_path_confirm,
    _update_last_directory,
    ChipToggle,
)

try:
    from . import theme
except ImportError:
    import gui.theme as theme


# 数据类型定义
DATA_TYPES = [
    ("fuel", "油耗数据"),
    ("electrical", "电耗数据"),
    ("operation", "设备运行"),
    ("production", "生产数据"),
    ("work_efficiency", "工作效率"),
]

# 年份范围：当前年 ± 2
_CURRENT_YEAR = date.today().year
_YEAR_OPTIONS = [str(y) for y in range(_CURRENT_YEAR - 2, _CURRENT_YEAR + 3)]
_MONTH_OPTIONS = [str(m) for m in range(1, 13)]


def create_sync_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建 MineBase 数据同步区域，返回 (container, refs_dict)"""

    # --- 目录路径 ---
    sync_path = ft.TextField(
        label="输出目录",
        hint_text="选择 MiningProcessor 输出目录...",
        expand=True,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        value=_get_initial_directory(),
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )

    _browse_picker = ft.FilePicker()
    page.services.append(_browse_picker)

    async def on_browse(e):
        result = await _browse_picker.get_directory_path(dialog_title="选择输出目录")
        if result:
            sync_path.value = result
            _update_last_directory(result, is_dir=True)
            _show_path_confirm(sync_path)
            sync_path.update()

    sync_path.suffix.on_click = on_browse

    # --- 同步模式 ---
    mode_toggle = ChipToggle(
        options=[("api", "API 模式"), ("database", "直连数据库")],
        initial="api",
    )

    # --- 数据类型选择 ---
    type_checks = {}
    for key, label in DATA_TYPES:
        type_checks[key] = ft.Checkbox(
            label=label,
            value=True,
            active_color=theme.PRIMARY,
        )

    select_all = ft.Checkbox(
        label="全选",
        value=True,
        active_color=theme.PRIMARY,
    )

    def on_select_all(e):
        for cb in type_checks.values():
            cb.value = select_all.value
            cb.update()

    select_all.on_change = on_select_all

    def on_type_change(e):
        all_checked = all(cb.value for cb in type_checks.values())
        select_all.value = all_checked
        select_all.update()

    for cb in type_checks.values():
        cb.on_change = on_type_change

    # --- 预览模式 ---
    dry_run_check = ft.Checkbox(
        label="预览模式（不实际推送）",
        value=False,
        active_color=theme.PRIMARY,
    )

    # --- 工时表头映射 & 台账匹配 ---
    header_mapping_check = ft.Checkbox(
        label="应用工时表头映射",
        value=True,
        active_color=theme.PRIMARY,
        tooltip="对工作效率表应用列名映射配置",
    )

    ledger_match_check = ft.Checkbox(
        label="应用台账匹配",
        value=False,
        active_color=theme.PRIMARY,
        tooltip="使用设备台账标准化设备名称",
    )

    # --- 年份/月份 ---
    year_dropdown = ft.Dropdown(
        label="年份",
        options=[ft.dropdown.Option(v) for v in _YEAR_OPTIONS],
        value=str(_CURRENT_YEAR),
        width=120,
        dense=True,
    )

    month_dropdown = ft.Dropdown(
        label="月份",
        options=[ft.dropdown.Option(v) for v in _MONTH_OPTIONS],
        value=str(date.today().month),
        width=100,
        dense=True,
    )

    # --- 表头起始行 ---
    header_row_field = ft.TextField(
        label="表头起始行",
        hint_text="自动检测",
        width=120,
        dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # --- 日期范围 ---
    today = date.today()
    yesterday = today - timedelta(days=1)

    date_start_field = ft.TextField(
        label="起始日期",
        value=yesterday.isoformat(),
        width=140,
        dense=True,
        hint_text="YYYY-MM-DD",
    )

    date_end_field = ft.TextField(
        label="结束日期",
        value=today.isoformat(),
        width=140,
        dense=True,
        hint_text="YYYY-MM-DD",
    )

    def on_yesterday_click(e):
        date_start_field.value = yesterday.isoformat()
        date_end_field.value = yesterday.isoformat()
        date_start_field.update()
        date_end_field.update()

    yesterday_btn = ft.ElevatedButton(
        "昨日",
        icon=ft.Icons.CALENDAR_TODAY,
        on_click=on_yesterday_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM),
        ),
    )

    def on_clear_date(e):
        date_start_field.value = ""
        date_end_field.value = ""
        date_start_field.update()
        date_end_field.update()

    clear_date_btn = ft.ElevatedButton(
        "清除",
        icon=ft.Icons.CLEAR_ALL,
        on_click=on_clear_date,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM),
        ),
    )

    # --- 同步按钮 ---
    sync_btn = theme.primary_btn("同步到 MineBase", icon=ft.Icons.CLOUD_UPLOAD)

    # --- 结果显示 ---
    result_text = ft.Text(
        "",
        size=13,
        color=theme.TEXT_SECONDARY,
        visible=False,
    )

    # --- 布局 ---
    type_row = ft.ResponsiveRow(
        [ft.Container(select_all, col={"xs": 12, "md": 6})]
        + [ft.Container(cb, col={"xs": 12, "md": 6}) for cb in type_checks.values()],
        run_spacing=4,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("MineBase 数据同步"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("输出目录", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            sync_path,
                            ft.Divider(height=1, color=theme.BORDER),
                            ft.Text("同步模式", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            mode_toggle.row,
                            ft.Divider(height=1, color=theme.BORDER),
                            ft.Text("处理参数", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            ft.ResponsiveRow(
                                [
                                    ft.Container(year_dropdown, col={"xs": 6, "md": 3}),
                                    ft.Container(month_dropdown, col={"xs": 6, "md": 3}),
                                    ft.Container(header_row_field, col={"xs": 6, "md": 3}),
                                ],
                                run_spacing=4,
                            ),
                            ft.Divider(height=1, color=theme.BORDER),
                            ft.Text("日期范围过滤", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            ft.ResponsiveRow(
                                [
                                    ft.Container(date_start_field, col={"xs": 6, "md": 3}),
                                    ft.Container(date_end_field, col={"xs": 6, "md": 3}),
                                    ft.Container(
                                        ft.Row([yesterday_btn, clear_date_btn], spacing=8),
                                        col={"xs": 12, "md": 6},
                                    ),
                                ],
                                run_spacing=4,
                                alignment=ft.MainAxisAlignment.START,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Divider(height=1, color=theme.BORDER),
                            ft.Text("数据类型", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            type_row,
                            ft.Divider(height=1, color=theme.BORDER),
                            dry_run_check,
                            header_mapping_check,
                            ledger_match_check,
                            ft.Row(
                                [sync_btn, result_text],
                                alignment=ft.MainAxisAlignment.START,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=12,
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=theme.SURFACE,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_LG,
                    padding=theme.SPACING_LG,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding.symmetric(horizontal=0, vertical=8),
    )

    refs = {
        "path": sync_path,
        "mode": mode_toggle,
        "types": type_checks,
        "dry_run": dry_run_check,
        "btn": sync_btn,
        "result_text": result_text,
        "year": year_dropdown,
        "month": month_dropdown,
        "header_row": header_row_field,
        "date_start": date_start_field,
        "date_end": date_end_field,
        "apply_header": header_mapping_check,
        "use_ledger": ledger_match_check,
    }

    return container, refs
