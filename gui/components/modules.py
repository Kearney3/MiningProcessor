"""数据处理模块区域组件"""
from datetime import datetime

import flet as ft

from .common import _last_directory, _update_last_directory, _log_message, _get_initial_directory, _show_path_confirm, ChipToggle, year_options, month_options, make_browse_handler, HeaderModeConfig, safe_update
from .types import ModuleRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_modules_section(page: ft.Page) -> tuple[ft.Container, "ModuleRefs"]:
    """创建数据处理模块区域，返回 (container, module_refs)"""

    current_date = datetime.now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)

    # --- Fuel ---
    fuel_path = ft.TextField(
        label="燃油数据处理",
        hint_text="输入路径或点击按钮选择...",
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    fuel_year = ft.Dropdown(
        label="年份",
        width=125,
        options=year_options(),
        value=current_year,
    )
    fuel_btn = theme.primary_btn("处理", icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Production ---
    prod_path = ft.TextField(
        label="生产数据处理",
        hint_text="输入路径或点击按钮选择...",
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
    )
    prod_file_btn = theme.secondary_btn("选文件", icon=ft.Icons.UPLOAD_FILE)
    prod_folder_btn = theme.secondary_btn("选文件夹", icon=ft.Icons.FOLDER_OPEN)
    prod_raw_start = ft.TextField(
        label="表头起始行",
        width=100,
        value="-1",
        hint_text="-1",
        color=theme.TEXT_PRIMARY,
    )
    prod_btn = theme.primary_btn("处理", icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Electrical ---
    elec_path = ft.TextField(
        label="电力数据处理",
        hint_text="输入路径或点击按钮选择...",
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    elec_year = ft.Dropdown(
        label="年份",
        width=125,
        options=year_options(),
        value=current_year,
    )
    elec_btn = theme.primary_btn("处理", icon=ft.Icons.PLAY_ARROW, disabled=False)
    elec_add_shift = ft.Checkbox(
        label="添加班次列",
        value=False,
        tooltip="在日期列右侧新增班次列",
    )
    elec_default_shift = ft.Dropdown(
        label="默认班次",
        width=100,
        options=[ft.dropdown.Option("Day"), ft.dropdown.Option("Night")],
        value="Day",
        visible=False,
    )

    def _on_shift_toggle(e):
        elec_default_shift.visible = elec_add_shift.value
        elec_default_shift.update()

    elec_add_shift.on_change = _on_shift_toggle

    # --- Work time ---
    work_path = ft.TextField(
        label="工时数据处理",
        hint_text="输入路径或点击按钮选择...",
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    work_year = ft.Dropdown(
        label="年份",
        width=125,
        options=year_options(),
        value=current_year,
    )
    work_month = ft.Dropdown(
        label="月份",
        width=125,
        options=month_options(),
        value=current_month,
    )
    _work_hmc = HeaderModeConfig(
        label="表头修改",
        tooltip="开启后按配置的映射关系重命名输出表头",
    )

    work_btn = theme.primary_btn("处理", icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Excel Merger ---
    merge_path = ft.TextField(
        label="Excel 合并",
        hint_text="输入路径或点击按钮选择...",
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    merge_keyword = ft.TextField(
        label="关键字",
        hint_text="例如: Fuel",
        width=150,
        color=theme.TEXT_PRIMARY,
    )
    merge_strip_time = ft.Checkbox(
        label="仅保留日期",
        value=False,
        tooltip="勾选后，时间列将去除时分秒，格式为 YYYY-MM-DD",
    )
    merge_btn = theme.primary_btn("合并", icon=ft.Icons.MERGE_TYPE, disabled=False)

    # --- 排序配置列表（Excel 合并用） ---
    sort_configs_state: list[dict] = []

    sort_rules_column = ft.Column(
        spacing=4,
        expand=True,
    )

    def build_sort_rules():
        controls = []
        for i, cfg in enumerate(sort_configs_state):
            idx = i  # 捕获当前索引

            col_field = ft.TextField(
                value=cfg.get("column", ""),
                text_size=12,
                hint_text="列名",
                expand=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
            )
            order_dropdown = ft.Dropdown(
                value="升序" if cfg.get("ascending", True) else "降序",
                options=[ft.dropdown.Option("升序"), ft.dropdown.Option("降序")],
                width=90,
                text_size=12,
            )

            def on_col_change(e, _idx=idx):
                sort_configs_state[_idx]["column"] = e.control.value

            def on_order_select(e, _idx=idx):
                sort_configs_state[_idx]["ascending"] = (e.control.value == "升序")

            col_field.on_change = on_col_change
            order_dropdown.on_select = on_order_select

            def move_up(e, _idx=idx):
                if _idx > 0:
                    sort_configs_state[_idx - 1], sort_configs_state[_idx] = (
                        sort_configs_state[_idx],
                        sort_configs_state[_idx - 1],
                    )
                    build_sort_rules()
                    sort_rules_column.update()

            def move_down(e, _idx=idx):
                if _idx < len(sort_configs_state) - 1:
                    sort_configs_state[_idx + 1], sort_configs_state[_idx] = (
                        sort_configs_state[_idx],
                        sort_configs_state[_idx + 1],
                    )
                    build_sort_rules()
                    sort_rules_column.update()

            def remove_row(e, _idx=idx):
                sort_configs_state.pop(_idx)
                build_sort_rules()
                sort_rules_column.update()

            up_btn = ft.IconButton(
                icon=ft.Icons.ARROW_UPWARD, tooltip="上移", on_click=move_up, icon_size=16
            )
            down_btn = ft.IconButton(
                icon=ft.Icons.ARROW_DOWNWARD, tooltip="下移", on_click=move_down, icon_size=16
            )
            del_btn = ft.IconButton(
                icon=ft.Icons.DELETE, tooltip="删除", on_click=remove_row, icon_size=16
            )

            row_container = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(str(idx + 1), width=30, size=12, color=theme.TEXT_SECONDARY),
                        col_field,
                        order_dropdown,
                        ft.Row([up_btn, down_btn, del_btn], spacing=2),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border=ft.Border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_SM,
                bgcolor=theme.SURFACE_HIGH,
            )

            controls.append(row_container)

        sort_rules_column.controls = controls
        sort_rules_column.update()

    def add_sort_config(e):
        sort_configs_state.append({"column": "", "ascending": True})
        build_sort_rules()

    add_sort_btn = theme.secondary_btn("添加排序条件", icon=ft.Icons.ADD, on_click=add_sort_config, height=36)

    # --- FilePicker instances (must be added to page.overlay to work repeatedly) ---
    _fuel_picker = ft.FilePicker()
    _prod_file_picker = ft.FilePicker()
    _prod_folder_picker = ft.FilePicker()
    _elec_picker = ft.FilePicker()
    _work_picker = ft.FilePicker()
    _merge_picker = ft.FilePicker()
    page.services.extend([
        _fuel_picker, _prod_file_picker, _prod_folder_picker,
        _elec_picker, _work_picker, _merge_picker,
    ])

    on_fuel_browse = make_browse_handler(
        _fuel_picker, fuel_path, fuel_btn, "选择燃油数据文件",
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_prod_pick_file = make_browse_handler(
        _prod_file_picker, prod_path, prod_btn, "选择生产数据文件",
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_prod_pick_folder = make_browse_handler(
        _prod_folder_picker, prod_path, prod_btn, "选择生产数据文件夹",
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_elec_browse = make_browse_handler(
        _elec_picker, elec_path, elec_btn, "选择电力数据文件",
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_work_browse = make_browse_handler(
        _work_picker, work_path, work_btn, "选择工时数据文件",
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_merge_browse = make_browse_handler(
        _merge_picker, merge_path, merge_btn, "选择包含 Excel 文件的文件夹",
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )

    # 绑定浏览按钮
    fuel_path.suffix.on_click = on_fuel_browse
    prod_file_btn.on_click = on_prod_pick_file
    prod_folder_btn.on_click = on_prod_pick_folder
    elec_path.suffix.on_click = on_elec_browse
    work_path.suffix.on_click = on_work_browse
    merge_path.suffix.on_click = on_merge_browse

    # --- 台账匹配开关（设备 / 油品 独立控制） ---
    match_eq_toggle = ft.Checkbox(
        label="设备台账匹配",
        value=False,
    )
    match_oil_toggle = ft.Checkbox(
        label="油品台账匹配",
        value=False,
    )

    header_hint = ft.Row(
        [
            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=theme.TEXT_SECONDARY),
            ft.Text("映射规则可在「用户配置 → 工作效率表头映射配置」中编辑", size=11, color=theme.TEXT_SECONDARY),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=_work_hmc.toggle.value,
    )

    def _on_toggle_extra(enabled):
        header_hint.visible = enabled
        safe_update(header_hint)

    _work_hmc._on_toggle_extra = _on_toggle_extra

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("数据处理模块"),
                ft.Text(
                    "选择数据文件或文件夹后点击处理按钮，各模块独立运行。",
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),
                theme.module_card([
                    ft.Row([fuel_path, fuel_year, fuel_btn], spacing=8),
                ]),
                theme.module_card([
                    ft.Row([prod_path, prod_btn], spacing=8),
                    ft.Row([prod_file_btn, prod_folder_btn, prod_raw_start], spacing=8),
                ]),
                theme.module_card([
                    ft.Row([elec_path, elec_year, elec_add_shift, elec_default_shift, elec_btn], spacing=8),
                ]),
                theme.module_card([
                    ft.Row([work_path, work_year, work_month, work_btn], spacing=6),
                    ft.Row(
                        [_work_hmc.toggle, _work_hmc.mode.row, _work_hmc.fuzzy],
                        spacing=theme.SPACING_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    header_hint,
                ]),
                theme.module_card([
                    ft.Row([merge_path, merge_keyword, merge_strip_time, merge_btn], spacing=8),
                    ft.Text("排序配置（可选，留空则自动按第一个时间列排序）", size=12,
                            color=theme.TEXT_SECONDARY),
                    ft.Row([sort_rules_column, add_sort_btn], spacing=8,
                           alignment=ft.MainAxisAlignment.START),
                ], spacing=4),
                ft.Row([match_eq_toggle, match_oil_toggle], spacing=8),
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

    module_refs = {
        "_match_eq_toggle": match_eq_toggle,
        "_match_oil_toggle": match_oil_toggle,
        "fuel": {"path": fuel_path, "year": fuel_year, "btn": fuel_btn},
        "prod": {"path": prod_path, "raw_start": prod_raw_start, "btn": prod_btn},
        "elec": {"path": elec_path, "year": elec_year, "btn": elec_btn, "add_shift": elec_add_shift, "default_shift": elec_default_shift},
        "work": {"path": work_path, "year": work_year, "month": work_month, "header_toggle": _work_hmc.toggle, "header_mode": _work_hmc.mode, "header_fuzzy": _work_hmc.fuzzy, "btn": work_btn},
        "merge": {
            "path": merge_path,
            "keyword": merge_keyword,
            "strip_time": merge_strip_time,
            "btn": merge_btn,
            "sort_configs_state": sort_configs_state,
        },
    }
    return container, module_refs
