"""批量处理模块区域组件"""
from datetime import datetime, timedelta

import flet as ft

from .common import _last_directory, _update_last_directory, _log_message, _get_initial_directory, _show_path_confirm, ChipToggle, year_options, month_options, make_browse_handler, HeaderModeConfig, to_local_dt

try:
    from . import theme
except ImportError:
    import gui.theme as theme


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
        options=year_options(),
        value=current_year,
    )
    batch_month = ft.Dropdown(
        label="月份",
        width=125,
        options=month_options(),
        value=current_month,
    )

    # --- 生产数据表头自动检测 ---
    batch_auto_detect = ft.Checkbox(
        label="生产数据表头自动检测",
        value=True,
        tooltip="生产数据表头起始行使用自动检测",
    )

    # --- 表头起始行（仅在取消自动检测时显示） ---
    batch_raw_start = ft.TextField(
        label="表头起始行",
        width=100,
        value="-1",
        hint_text="-1（自动检测）",
        visible=False,
    )

    def _on_auto_detect_change(e):
        batch_raw_start.visible = not batch_auto_detect.value
        batch_raw_start.update()

    batch_auto_detect.on_change = _on_auto_detect_change

    # --- 合并输出 ---
    batch_merge = ft.Checkbox(
        label="合并输出",
        value=True,
        tooltip="将所有处理结果合并到单个 Excel 文件（Sheet 带前缀）",
    )

    # --- 台账匹配开关（设备 / 油品 独立控制） ---
    batch_match_eq = ft.Checkbox(
        label="设备台账匹配",
        value=True,
        tooltip="批量处理时自动匹配设备台账",
    )
    batch_match_oil = ft.Checkbox(
        label="油品台账匹配",
        value=True,
        tooltip="批量处理时自动匹配油品台账",
    )
    batch_skip_hidden_rows = ft.Checkbox(
        label="跳过隐藏行",
        value=False,
        tooltip="勾选后，Excel 中被隐藏的行将不会被读取",
    )
    batch_skip_hidden_cols = ft.Checkbox(
        label="跳过隐藏列",
        value=False,
        tooltip="勾选后，Excel 中被隐藏的列将不会被读取",
    )

    # --- 表内合并 ---
    batch_table_merge = ft.Checkbox(
        label="表内合并",
        value=False,
        tooltip="将所有数据通过左合并聚合到单个 Sheet（需先开启台账匹配）",
        disabled=not (batch_match_eq.value or batch_match_oil.value),
    )

    # ── 基准表芯片切换（表内合并专用） ──
    batch_base_table = ChipToggle(
        options=[("fuel", "燃油数据"), ("worktime", "工时数据")],
    )
    batch_base_table.row.visible = batch_table_merge.value

    # --- 工作效率表头修改开关 ---
    _batch_hmc = HeaderModeConfig(
        label="工作效率表头修改",
        tooltip="开启后按配置的映射关系重命名工作效率表输出表头",
        fuzzy_label="模糊匹配",
        fuzzy_tooltip="按列名匹配时启用模糊匹配（容错错别字）",
    )

    # ── 表内合并 / 合并输出 互斥 & 台账依赖 ──
    def _on_table_merge_change(e):
        if batch_table_merge.value:
            batch_merge.value = False
            batch_merge.disabled = True
        else:
            batch_merge.disabled = False
        batch_base_table.row.visible = batch_table_merge.value
        try:
            batch_merge.update()
            batch_base_table.row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_table_merge.on_change = _on_table_merge_change

    def _on_merge_change(e):
        if batch_merge.value:
            batch_table_merge.value = False
            batch_table_merge.disabled = True
            batch_base_table.row.visible = False
        else:
            any_ledger = batch_match_eq.value or batch_match_oil.value
            batch_table_merge.disabled = not any_ledger
        try:
            batch_table_merge.update()
            batch_base_table.row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_merge.on_change = _on_merge_change

    def _on_ledger_toggle_for_merge(e):
        any_ledger = batch_match_eq.value or batch_match_oil.value
        if not any_ledger:
            batch_table_merge.value = False
            batch_table_merge.disabled = True
            batch_base_table.row.visible = False
        else:
            batch_table_merge.disabled = batch_merge.value
        try:
            batch_table_merge.update()
            batch_base_table.row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_match_eq.on_change = _on_ledger_toggle_for_merge
    batch_match_oil.on_change = _on_ledger_toggle_for_merge

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
            current_date=to_local_dt(_selected_date[0]),
        )

        def _on_date_picked(ev):
            if dp.value:
                # dp.value 是 UTC datetime，需先转为本地时间再取日期
                _selected_date[0] = dp.value.astimezone().date()
                _update_date_display()
            page.pop_dialog()

        dp.on_change = _on_date_picked
        dp.on_dismiss = lambda ev: page.pop_dialog()
        page.show_dialog(dp)

    # --- 处理按钮 ---
    batch_btn = theme.primary_btn("批量处理", icon=ft.Icons.BOLT, disabled=False)

    # --- 进度区 ---
    batch_progress_bar = ft.ProgressBar(value=0.0, visible=False)
    batch_progress_text = ft.Text(value="", size=12, color=theme.TEXT_SECONDARY, visible=False)
    batch_cancel_btn = theme.secondary_btn("取消", icon=ft.Icons.CANCEL, visible=False, height=32)

    # --- 浏览按钮 ---
    _batch_picker = ft.FilePicker()
    page.services.append(_batch_picker)
    on_batch_browse = make_browse_handler(
        _batch_picker, batch_path, batch_btn, "选择批量处理文件夹",
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )

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
            ft.Container(ft.Row([batch_auto_detect, batch_raw_start], spacing=4), col={"xs": 12, "md": 6}),
            ft.Container(_batch_hmc.toggle, col={"xs": 12, "md": 6}),
            ft.Container(ft.Row([batch_match_eq, batch_match_oil, batch_skip_hidden_rows, batch_skip_hidden_cols], spacing=4), col={"xs": 12, "md": 6}),
            ft.Container(batch_merge, col={"xs": 12, "md": 6}),
            ft.Container(batch_table_merge, col={"xs": 12, "md": 6}),
            ft.Container(
                ft.Row([_batch_hmc.mode.row, _batch_hmc.fuzzy], spacing=4, wrap=True),
                col={"xs": 12, "md": 6},
            ),
            ft.Container(batch_base_table.row, col={"xs": 12, "md": 6}),
        ],
        run_spacing=4,
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    progress_row = ft.Row(
        [batch_progress_bar, batch_progress_text, batch_cancel_btn],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8,
        visible=False,
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

                # ── 进度区 ──
                progress_row,

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
        "raw_start_input": batch_raw_start,
        "merge": batch_merge,
        "table_merge": batch_table_merge,
        "base_table": batch_base_table,
        "match_eq_toggle": batch_match_eq,
        "match_oil_toggle": batch_match_oil,
        "_skip_hidden_rows_toggle": batch_skip_hidden_rows,
        "_skip_hidden_cols_toggle": batch_skip_hidden_cols,
        "header_toggle": _batch_hmc.toggle,
        "header_mode": _batch_hmc.mode,
        "header_fuzzy": _batch_hmc.fuzzy,
        "date_filter_toggle": date_filter_toggle,
        "selected_date": _selected_date,
        "btn": batch_btn,
        "progress_bar": batch_progress_bar,
        "progress_text": batch_progress_text,
        "cancel_btn": batch_cancel_btn,
        "progress_row": progress_row,
    }

    return container, batch_refs
