"""批量处理模块区域组件"""
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft

from .common import _last_directory, _update_last_directory

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def _show_path_confirm(text_field: ft.TextField):
    """在路径输入框右侧显示绿色确认勾。"""
    text_field.suffix = ft.Icon(ft.Icons.CHECK_CIRCLE, color=theme.SUCCESS, size=20)
    try:
        text_field.update()
    except (RuntimeError, AttributeError):
        pass


def create_batch_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建批量处理模块区域，返回 (container, batch_refs)"""

    current_date = datetime.now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)

    # --- 文件夹选择 ---
    batch_path = ft.TextField(
        label="批量处理文件夹",
        hint_text="选择包含待处理 Excel 文件的文件夹...",
        expand=True,
        read_only=False,
        color=theme.TEXT_PRIMARY,
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

    # --- 表内合并 ---
    batch_table_merge = ft.Checkbox(
        label="表内合并",
        value=False,
        tooltip="将所有数据通过左合并聚合到单个 Sheet（需先开启台账匹配）",
        disabled=not batch_ledger_toggle.value,
    )

    # ── 基准表芯片切换（表内合并专用） ──
    _base_table_state = ["fuel"]  # "fuel" | "worktime"

    _chip_fuel = ft.Container(
        content=ft.Text("燃油数据", size=12, weight=ft.FontWeight.W_500, color="#FFFFFF"),
        bgcolor=theme.PRIMARY,
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        on_click=None,
        ink=True,
    )
    _chip_worktime = ft.Container(
        content=ft.Text("工时数据", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        bgcolor=theme.SURFACE_HIGH,
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        on_click=None,
        ink=True,
    )

    class _BaseTableSelector:
        """带 .value 属性的芯片切换控件组，兼容 logic.py 的 .value 读取。"""
        def __init__(self, state: list, row: ft.Row):
            self._state = state
            self._row = row
        @property
        def value(self) -> str:
            return self._state[0]
        def update(self):
            self._row.update()

    batch_base_table_row = ft.Row(
        [_chip_fuel, _chip_worktime],
        spacing=0,
        tight=True,
        visible=batch_table_merge.value,
    )
    batch_base_table = _BaseTableSelector(_base_table_state, batch_base_table_row)

    def _update_base_table_chips():
        is_fuel = _base_table_state[0] == "fuel"
        _chip_fuel.bgcolor = theme.PRIMARY if is_fuel else theme.SURFACE_HIGH
        _chip_fuel.content.color = "#FFFFFF" if is_fuel else theme.TEXT_SECONDARY
        _chip_worktime.bgcolor = theme.PRIMARY if not is_fuel else theme.SURFACE_HIGH
        _chip_worktime.content.color = "#FFFFFF" if not is_fuel else theme.TEXT_SECONDARY
        try:
            batch_base_table_row.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_chip_fuel(e):
        _base_table_state[0] = "fuel"
        _update_base_table_chips()

    def _on_chip_worktime(e):
        _base_table_state[0] = "worktime"
        _update_base_table_chips()

    _chip_fuel.on_click = _on_chip_fuel
    _chip_worktime.on_click = _on_chip_worktime

    # --- 工作效率表头修改开关 ---
    batch_header_toggle = ft.Checkbox(
        label="工作效率表头修改",
        value=True,
        tooltip="开启后按配置的映射关系重命名工作效率表输出表头",
    )
    # ── 匹配模式芯片切换 ──
    _batch_mode_state = ["position"]  # "position" | "name"

    _batch_chip_position = ft.Container(
        content=ft.Text("按位置", size=12, weight=ft.FontWeight.W_500, color="#FFFFFF"),
        bgcolor=theme.PRIMARY,
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        on_click=None,
        ink=True,
    )
    _batch_chip_name = ft.Container(
        content=ft.Text("按列名", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        bgcolor=theme.SURFACE_HIGH,
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        on_click=None,
        ink=True,
    )
    class _ModeSelector:
        """带 .value 属性的芯片切换控件组，兼容 logic.py 的 .value 读取。"""
        def __init__(self, state: list, row: ft.Row):
            self._state = state
            self._row = row
        @property
        def value(self) -> str:
            return self._state[0]
        def update(self):
            self._row.update()

    batch_header_mode_row = ft.Row(
        [_batch_chip_position, _batch_chip_name],
        spacing=0,
        tight=True,
    )
    batch_header_mode = _ModeSelector(_batch_mode_state, batch_header_mode_row)

    batch_header_fuzzy = ft.Checkbox(
        label="模糊匹配",
        value=False,
        visible=False,
        tooltip="按列名匹配时启用模糊匹配（容错错别字）",
    )

    def _update_batch_chips():
        is_pos = _batch_mode_state[0] == "position"
        _batch_chip_position.bgcolor = theme.PRIMARY if is_pos else theme.SURFACE_HIGH
        _batch_chip_position.content.color = "#FFFFFF" if is_pos else theme.TEXT_SECONDARY
        _batch_chip_name.bgcolor = theme.PRIMARY if not is_pos else theme.SURFACE_HIGH
        _batch_chip_name.content.color = "#FFFFFF" if not is_pos else theme.TEXT_SECONDARY
        batch_header_fuzzy.visible = not is_pos
        try:
            batch_header_mode_row.update()
            batch_header_fuzzy.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_batch_chip_position(e):
        _batch_mode_state[0] = "position"
        _update_batch_chips()

    def _on_batch_chip_name(e):
        _batch_mode_state[0] = "name"
        _update_batch_chips()

    _batch_chip_position.on_click = _on_batch_chip_position
    _batch_chip_name.on_click = _on_batch_chip_name

    def _on_batch_header_toggle(e):
        enabled = batch_header_toggle.value
        _batch_chip_position.disabled = not enabled
        _batch_chip_name.disabled = not enabled
        if not enabled:
            batch_header_fuzzy.visible = False
        else:
            batch_header_fuzzy.visible = (_batch_mode_state[0] == "name")
        try:
            batch_header_mode_row.update()
            batch_header_fuzzy.update()
        except (RuntimeError, AttributeError):
            pass

    # ── 表内合并 / 合并输出 互斥 & 台账依赖 ──
    def _on_table_merge_change(e):
        if batch_table_merge.value:
            batch_merge.value = False
            batch_merge.disabled = True
        else:
            batch_merge.disabled = False
        batch_base_table_row.visible = batch_table_merge.value
        try:
            batch_merge.update()
            batch_base_table_row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_table_merge.on_change = _on_table_merge_change

    def _on_merge_change(e):
        if batch_merge.value:
            batch_table_merge.value = False
            batch_table_merge.disabled = True
            batch_base_table_row.visible = False
        else:
            batch_table_merge.disabled = not batch_ledger_toggle.value
        try:
            batch_table_merge.update()
            batch_base_table_row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_merge.on_change = _on_merge_change

    def _on_ledger_toggle_for_merge(e):
        if not batch_ledger_toggle.value:
            batch_table_merge.value = False
            batch_table_merge.disabled = True
            batch_base_table_row.visible = False
        else:
            batch_table_merge.disabled = batch_merge.value
        try:
            batch_table_merge.update()
            batch_base_table_row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_ledger_toggle.on_change = _on_ledger_toggle_for_merge

    batch_header_toggle.on_change = _on_batch_header_toggle

    # --- 日期筛选 ---
    _selected_date = [current_date.date()]  # 用列表包裹以便闭包修改

    _date_display_text = ft.Text(
        value=current_date.strftime("%Y-%m-%d"),
        size=14,
        weight=ft.FontWeight.W_600,
        color=theme.PRIMARY,
    )
    date_display = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.TODAY, size=16, color=theme.PRIMARY),
                _date_display_text,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.PRIMARY_CONTAINER,
        border=ft.Border.all(1, theme.PRIMARY),
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
    )

    date_filter_toggle = ft.Checkbox(
        label="按日期筛选",
        value=False,
        tooltip="开启后只保留所选日期的数据",
    )

    def _update_date_display():
        _date_display_text.value = _selected_date[0].strftime("%Y-%m-%d")
        try:
            _date_display_text.update()
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
            page.pop_dialog()

        dp.on_change = _on_date_picked
        dp.on_dismiss = lambda ev: page.pop_dialog()
        page.show_dialog(dp)

    # --- 处理按钮 ---
    batch_btn = theme.primary_btn("批量处理", icon=ft.Icons.BOLT, disabled=False)

    # --- 浏览按钮 ---
    async def on_batch_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.get_directory_path(
            dialog_title="选择批量处理文件夹",
            initial_directory=_last_directory[0] or None,
        )
        if path:
            batch_path.value = path
            _update_last_directory(path)
            _show_path_confirm(batch_path)
            batch_btn.disabled = False
            batch_btn.update()

    batch_path.suffix.on_click = on_batch_browse

    # --- 日期筛选行可见性 ---
    date_nav_row = ft.Row(
        [
            date_display,
            theme.secondary_btn("上一天", icon=ft.Icons.ARROW_BACK_IOS, on_click=_on_prev_day, height=32),
            theme.secondary_btn("今天", icon=ft.Icons.CALENDAR_TODAY, on_click=_on_today, height=32),
            theme.secondary_btn("选择日期", icon=ft.Icons.CALENDAR_MONTH, on_click=_on_pick_date, height=32),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=date_filter_toggle.value,
    )

    def _on_date_filter_toggle(e):
        date_nav_row.visible = date_filter_toggle.value
        try:
            date_nav_row.update()
        except (RuntimeError, AttributeError):
            pass

    date_filter_toggle.on_change = _on_date_filter_toggle

    # --- 布局 ---
    # 处理选项（可折叠，2 列布局）
    options_grid = ft.ResponsiveRow(
        [
            ft.Container(batch_auto_detect, col={"xs": 12, "md": 6}),
            ft.Container(batch_header_toggle, col={"xs": 12, "md": 6}),
            ft.Container(batch_ledger_toggle, col={"xs": 12, "md": 6}),
            ft.Container(batch_merge, col={"xs": 12, "md": 6}),
            ft.Container(batch_table_merge, col={"xs": 12, "md": 6}),
            ft.Container(
                ft.Row([batch_header_mode_row, batch_header_fuzzy], spacing=4, wrap=True),
                col={"xs": 12, "md": 6},
            ),
            ft.Container(batch_base_table_row, col={"xs": 12, "md": 6}),
        ],
        run_spacing=4,
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    options_collapsible = theme.make_collapsible(
        title="处理选项",
        subtitle="数据检测、台账匹配、合并输出等处理参数",
        icon=ft.Icons.TUNE,
        initially_expanded=False,
        content_controls=[options_grid],
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("批量处理"),
                ft.Text(
                    "选择文件夹后自动扫描并处理各类数据文件，结果可合并或分别输出。",
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),

                # ── 文件夹选择 ──
                theme.module_card([
                    ft.Row([batch_path], spacing=8),
                ], label="目标文件夹"),

                # ── 日期参数 ──
                theme.module_card([
                    ft.Row(
                        [batch_year, batch_month, date_filter_toggle],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    date_nav_row,
                ], label="日期参数"),

                # ── 处理选项（折叠） ──
                options_collapsible,

                # ── 操作按钮 ──
                ft.Row(
                    [batch_btn],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=theme.SPACING_MD,
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
        "table_merge": batch_table_merge,
        "base_table": batch_base_table,
        "ledger_toggle": batch_ledger_toggle,
        "header_toggle": batch_header_toggle,
        "header_mode": batch_header_mode,
        "header_fuzzy": batch_header_fuzzy,
        "date_filter_toggle": date_filter_toggle,
        "selected_date": _selected_date,
        "btn": batch_btn,
    }

    return container, batch_refs
