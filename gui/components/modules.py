"""数据处理模块区域组件"""
import flet as ft

from .common import (
    _last_directory, _update_last_directory, _log_message, _get_initial_directory,
    _show_path_confirm, ChipToggle, year_options, month_options,
    make_browse_handler, HeaderModeConfig, safe_update, create_anomaly_controls,
    create_anomaly_results_table,
)
from .types import ModuleRefs
from func.time_utils import local_now
from gui.i18n import t

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_modules_section(page: ft.Page) -> tuple[ft.Container, "ModuleRefs"]:
    """创建数据处理模块区域，返回 (container, module_refs)"""

    current_date = local_now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)

    # --- Fuel ---
    fuel_path = ft.TextField(
        label=t("components:modules.燃油数据处理_8744"),
        hint_text=t("components:modules.输入路径或点击按钮选择..._d300"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.浏览_9c5c"),
        ),
    )
    fuel_year = ft.Dropdown(
        label=t("components:modules.年份_8f30"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    fuel_btn = theme.primary_btn(t("components:modules.处理_7b1d"), icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Production ---
    prod_path = ft.TextField(
        label=t("components:modules.生产数据处理_ea37"),
        hint_text=t("components:modules.输入路径或点击按钮选择..._d300"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
    )
    prod_file_btn = theme.secondary_btn(t("components:modules.选文件_ef59"), icon=ft.Icons.UPLOAD_FILE)
    prod_folder_btn = theme.secondary_btn(t("components:modules.选文件夹_2f6e"), icon=ft.Icons.FOLDER_OPEN)
    prod_raw_start = ft.TextField(
        label=t("components:modules.表头起始行_7c63"),
        width=100,
        value="6",
        hint_text="6",
        color=theme.TEXT_PRIMARY,
        disabled=True,
    )
    prod_auto_detect = ft.Switch(
        label=t("components:modules.自动识别表头_515c"),
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
    prod_btn = theme.primary_btn(t("components:modules.处理_7b1d"), icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- 生产处理汇总区域 ---
    prod_summary_container = ft.Column(
        spacing=4,
        visible=False,
    )

    # --- Electrical ---
    elec_path = ft.TextField(
        label=t("components:modules.电力数据处理_0a6f"),
        hint_text=t("components:modules.输入路径或点击按钮选择..._d300"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.浏览_9c5c"),
        ),
    )
    elec_year = ft.Dropdown(
        label=t("components:modules.年份_8f30"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    elec_btn = theme.primary_btn(t("components:modules.处理_7b1d"), icon=ft.Icons.PLAY_ARROW, disabled=False)
    elec_add_shift = ft.Checkbox(
        label=t("components:modules.添加班次列_2612"),
        value=False,
        tooltip=t("components:modules.在日期列右侧新增班次列_b6ce"),
    )
    elec_default_shift = ft.Dropdown(
        label=t("components:modules.默认班次_d68b"),
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
        label=t("components:modules.工时数据处理_f56b"),
        hint_text=t("components:modules.输入路径或点击按钮选择..._d300"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.浏览_9c5c"),
        ),
    )
    work_year = ft.Dropdown(
        label=t("components:modules.年份_8f30"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    work_month = ft.Dropdown(
        label=t("components:modules.月份_8190"),
        width=125,
        options=month_options(),
        value=current_month,
    )
    _work_hmc = HeaderModeConfig(
        label=t("components:modules.表头修改_6f3e"),
        tooltip=t("components:modules.开启后按配置的映射关系重命名输_539a"),
    )

    work_btn = theme.primary_btn(t("components:modules.处理_7b1d"), icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Excel Merger ---
    merge_path = ft.TextField(
        label=t("components:modules.Excel合并_bbe4"),
        hint_text=t("components:modules.输入路径或点击按钮选择..._d300"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.浏览_9c5c"),
        ),
    )
    merge_keyword = ft.TextField(
        label=t("components:modules.关键字_cfb5"),
        hint_text=t("components:modules.例如:Fuel_8734"),
        expand=True,
        color=theme.TEXT_PRIMARY,
    )
    merge_strip_time = ft.Checkbox(
        label=t("components:modules.仅保留日期_b960"),
        value=False,
        tooltip=t("components:modules.勾选后，时间列将去除时分秒，格_88e2"),
    )
    merge_tolerant_header = ft.Checkbox(
        label=t("components:modules.兼容表头_3795"),
        value=False,
        tooltip=t("components:modules.勾选后，表头不一致的文件也会合_4a49"),
    )
    merge_dedup = ft.Checkbox(
        label=t("components:modules.去除重复记录_6f2d"),
        value=False,
        tooltip=t("components:modules.勾选后，合并结果中完全重复的行_2e26"),
    )
    merge_btn = theme.primary_btn(t("components:modules.合并_bd81"), icon=ft.Icons.MERGE_TYPE, disabled=False)

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
                hint_text=t("components:modules.列名_8f98"),
                expand=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
            )
            order_dropdown = ft.Dropdown(
                value=t("components:modules.升序_a4ac") if cfg.get("ascending", True) else t("components:modules.降序_d05d"),
                options=[ft.dropdown.Option(t("components:modules.升序_a4ac")), ft.dropdown.Option(t("components:modules.降序_d05d"))],
                width=90,
                text_size=12,
            )

            def on_col_change(e, _idx=idx):
                sort_configs_state[_idx]["column"] = e.control.value

            def on_order_select(e, _idx=idx):
                sort_configs_state[_idx]["ascending"] = (e.control.value == t("components:modules.升序_a4ac"))

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
                icon=ft.Icons.ARROW_UPWARD, tooltip=t("components:modules.上移_315e"), on_click=move_up, icon_size=16
            )
            down_btn = ft.IconButton(
                icon=ft.Icons.ARROW_DOWNWARD, tooltip=t("components:modules.下移_17ac"), on_click=move_down, icon_size=16
            )
            del_btn = ft.IconButton(
                icon=ft.Icons.DELETE, tooltip=t("components:modules.删除_2f4a"), on_click=remove_row, icon_size=16
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

    add_sort_btn = theme.secondary_btn(t("components:modules.添加排序条件_9336"), icon=ft.Icons.ADD, on_click=add_sort_config, height=36)

    # --- Maintenance ---
    maint_path = ft.TextField(
        label=t("components:modules.维修记录处理_7e96"),
        hint_text=t("components:modules.选择出勤统计表文件或文件夹.._cdbd"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
    )
    maint_file_btn = theme.secondary_btn(t("components:modules.选文件_ef59"), icon=ft.Icons.UPLOAD_FILE)
    maint_folder_btn = theme.secondary_btn(t("components:modules.选文件夹_2f6e"), icon=ft.Icons.FOLDER_OPEN)
    maint_btn = theme.primary_btn(t("components:modules.处理_7b1d"), icon=ft.Icons.PLAY_ARROW, disabled=False)
    maint_split_year = ft.Checkbox(
        label=t("components:modules.按年份拆分输出_0709"),
        value=False,
        tooltip=t("components:modules.勾选后，每年生成独立的统计文件_c64a"),
    )
    maint_details_only = ft.Checkbox(
        label=t("components:modules.仅导出明细_02b8"),
        value=False,
        tooltip=t("components:modules.勾选后只输出维修明细sheet_a420"),
    )
    maint_use_ml = ft.Checkbox(
        label=t("components:modules.启用机器学习辅助识别_0cea"),
        value=True,
        tooltip=t("components:modules.仅对规则仍判为'其他/待确认'_47d8"),
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
        _fuel_picker, fuel_path, fuel_btn, t("components:modules.选择燃油数据文件_5fbd"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_prod_pick_file = make_browse_handler(
        _prod_file_picker, prod_path, prod_btn, t("components:modules.选择生产数据文件_51cb"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_prod_pick_folder = make_browse_handler(
        _prod_folder_picker, prod_path, prod_btn, t("components:modules.选择生产数据文件夹_3b6e"),
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_elec_browse = make_browse_handler(
        _elec_picker, elec_path, elec_btn, t("components:modules.选择电力数据文件_dcf4"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_work_browse = make_browse_handler(
        _work_picker, work_path, work_btn, t("components:modules.选择工时数据文件或文件夹_9fd1"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_merge_browse = make_browse_handler(
        _merge_picker, merge_path, merge_btn, t("components:modules.选择包含Excel文件的文件夹_6903"),
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_maint_pick_file = make_browse_handler(
        _maint_file_picker, maint_path, maint_btn, t("components:modules.选择出勤统计表文件_804e"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_maint_pick_folder = make_browse_handler(
        _maint_folder_picker, maint_path, maint_btn, t("components:modules.选择出勤统计表文件夹_2119"),
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
        label=t("components:modules.设备台账匹配_5a23"),
        value=False,
    )
    match_oil_toggle = ft.Checkbox(
        label=t("components:modules.油品台账匹配_8663"),
        value=False,
    )
    match_model_toggle = ft.Checkbox(
        label=t("components:modules.型号台账匹配_135c"),
        value=False,
        tooltip=t("components:modules.需同时开启设备台账匹配，按标准_6668"),
    )
    skip_hidden_rows_toggle = ft.Checkbox(
        label=t("components:modules.跳过隐藏行_bc25"),
        value=False,
        tooltip=t("components:modules.勾选后，Excel中被隐藏的行_ecd7"),
    )
    skip_hidden_cols_toggle = ft.Checkbox(
        label=t("components:modules.跳过隐藏列_3ed3"),
        value=False,
        tooltip=t("components:modules.勾选后，Excel中被隐藏的列_398b"),
    )
    filter_zero_hours_toggle = ft.Checkbox(
        label=t("components:modules.过滤零小时数_549f"),
        value=False,
        tooltip=t("components:modules.勾选后，发动机小时数为0或为空_78cd"),
    )
    filter_zero_work_hours_toggle = ft.Checkbox(
        label=t("components:modules.过滤零运行小时数_eaf1"),
        value=False,
        tooltip=t("components:modules.勾选后，运行小时数为0或为空的_c4ff"),
    )

    # --- 生产模块过滤开关 ---
    prod_filter_zero_hours_meter = ft.Checkbox(
        label=t("components:modules.过滤零小时仪表_99e8"),
        value=False,
        tooltip=t("components:modules.勾选后，小时数仪表开始或结束为_3b68"),
    )
    prod_filter_zero_km_meter = ft.Checkbox(
        label=t("components:modules.过滤零公里仪表_2e3c"),
        value=False,
        tooltip=t("components:modules.勾选后，公里数仪表开始或结束为_1e34"),
    )
    prod_filter_zero_run_hours = ft.Checkbox(
        label=t("components:modules.过滤零运行小时数_eaf1"),
        value=False,
        tooltip=t("components:modules.勾选后，运行小时数为0或为空的_c4ff"),
    )
    prod_filter_zero_run_km = ft.Checkbox(
        label=t("components:modules.过滤零运行里程_d55d"),
        value=False,
        tooltip=t("components:modules.勾选后，运行里程为0或为空的记_3be2"),
    )

    # --- 异常值检测开关（使用共享工厂） ---
    anomaly_ctrls = create_anomaly_controls()
    anomaly_panel = anomaly_ctrls["container"]
    anomaly_results = create_anomaly_results_table()

    header_hint = ft.Row(
        [
            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=theme.TEXT_SECONDARY),
            ft.Text(t("components:modules.映射规则可在「用户配置→工作效_e843"), size=11, color=theme.TEXT_SECONDARY),
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
                theme.section_title(t("components:modules.数据处理模块_89fa")),
                ft.Text(
                    t("components:modules.选择数据文件或文件夹后点击处理_5fea"),
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),
                theme.module_card([
                    ft.Row([fuel_path, fuel_year, fuel_btn], spacing=8),
                    ft.Row([filter_zero_hours_toggle, filter_zero_work_hours_toggle], spacing=8),
                ]),
                theme.module_card([
                    ft.Row([prod_path, prod_btn], spacing=8),
                    ft.Row([prod_file_btn, prod_folder_btn, prod_auto_detect, prod_raw_start], spacing=8),
                    ft.Row([prod_filter_zero_hours_meter, prod_filter_zero_km_meter,
                            prod_filter_zero_run_hours, prod_filter_zero_run_km], spacing=8),
                    prod_summary_container,
                ]),
                theme.module_card([
                    ft.Row([elec_path, elec_year, elec_add_shift, elec_default_shift, elec_btn], spacing=8),
                ]),
                theme.module_card([
                    ft.Row([work_path, work_year, work_month, work_btn], spacing=6),
                    ft.Row(
                        [_work_hmc.toggle, _work_hmc.mode.row],
                        spacing=theme.SPACING_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    header_hint,
                ]),
                theme.module_card([
                    ft.Row([merge_path, merge_btn], spacing=8),
                    ft.Row([merge_keyword], spacing=8),
                    ft.Row([merge_strip_time, merge_tolerant_header, merge_dedup], spacing=8,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(t("components:modules.排序配置（可选，留空则自动按第_1d9b"), size=12,
                            color=theme.TEXT_SECONDARY),
                    ft.Row([sort_rules_column, add_sort_btn], spacing=8,
                           alignment=ft.MainAxisAlignment.START),
                ], spacing=4),
                theme.module_card([
                    maint_path,
                    ft.Row(
                        [maint_file_btn, maint_folder_btn, maint_btn],
                        spacing=8,
                    ),
                    ft.Row(
                        [maint_split_year, maint_details_only, maint_use_ml],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ]),
                anomaly_panel,
                ft.Row([match_eq_toggle, match_oil_toggle, match_model_toggle,
                        skip_hidden_rows_toggle, skip_hidden_cols_toggle], spacing=8),
                anomaly_results["container"],
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
        "_match_model_toggle": match_model_toggle,
        "_skip_hidden_rows_toggle": skip_hidden_rows_toggle,
        "_skip_hidden_cols_toggle": skip_hidden_cols_toggle,
        "_anomaly_enabled": anomaly_ctrls["_anomaly_enabled"],
        "_anomaly_report": anomaly_ctrls["_anomaly_report"],
        "_anomaly_mode": anomaly_ctrls["_anomaly_mode"],
        "anomaly_results": anomaly_results,
        "fuel": {"path": fuel_path, "year": fuel_year, "btn": fuel_btn, "_filter_zero_hours_toggle": filter_zero_hours_toggle, "_filter_zero_work_hours_toggle": filter_zero_work_hours_toggle},
        "prod": {"path": prod_path, "raw_start": prod_raw_start, "btn": prod_btn, "auto_detect": prod_auto_detect, "summary_container": prod_summary_container,
                 "_filter_zero_hours_meter_toggle": prod_filter_zero_hours_meter, "_filter_zero_km_meter_toggle": prod_filter_zero_km_meter,
                 "_filter_zero_run_hours_toggle": prod_filter_zero_run_hours, "_filter_zero_run_km_toggle": prod_filter_zero_run_km},
        "elec": {"path": elec_path, "year": elec_year, "btn": elec_btn, "add_shift": elec_add_shift, "default_shift": elec_default_shift},
        "work": {"path": work_path, "year": work_year, "month": work_month, "header_toggle": _work_hmc.toggle, "header_mode": _work_hmc.mode, "btn": work_btn},
        "merge": {
            "path": merge_path,
            "keyword": merge_keyword,
            "strip_time": merge_strip_time,
            "tolerant_header": merge_tolerant_header,
            "dedup": merge_dedup,
            "btn": merge_btn,
            "sort_configs_state": sort_configs_state,
        },
        "maint": {
            "path": maint_path,
            "btn": maint_btn,
            "split_year": maint_split_year,
            "details_only": maint_details_only,
            "use_ml": maint_use_ml,
        },
    }
    return container, module_refs
