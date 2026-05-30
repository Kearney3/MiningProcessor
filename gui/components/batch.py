"""批量处理模块区域组件"""
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_batch_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建批量处理模块区域，返回 (container, batch_refs)"""

    current_date = datetime.now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)
    _last_directory = [""]

    # --- 文件夹选择 ---
    batch_path = ft.TextField(
        label="批量处理文件夹",
        hint_text="选择包含待处理 Excel 文件的文件夹...",
        expand=True,
        read_only=False,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )

    # --- 年份/月份 ---
    batch_year = ft.Dropdown(
        label="年份",
        width=125,
        options=[ft.dropdown.Option(str(y)) for y in range(2015, 2040)],
        value=current_year,
    )
    batch_month = ft.Dropdown(
        label="月份",
        width=125,
        options=[ft.dropdown.Option(str(m)) for m in range(1, 13)],
        value=current_month,
    )

    # --- 生产数据表头自动检测 ---
    batch_auto_detect = ft.Checkbox(
        label="生产数据表头自动检测",
        value=True,
        tooltip="生产数据表头起始行使用自动检测",
    )

    # --- 合并输出 ---
    batch_merge = ft.Checkbox(
        label="合并输出",
        value=True,
        tooltip="将所有处理结果合并到单个 Excel 文件（Sheet 带前缀）",
    )

    # --- 台账匹配开关 ---
    batch_ledger_toggle = ft.Checkbox(
        label="启用台账匹配",
        value=True,
        tooltip="批量处理时自动匹配设备台账和油品台账",
    )

    # --- 工作效率表头修改开关 ---
    batch_header_toggle = ft.Checkbox(
        label="工作效率表头修改",
        value=True,
        tooltip="开启后按配置的映射关系重命名工作效率表输出表头",
    )
    batch_header_mode = ft.Dropdown(
        label="匹配模式",
        width=110,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        value="position",
        options=[
            ft.dropdown.Option(key="position", text="按位置"),
            ft.dropdown.Option(key="name", text="按列名"),
        ],
        tooltip="按位置: 按列序号匹配；按列名: 按列标题文本匹配",
    )
    batch_header_fuzzy = ft.Checkbox(
        label="模糊匹配",
        value=False,
        visible=False,
        tooltip="按列名匹配时启用模糊匹配（容错错别字）",
    )

    def _on_batch_mode_change(e):
        batch_header_fuzzy.visible = (batch_header_mode.value == "name")
        try:
            batch_header_fuzzy.update()
        except (RuntimeError, AttributeError):
            pass

    batch_header_mode.on_change = _on_batch_mode_change

    # --- 日期筛选 ---
    _selected_date = [current_date.date()]  # 用列表包裹以便闭包修改

    date_display = ft.Text(
        value=current_date.strftime("%Y-%m-%d"),
        size=14,
        weight=ft.FontWeight.W_500,
        color=theme.TEXT_PRIMARY,
    )

    date_filter_toggle = ft.Checkbox(
        label="按日期筛选",
        value=False,
        tooltip="开启后只保留所选日期的数据",
    )

    def _update_date_display():
        date_display.value = _selected_date[0].strftime("%Y-%m-%d")
        try:
            date_display.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_prev_day(e):
        _selected_date[0] = _selected_date[0] - timedelta(days=1)
        _update_date_display()

    def _on_today(e):
        _selected_date[0] = datetime.now().date()
        _update_date_display()

    async def _on_pick_date(e):
        dp = ft.DatePicker(
            first_date=datetime(2015, 1, 1),
            last_date=datetime(2040, 12, 31),
            current_date=datetime.combine(_selected_date[0], datetime.min.time()),
        )

        def _on_date_picked(ev):
            if dp.value:
                _selected_date[0] = dp.value.date()
                _update_date_display()
            page.close(dp)

        dp.on_change = _on_date_picked
        dp.on_dismiss = lambda ev: page.close(dp)
        page.open(dp)

    # --- 处理按钮 ---
    batch_btn = ft.Button(
        "批量处理",
        icon=ft.Icons.BOLT,
        disabled=False,
        style=ft.ButtonStyle(bgcolor=theme.PRIMARY, color="#FFFFFF"),
    )

    # --- 浏览按钮 ---
    async def on_batch_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.get_directory_path(
            dialog_title="选择批量处理文件夹",
            initial_directory=_last_directory[0] or None,
        )
        if path:
            batch_path.value = path
            _last_directory[0] = path
            batch_path.update()
            batch_btn.disabled = False
            batch_btn.update()

    batch_path.suffix.on_click = on_batch_browse

    # --- 布局 ---
    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("批量处理"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([batch_path], spacing=8),
                            ft.Row(
                                [
                                    batch_year,
                                    batch_month,
                                    date_filter_toggle,
                                    date_display,
                                    ft.Button(
                                        "上一天",
                                        icon=ft.Icons.ARROW_BACK_IOS,
                                        on_click=_on_prev_day,
                                        style=ft.ButtonStyle(bgcolor=theme.SURFACE_HIGH, color=theme.TEXT_PRIMARY),
                                    ),
                                    ft.Button(
                                        "今天",
                                        icon=ft.Icons.CALENDAR_TODAY,
                                        on_click=_on_today,
                                        style=ft.ButtonStyle(bgcolor=theme.SURFACE_HIGH, color=theme.TEXT_PRIMARY),
                                    ),
                                    ft.Button(
                                        "选择日期",
                                        icon=ft.Icons.CALENDAR_MONTH,
                                        on_click=_on_pick_date,
                                        style=ft.ButtonStyle(bgcolor=theme.SURFACE_HIGH, color=theme.TEXT_PRIMARY),
                                    ),
                                ],
                                spacing=4,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True,
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        batch_auto_detect,
                                        batch_merge,
                                        batch_ledger_toggle,
                                        batch_header_toggle,
                                        ft.Container(expand=True),
                                        batch_btn,
                                    ],
                                    spacing=theme.SPACING_SM,
                                    wrap=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                padding=ft.Padding.symmetric(horizontal=0, vertical=2),
                            ),
                        ],
                        spacing=8,
                        expand=True,
                    ),
                    padding=12,
                ),
            ],
            spacing=8,
            expand=True,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    batch_refs = {
        "path": batch_path,
        "year": batch_year,
        "month": batch_month,
        "auto_detect": batch_auto_detect,
        "merge": batch_merge,
        "ledger_toggle": batch_ledger_toggle,
        "header_toggle": batch_header_toggle,
        "header_mode": batch_header_mode,
        "header_fuzzy": batch_header_fuzzy,
        "date_filter_toggle": date_filter_toggle,
        "selected_date": _selected_date,
        "btn": batch_btn,
    }

    return container, batch_refs
