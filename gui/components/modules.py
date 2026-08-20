"""数据处理模块区域组件"""
import flet as ft

from func.time_utils import local_now
from gui.i18n import t

from .common import (
    HeaderModeConfig,
    _log_message,
    create_anomaly_controls,
    create_anomaly_results_table,
    make_browse_handler,
    month_options,
    safe_update,
    year_options,
)
from .types import ModuleRefs

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
        label=t("components:modules.fuelProcessing"),
        hint_text=t("components:modules.enterAPathOrUseTheBrowseButton"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.browse"),
        ),
    )
    fuel_year = ft.Dropdown(
        label=t("components:modules.year"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    fuel_btn = theme.primary_btn(t("components:modules.process"), icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Tire life ---
    tire_path = ft.TextField(
        label=t("components:modules.tireProcessing"),
        hint_text=t("components:modules.enterAPathOrUseTheBrowseButton"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.browse"),
        ),
    )
    tire_btn = theme.primary_btn(
        t("components:modules.process"),
        icon=ft.Icons.PLAY_ARROW,
        disabled=False,
    )

    # --- Production ---
    prod_path = ft.TextField(
        label=t("components:modules.productionProcessing"),
        hint_text=t("components:modules.enterAPathOrUseTheBrowseButton"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
    )
    prod_file_btn = theme.secondary_btn(t("components:modules.file"), icon=ft.Icons.UPLOAD_FILE)
    prod_folder_btn = theme.secondary_btn(t("components:modules.folder"), icon=ft.Icons.FOLDER_OPEN)
    prod_raw_start = ft.TextField(
        label=t("components:modules.headerStartRow"),
        width=100,
        value="6",
        hint_text="6",
        color=theme.TEXT_PRIMARY,
        disabled=True,
    )
    prod_auto_detect = ft.Switch(
        label=t("components:modules.autoDetectHeader"),
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
    prod_btn = theme.primary_btn(t("components:modules.process"), icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- 生产处理汇总区域 ---
    prod_summary_container = ft.Column(
        spacing=4,
        visible=False,
    )

    # --- Electrical ---
    elec_path = ft.TextField(
        label=t("components:modules.electricalProcessing"),
        hint_text=t("components:modules.enterAPathOrUseTheBrowseButton"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.browse"),
        ),
    )
    elec_year = ft.Dropdown(
        label=t("components:modules.year"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    elec_btn = theme.primary_btn(t("components:modules.process"), icon=ft.Icons.PLAY_ARROW, disabled=False)
    elec_add_shift = ft.Checkbox(
        label=t("components:modules.addShiftColumn"),
        value=False,
        tooltip=t("components:modules.addShiftColumnAfterDate"),
    )
    elec_default_shift = ft.Dropdown(
        label=t("components:modules.defaultShift"),
        width=100,
        options=[
            ft.dropdown.Option("Day", t("common:dayShift")),
            ft.dropdown.Option("Night", t("common:nightShift")),
        ],
        value="Day",
        visible=False,
    )

    def _on_shift_toggle(e):
        elec_default_shift.visible = elec_add_shift.value
        elec_default_shift.update()

    elec_add_shift.on_change = _on_shift_toggle

    # --- Work time ---
    work_path = ft.TextField(
        label=t("components:modules.worktimeProcessing"),
        hint_text=t("components:modules.enterAPathOrUseTheBrowseButton"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.browse"),
        ),
    )
    work_year = ft.Dropdown(
        label=t("components:modules.year"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    work_month = ft.Dropdown(
        label=t("components:modules.month"),
        width=125,
        options=month_options(),
        value=current_month,
    )
    _work_hmc = HeaderModeConfig(
        label=t("components:modules.headerMapping"),
        tooltip=t("components:modules.whenEnabledRenameOutputHeadersUsingTheConfiguredMapping"),
    )

    work_btn = theme.primary_btn(t("components:modules.process"), icon=ft.Icons.PLAY_ARROW, disabled=False)

    # --- Excel Merger ---
    merge_path = ft.TextField(
        label=t("components:modules.excelMerge"),
        hint_text=t("components:modules.enterAPathOrUseTheBrowseButton"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:modules.browse"),
        ),
    )
    merge_keyword = ft.TextField(
        label=t("components:modules.keyword"),
        hint_text=t("components:modules.itemFuel"),
        expand=True,
        color=theme.TEXT_PRIMARY,
    )
    merge_strip_time = ft.Checkbox(
        label=t("components:modules.dateOnly"),
        value=False,
        tooltip=t("components:modules.columnColumnColumnYyyyMmDd"),
    )
    merge_tolerant_header = ft.Checkbox(
        label=t("components:modules.compatibleHeaders"),
        value=False,
        tooltip=t("components:modules.columnColumnfilecolumnColumn"),
    )
    merge_dedup = ft.Checkbox(
        label=t("components:modules.removeDuplicateRecords"),
        value=False,
        tooltip=t("components:modules.itemItemItemrecords"),
    )
    merge_btn = theme.primary_btn(t("components:modules.merge"), icon=ft.Icons.MERGE_TYPE, disabled=False)

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
                hint_text=t("components:modules.columnName"),
                expand=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
            )
            order_dropdown = ft.Dropdown(
                value=t("components:modules.asc") if cfg.get("ascending", True) else t("components:modules.desc"),
                options=[ft.dropdown.Option(t("components:modules.asc")), ft.dropdown.Option(t("components:modules.desc"))],
                width=90,
                text_size=12,
            )

            def on_col_change(e, _idx=idx):
                sort_configs_state[_idx]["column"] = e.control.value

            def on_order_select(e, _idx=idx):
                sort_configs_state[_idx]["ascending"] = (e.control.value == t("components:modules.asc"))

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
                icon=ft.Icons.ARROW_UPWARD, tooltip=t("components:modules.moveUp"), on_click=move_up, icon_size=16
            )
            down_btn = ft.IconButton(
                icon=ft.Icons.ARROW_DOWNWARD, tooltip=t("components:modules.moveDown"), on_click=move_down, icon_size=16
            )
            del_btn = ft.IconButton(
                icon=ft.Icons.DELETE, tooltip=t("components:modules.delete"), on_click=remove_row, icon_size=16
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

    add_sort_btn = theme.secondary_btn(t("components:modules.addSortRule"), icon=ft.Icons.ADD, on_click=add_sort_config, height=36)

    # --- Maintenance ---
    maint_path = ft.TextField(
        label=t("components:modules.maintenanceRecords"),
        hint_text=t("components:modules.selectAttendanceReportFileOrFolder"),
        expand=2,
        read_only=False,
        color=theme.TEXT_PRIMARY,
    )
    maint_file_btn = theme.secondary_btn(t("components:modules.file"), icon=ft.Icons.UPLOAD_FILE)
    maint_folder_btn = theme.secondary_btn(t("components:modules.folder"), icon=ft.Icons.FOLDER_OPEN)
    maint_btn = theme.primary_btn(t("components:modules.process"), icon=ft.Icons.PLAY_ARROW, disabled=False)
    maint_split_year = ft.Checkbox(
        label=t("components:modules.splitByYear"),
        value=False,
        tooltip=t("components:modules.fileFilefile"),
    )
    maint_details_only = ft.Checkbox(
        label=t("components:modules.detailsOnly"),
        value=False,
        tooltip=t("components:modules.itemoutputmaintenanceDetailsSheetItemFileitemItem"),
    )
    maint_use_ml = ft.Checkbox(
        label=t("components:modules.enableMlAssistedClassification"),
        value=True,
        tooltip=t("components:modules.mlFallbackHint"),
    )

    # --- FilePicker instances (must be added to page.overlay to work repeatedly) ---
    _fuel_picker = ft.FilePicker()
    _tire_picker = ft.FilePicker()
    _prod_file_picker = ft.FilePicker()
    _prod_folder_picker = ft.FilePicker()
    _elec_picker = ft.FilePicker()
    _work_picker = ft.FilePicker()
    _merge_picker = ft.FilePicker()
    _maint_file_picker = ft.FilePicker()
    _maint_folder_picker = ft.FilePicker()
    page.services.extend([
        _fuel_picker, _tire_picker, _prod_file_picker, _prod_folder_picker,
        _elec_picker, _work_picker, _merge_picker,
        _maint_file_picker, _maint_folder_picker,
    ])

    on_fuel_browse = make_browse_handler(
        _fuel_picker, fuel_path, fuel_btn, t("components:modules.selectFuelDataFile"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_tire_browse = make_browse_handler(
        _tire_picker,
        tire_path,
        tire_btn,
        t("components:modules.selectTireDataFile"),
        extensions=["xlsx"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_prod_pick_file = make_browse_handler(
        _prod_file_picker, prod_path, prod_btn, t("components:modules.selectProductionDataFile"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_prod_pick_folder = make_browse_handler(
        _prod_folder_picker, prod_path, prod_btn, t("components:modules.selectfiledatafolder"),
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_elec_browse = make_browse_handler(
        _elec_picker, elec_path, elec_btn, t("components:modules.selectElectricalDataFile"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_work_browse = make_browse_handler(
        _work_picker, work_path, work_btn, t("components:modules.selectWorktimeFileOrFolder"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_merge_browse = make_browse_handler(
        _merge_picker, merge_path, merge_btn, t("components:modules.selectfileExcelFilefilefolder"),
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_maint_pick_file = make_browse_handler(
        _maint_file_picker, maint_path, maint_btn, t("components:modules.selectfilefile"),
        extensions=["xlsx", "xls"],
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )
    on_maint_pick_folder = make_browse_handler(
        _maint_folder_picker, maint_path, maint_btn, t("components:modules.selectfilefolder"),
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )

    # 绑定浏览按钮
    fuel_path.suffix.on_click = on_fuel_browse
    tire_path.suffix.on_click = on_tire_browse
    prod_file_btn.on_click = on_prod_pick_file
    prod_folder_btn.on_click = on_prod_pick_folder
    elec_path.suffix.on_click = on_elec_browse
    work_path.suffix.on_click = on_work_browse
    merge_path.suffix.on_click = on_merge_browse
    maint_file_btn.on_click = on_maint_pick_file
    maint_folder_btn.on_click = on_maint_pick_folder

    # --- 台账匹配开关（设备 / 油品 独立控制） ---
    match_eq_toggle = ft.Checkbox(
        label=t("components:modules.equipmentLedgerMatch"),
        value=False,
    )
    match_oil_toggle = ft.Checkbox(
        label=t("components:modules.oilLedgerMatch"),
        value=False,
    )
    match_model_toggle = ft.Checkbox(
        label=t("components:modules.modelLedgerMatch"),
        value=False,
        tooltip=t("components:modules.requiresEquipmentLedgerMatchingFillModelAttributesUsingTheStandardEquipmentId"),
    )
    skip_hidden_rows_toggle = ft.Checkbox(
        label=t("components:modules.skipHiddenRows"),
        value=False,
        tooltip=t("components:modules.whenSelectedExcelHiddenRowsAreNotRead"),
    )
    skip_hidden_cols_toggle = ft.Checkbox(
        label=t("components:modules.skipHiddenColumns"),
        value=False,
        tooltip=t("components:modules.whenSelectedExcelHiddenColumnsAreNotRead"),
    )
    filter_zero_hours_toggle = ft.Checkbox(
        label=t("components:modules.filterZeroEngineHours"),
        value=False,
        tooltip=t("components:modules.whenSelectedEngineHoursAre0ZeroOrEmptyRecordsAreFiltered"),
    )
    filter_zero_work_hours_toggle = ft.Checkbox(
        label=t("components:modules.filterZeroOperatingHours"),
        value=False,
        tooltip=t("components:modules.hoursOperatingHourshours0OrEmptyhoursrecordshours"),
    )

    # --- 生产模块过滤开关 ---
    prod_filter_zero_hours_meter = ft.Checkbox(
        label=t("components:modules.filterZeroHoursMeter"),
        value=False,
        tooltip=t("components:modules.whenSelectedHourMeterStartOrEndIs0ZeroOrEmptyRecordsAreFiltered"),
    )
    prod_filter_zero_km_meter = ft.Checkbox(
        label=t("components:modules.filterZeroKilometerMeter"),
        value=False,
        tooltip=t("components:modules.whenSelectedOdometerStartOrEndIs0ZeroOrEmptyRecordsAreFiltered"),
    )
    prod_filter_zero_run_hours = ft.Checkbox(
        label=t("components:modules.filterZeroOperatingHours"),
        value=False,
        tooltip=t("components:modules.hoursOperatingHourshours0OrEmptyhoursrecordshours"),
    )
    prod_filter_zero_run_km = ft.Checkbox(
        label=t("components:modules.filterZeroOperatingDistance"),
        value=False,
        tooltip=t("components:modules.itemOperatingDistanceitem0OrEmptyitemrecordsitem"),
    )

    # --- 异常值检测开关（使用共享工厂） ---
    anomaly_ctrls = create_anomaly_controls()
    anomaly_panel = anomaly_ctrls["container"]
    anomaly_results = create_anomaly_results_table()

    header_hint = ft.Row(
        [
            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=theme.TEXT_SECONDARY),
            ft.Text(t("components:modules.editMappingRulesInUserConfigWorktimeHeaderMapping"), size=11, color=theme.TEXT_SECONDARY),
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
                theme.section_title(t("components:modules.dataProcessing")),
                ft.Text(
                    t("components:modules.selectADataFileOrFolderThenClickProcessEachModuleRunsIndependently"),
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
                    ft.Text(t("components:modules.configurationconfigurationConfigurationConfigurationitemsconfiguration"), size=12,
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
                theme.module_card([
                    ft.Row([tire_path, tire_btn], spacing=8),
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
        "tire": {"path": tire_path, "btn": tire_btn},
    }
    return container, module_refs
