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
        value="6",
        hint_text="6",
        color=theme.TEXT_PRIMARY,
        disabled=True,
    )
    prod_auto_detect = ft.Switch(
        label="自动识别表头",
        value=True,
        active_color=theme.PRIMARY,
    )

    def _on_prod_auto_detect_change(e):
        is_auto = prod_auto_detect.value
        prod_raw_start.disabled = is_auto
        if is_auto:
            prod_raw_start.value = "6"
        prod_raw_start.update()

    prod_auto_detect.on_change = _on_prod_auto_detect_change
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

    # --- Maintenance ---
    maint_path = ft.TextField(
        label="维修记录处理",
        hint_text="选择出勤统计表文件或文件夹...",
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
    )
    maint_file_btn = theme.secondary_btn("选文件", icon=ft.Icons.UPLOAD_FILE)
    maint_folder_btn = theme.secondary_btn("选文件夹", icon=ft.Icons.FOLDER_OPEN)
    maint_btn = theme.primary_btn("处理", icon=ft.Icons.PLAY_ARROW, disabled=False)
    maint_split_year = ft.Checkbox(
        label="按年份拆分输出",
        value=False,
        tooltip="勾选后，每年生成独立的统计文件",
    )
    maint_details_only = ft.Checkbox(
        label="仅导出明细",
        value=False,
        tooltip="勾选后只输出维修明细 sheet（不含统计表），文件更小、打开更快",
    )

    # --- FilePicker instances (must be added to page.overlay to work repeatedly) ---
    _fuel_picker = ft.FilePicker()
    _prod_file_picker = ft.FilePicker()
    _prod_folder_picker = ft.FilePicker()
    _elec_picker = ft.FilePicker()
    _work_picker = ft.FilePicker()
    _merge_picker = ft.FilePicker()
    _maint_file_picker = ft.FilePicker()
    _maint_folder_picker = ft.FilePicker()
    page.services.extend([
        _fuel_picker, _prod_file_picker, _prod_folder_picker,
        _elec_picker, _work_picker, _merge_picker,
        _maint_file_picker, _maint_folder_picker,
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
        _work_picker, work_path, work_btn, "选择工时数据文件或文件夹",
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_merge_browse = make_browse_handler(
        _merge_picker, merge_path, merge_btn, "选择包含 Excel 文件的文件夹",
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_maint_pick_file = make_browse_handler(
        _maint_file_picker, maint_path, maint_btn, "选择出勤统计表文件",
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_maint_pick_folder = make_browse_handler(
        _maint_folder_picker, maint_path, maint_btn, "选择出勤统计表文件夹",
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
    maint_file_btn.on_click = on_maint_pick_file
    maint_folder_btn.on_click = on_maint_pick_folder

    # --- 台账匹配开关（设备 / 油品 独立控制） ---
    match_eq_toggle = ft.Checkbox(
        label="设备台账匹配",
        value=False,
    )
    match_oil_toggle = ft.Checkbox(
        label="油品台账匹配",
        value=False,
    )
    skip_hidden_rows_toggle = ft.Checkbox(
        label="跳过隐藏行",
        value=False,
        tooltip="勾选后，Excel 中被隐藏的行将不会被读取",
    )
    skip_hidden_cols_toggle = ft.Checkbox(
        label="跳过隐藏列",
        value=False,
        tooltip="勾选后，Excel 中被隐藏的列将不会被读取",
    )

    # --- 异常值检测开关 ---
    _anomaly_mode = "flag"  # 内部状态：flag | filter | handle

    anomaly_enabled = ft.Checkbox(
        label="启用异常值检测",
        value=False,
        tooltip="开启后对处理的数据进行异常值检测",
    )
    anomaly_report = ft.Checkbox(
        label="输出异常报告",
        value=False,
        tooltip="生成异常报告 Excel 文件",
    )
    anomaly_flag = ft.Checkbox(
        label="标记异常值",
        value=True,
        tooltip="在数据中标记异常值（不删除）",
    )
    anomaly_filter = ft.Checkbox(
        label="过滤异常值",
        value=False,
        tooltip="移除异常行（与标记互斥）",
    )
    anomaly_handle = ft.Checkbox(
        label="处理异常值",
        value=False,
        tooltip="按用户配置替换异常值（与标记互斥）",
    )

    def _set_anomaly_mode(mode: str):
        """设置异常值处理模式，确保三选一互斥。"""
        nonlocal _anomaly_mode
        _anomaly_mode = mode
        anomaly_flag.value = (mode == "flag")
        anomaly_filter.value = (mode == "filter")
        anomaly_handle.value = (mode == "handle")
        safe_update(anomaly_flag)
        safe_update(anomaly_filter)
        safe_update(anomaly_handle)

    def _on_anomaly_enabled_change(e):
        enabled = anomaly_enabled.value
        anomaly_report.disabled = not enabled
        anomaly_flag.disabled = not enabled
        anomaly_filter.disabled = not enabled
        anomaly_handle.disabled = not enabled
        safe_update(anomaly_report)
        safe_update(anomaly_flag)
        safe_update(anomaly_filter)
        safe_update(anomaly_handle)

    def _on_anomaly_flag_change(e):
        if anomaly_flag.value:
            _set_anomaly_mode("flag")
        elif _anomaly_mode == "flag":
            anomaly_flag.value = True
            safe_update(anomaly_flag)

    def _on_anomaly_filter_change(e):
        if anomaly_filter.value:
            _set_anomaly_mode("filter")
        elif _anomaly_mode == "filter":
            anomaly_filter.value = True
            safe_update(anomaly_filter)

    def _on_anomaly_handle_change(e):
        if anomaly_handle.value:
            _set_anomaly_mode("handle")
        elif _anomaly_mode == "handle":
            anomaly_handle.value = True
            safe_update(anomaly_handle)

    anomaly_enabled.on_change = _on_anomaly_enabled_change
    anomaly_flag.on_change = _on_anomaly_flag_change
    anomaly_filter.on_change = _on_anomaly_filter_change
    anomaly_handle.on_change = _on_anomaly_handle_change

    # 初始状态：子开关跟随总开关
    anomaly_report.disabled = not anomaly_enabled.value
    anomaly_flag.disabled = not anomaly_enabled.value
    anomaly_filter.disabled = not anomaly_enabled.value
    anomaly_handle.disabled = not anomaly_enabled.value

    anomaly_panel = ft.Container(
        content=ft.Column([
            ft.Row([anomaly_enabled], spacing=8),
            ft.Container(
                content=ft.Column([
                    ft.Row([anomaly_report], spacing=8),
                    ft.Row([anomaly_flag, anomaly_filter, anomaly_handle], spacing=16),
                ], spacing=4),
                padding=ft.Padding.only(left=24),
            ),
        ], spacing=4),
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_SM,
        bgcolor=theme.SURFACE_HIGH,
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
                    ft.Row([prod_file_btn, prod_folder_btn, prod_auto_detect, prod_raw_start], spacing=8),
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
                theme.module_card([
                    ft.Row([maint_path, maint_btn], spacing=8),
                    ft.Row([maint_file_btn, maint_folder_btn, maint_split_year, maint_details_only], spacing=8),
                ]),
                anomaly_panel,
                ft.Row([match_eq_toggle, match_oil_toggle, skip_hidden_rows_toggle, skip_hidden_cols_toggle], spacing=8),
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
        "_skip_hidden_rows_toggle": skip_hidden_rows_toggle,
        "_skip_hidden_cols_toggle": skip_hidden_cols_toggle,
        "_anomaly_enabled": anomaly_enabled,
        "_anomaly_report": anomaly_report,
        "_anomaly_flag": anomaly_flag,
        "_anomaly_filter": anomaly_filter,
        "_anomaly_handle": anomaly_handle,
        "_anomaly_mode": lambda: _anomaly_mode,
        "fuel": {"path": fuel_path, "year": fuel_year, "btn": fuel_btn},
        "prod": {"path": prod_path, "raw_start": prod_raw_start, "btn": prod_btn, "auto_detect": prod_auto_detect},
        "elec": {"path": elec_path, "year": elec_year, "btn": elec_btn, "add_shift": elec_add_shift, "default_shift": elec_default_shift},
        "work": {"path": work_path, "year": work_year, "month": work_month, "header_toggle": _work_hmc.toggle, "header_mode": _work_hmc.mode, "header_fuzzy": _work_hmc.fuzzy, "btn": work_btn},
        "merge": {
            "path": merge_path,
            "keyword": merge_keyword,
            "strip_time": merge_strip_time,
            "btn": merge_btn,
            "sort_configs_state": sort_configs_state,
        },
        "maint": {"path": maint_path, "btn": maint_btn, "split_year": maint_split_year, "details_only": maint_details_only},
    }
    return container, module_refs
