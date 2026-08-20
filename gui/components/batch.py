"""批量处理模块区域组件"""
import contextlib
from datetime import datetime, timedelta

import flet as ft

from func.time_utils import local_now, local_today
from gui.i18n import t

from .common import (
    ChipToggle,
    HeaderModeConfig,
    _log_message,
    create_anomaly_controls,
    create_anomaly_results_table,
    make_browse_handler,
    month_options,
    to_local_dt,
    year_options,
)

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_batch_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建批量处理模块区域，返回 (container, batch_refs)"""

    current_date = local_now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)

    # --- 文件夹选择 ---
    batch_path = ft.TextField(
        label=t("components:batch.batchFolder"),
        hint_text=t("components:batch.selectfileprocessingExcelFilefilefolder"),
        expand=True,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:batch.browse"),
        ),
    )

    # --- 年份/月份 ---
    batch_year = ft.Dropdown(
        label=t("components:batch.year"),
        width=125,
        options=year_options(),
        value=current_year,
    )
    batch_month = ft.Dropdown(
        label=t("components:batch.month"),
        width=125,
        options=month_options(),
        value=current_month,
    )

    # --- 生产数据表头自动检测 ---
    batch_auto_detect = ft.Checkbox(
        label=t("components:batch.autoDetectHeader"),
        value=True,
        tooltip=t("components:batch.useAutomaticDetectionForTheProductionHeaderStartRow"),
    )

    # --- 表头起始行（仅在取消自动检测时显示） ---
    batch_raw_start = ft.TextField(
        label=t("components:batch.headerStartRow"),
        width=100,
        value="-1",
        hint_text=t("components:batch.1AutoDetect"),
        visible=False,
    )

    def _on_auto_detect_change(e):
        batch_raw_start.visible = not batch_auto_detect.value
        batch_raw_start.update()

    batch_auto_detect.on_change = _on_auto_detect_change

    # --- 合并输出 ---
    batch_merge = ft.Checkbox(
        label=t("components:batch.mergeOutput"),
        value=True,
        tooltip=t("components:batch.mergeAllProcessingResultsIntoASingleExcelFileSheetWithPrefix"),
    )

    # --- 台账匹配开关（设备 / 油品 独立控制） ---
    batch_match_eq = ft.Checkbox(
        label=t("components:batch.equipmentLedgerMatch"),
        value=True,
        tooltip=t("components:batch.automaticallyMatchTheEquipmentLedgerDuringBatchProcessing"),
    )
    batch_match_oil = ft.Checkbox(
        label=t("components:batch.oilLedgerMatch"),
        value=True,
        tooltip=t("components:batch.automaticallyMatchTheOilLedgerDuringBatchProcessing"),
    )
    batch_match_model = ft.Checkbox(
        label=t("components:batch.modelLedgerMatch"),
        value=False,
        tooltip=t("components:batch.requiresEquipmentLedgerMatchingFillModelAttributesUsingTheStandardEquipmentId"),
    )
    batch_skip_hidden_rows = ft.Checkbox(
        label=t("components:batch.skipHiddenRows"),
        value=False,
        tooltip=t("components:batch.whenSelectedExcelHiddenRowsAreNotRead"),
    )
    batch_skip_hidden_cols = ft.Checkbox(
        label=t("components:batch.skipHiddenColumns"),
        value=False,
        tooltip=t("components:batch.whenSelectedExcelHiddenColumnsAreNotRead"),
    )
    batch_filter_zero_hours = ft.Checkbox(
        label=t("components:batch.filterZeroEngineHours"),
        value=False,
        tooltip=t("components:batch.whenSelectedEngineHoursAre0ZeroOrEmptyRecordsAreFiltered"),
    )
    batch_filter_zero_work_hours = ft.Checkbox(
        label=t("components:batch.filterZeroOperatingHours"),
        value=False,
        tooltip=t("components:batch.hoursOperatingHourshours0OrEmptyhoursrecordshours"),
    )
    batch_filter_zero_hours_meter = ft.Checkbox(
        label=t("components:batch.filterZeroHoursMeter"),
        value=False,
        tooltip=t("components:batch.whenSelectedHourMeterStartOrEndIs0ZeroOrEmptyRecordsAreFiltered"),
    )
    batch_filter_zero_km_meter = ft.Checkbox(
        label=t("components:batch.filterZeroKilometerMeter"),
        value=False,
        tooltip=t("components:batch.whenSelectedOdometerStartOrEndIs0ZeroOrEmptyRecordsAreFiltered"),
    )
    batch_filter_zero_run_hours = ft.Checkbox(
        label=t("components:batch.filterZeroOperatingHours"),
        value=False,
        tooltip=t("components:batch.hoursOperatingHourshours0OrEmptyhoursrecordshours"),
    )
    batch_filter_zero_run_km = ft.Checkbox(
        label=t("components:batch.filterZeroOperatingDistance"),
        value=False,
        tooltip=t("components:batch.itemOperatingDistanceitem0OrEmptyitemrecordsitem"),
    )

    # --- 异常值检测 ---
    _anomaly = create_anomaly_controls()
    anomaly_results = create_anomaly_results_table()

    # --- 表内合并 ---
    batch_table_merge = ft.Checkbox(
        label=t("components:batch.mergeWithinSheet"),
        value=False,
        tooltip=t("components:batch.aggregateAllDataUsingALeftMergeIntoASingleSheetEnableLedgerMatchingFirst"),
        disabled=not (batch_match_eq.value or batch_match_oil.value or batch_match_model.value),
    )

    # ── 基准表芯片切换（表内合并专用） ──
    batch_base_table = ChipToggle(
        options=[("fuel", t("components:batch.fuelData")), ("worktime", t("components:batch.worktimeData"))],
    )
    batch_base_table.row.visible = batch_table_merge.value

    # --- 工作效率表头修改开关 ---
    _batch_hmc = HeaderModeConfig(
        label=t("components:batch.worktimeHeaderMapping"),
        tooltip=t("components:batch.whenEnabledRenameWorktimeReportHeadersUsingTheConfiguredMapping"),
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
            any_ledger = batch_match_eq.value or batch_match_oil.value or batch_match_model.value
            batch_table_merge.disabled = not any_ledger
        try:
            batch_table_merge.update()
            batch_base_table.row.update()
        except (RuntimeError, AttributeError):
            pass

    batch_merge.on_change = _on_merge_change

    def _on_ledger_toggle_for_merge(e):
        any_ledger = batch_match_eq.value or batch_match_oil.value or batch_match_model.value
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
    batch_match_model.on_change = _on_ledger_toggle_for_merge

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
        label=t("components:batch.filterByDate"),
        value=False,
        tooltip=t("components:batch.whenEnabledKeepOnlyDataForTheSelectedDate"),
    )

    def _update_date_display():
        _date_display_text.value = _selected_date[0].strftime("%Y-%m-%d")
        with contextlib.suppress(RuntimeError, AttributeError):
            _date_display_text.update()

    def _on_prev_day(e):
        _selected_date[0] = _selected_date[0] - timedelta(days=1)
        _update_date_display()

    def _on_today(e):
        _selected_date[0] = local_today()
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
    batch_btn = theme.primary_btn(t("components:batch.batchProcessing"), icon=ft.Icons.BOLT, disabled=False)

    # --- 进度区 ---
    batch_progress_bar = ft.ProgressBar(value=0.0, visible=False)
    batch_progress_text = ft.Text(value="", size=12, color=theme.TEXT_SECONDARY, visible=False)
    batch_cancel_btn = theme.secondary_btn(t("components:batch.cancel"), icon=ft.Icons.CANCEL, visible=False, height=32)

    # --- 浏览按钮 ---
    _batch_picker = ft.FilePicker()
    page.services.append(_batch_picker)
    on_batch_browse = make_browse_handler(
        _batch_picker, batch_path, batch_btn, t("components:batch.selectBatchProcessingFolder"),
        mode="folder",
        log_fn=lambda msg: _log_message(page.logger.error, msg),
    )

    batch_path.suffix.on_click = on_batch_browse

    # --- 日期筛选行可见性 ---
    date_nav_row = ft.Row(
        [
            date_display,
            theme.secondary_btn(t("components:batch.previousDay"), icon=ft.Icons.ARROW_BACK_IOS, on_click=_on_prev_day, height=32),
            theme.secondary_btn(t("components:batch.today"), icon=ft.Icons.CALENDAR_TODAY, on_click=_on_today, height=32),
            theme.secondary_btn(t("components:batch.selectDate"), icon=ft.Icons.CALENDAR_MONTH, on_click=_on_pick_date, height=32),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=date_filter_toggle.value,
    )

    def _on_date_filter_toggle(e):
        date_nav_row.visible = date_filter_toggle.value
        with contextlib.suppress(RuntimeError, AttributeError):
            date_nav_row.update()

    date_filter_toggle.on_change = _on_date_filter_toggle

    # --- 布局 ---
    options_grid = ft.ResponsiveRow(
        [
            ft.Container(ft.Row([batch_auto_detect, batch_raw_start], spacing=4), col={"xs": 12, "md": 6}),
            ft.Container(_batch_hmc.toggle, col={"xs": 12, "md": 6}),
            ft.Container(
                _batch_hmc.mode.row,
                col={"xs": 12, "md": 6},
            ),
        ],
        run_spacing=4,
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    output_grid = ft.ResponsiveRow(
        [
            ft.Container(batch_merge, col={"xs": 12, "md": 6}),
            ft.Container(batch_table_merge, col={"xs": 12, "md": 6}),
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

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title(t("components:batch.batchProcessing")),
                ft.Text(
                    t("components:batch.selectAFolderToScanAndProcessReportFilesResultsCanBeMergedOrExportedSeparately"),
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),

                # ── 文件夹 + 日期 ──
                theme.module_card([
                    ft.Row([batch_path], spacing=8),
                    ft.Row(
                        [batch_year, batch_month, date_filter_toggle],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    date_nav_row,
                ], label=t("components:batch.targetFolder")),

                # ── 处理参数 ──
                theme.module_card([
                    options_grid,
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Text(t("components:batch.dataOptions"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                    ft.ResponsiveRow(
                        [
                            ft.Container(batch_match_eq, col={"xs": 6}),
                            ft.Container(batch_match_oil, col={"xs": 6}),
                            ft.Container(batch_match_model, col={"xs": 6}),
                            ft.Container(batch_skip_hidden_rows, col={"xs": 6}),
                            ft.Container(batch_skip_hidden_cols, col={"xs": 6}),
                        ],
                        run_spacing=4,
                    ),
                ], label=t("components:batch.processingParameters")),

                # ── 数据过滤 ──
                theme.module_card([
                    ft.Text(t("components:batch.fuelProcessing"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                    ft.ResponsiveRow(
                        [
                            ft.Container(batch_filter_zero_hours, col={"xs": 6}),
                            ft.Container(batch_filter_zero_work_hours, col={"xs": 6}),
                        ],
                        run_spacing=4,
                    ),
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Text(t("components:batch.productionData"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                    ft.ResponsiveRow(
                        [
                            ft.Container(batch_filter_zero_hours_meter, col={"xs": 6}),
                            ft.Container(batch_filter_zero_km_meter, col={"xs": 6}),
                            ft.Container(batch_filter_zero_run_hours, col={"xs": 6}),
                            ft.Container(batch_filter_zero_run_km, col={"xs": 6}),
                        ],
                        run_spacing=4,
                    ),
                ], label=t("components:batch.dataFilters")),

                # ── 输出方式 ──
                theme.module_card([
                    output_grid,
                ], label=t("components:batch.outputMode")),

                # ── 异常值检测 ──
                theme.module_card([
                    _anomaly["container"],
                ], label=t("components:batch.anomalyDetection")),

                # ── 进度 + 操作 ──
                progress_row,
                ft.Row(
                    [batch_btn],
                    alignment=ft.MainAxisAlignment.END,
                ),
                anomaly_results["container"],
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
        "match_model_toggle": batch_match_model,
        "_skip_hidden_rows_toggle": batch_skip_hidden_rows,
        "_skip_hidden_cols_toggle": batch_skip_hidden_cols,
        "_filter_zero_hours_toggle": batch_filter_zero_hours,
        "_filter_zero_work_hours_toggle": batch_filter_zero_work_hours,
        "_filter_zero_hours_meter_toggle": batch_filter_zero_hours_meter,
        "_filter_zero_km_meter_toggle": batch_filter_zero_km_meter,
        "_filter_zero_run_hours_toggle": batch_filter_zero_run_hours,
        "_filter_zero_run_km_toggle": batch_filter_zero_run_km,
        "_anomaly_enabled": _anomaly["_anomaly_enabled"],
        "_anomaly_report": _anomaly["_anomaly_report"],
        "_anomaly_mode": _anomaly["_anomaly_mode"],
        "anomaly_results": anomaly_results,
        "header_toggle": _batch_hmc.toggle,
        "header_mode": _batch_hmc.mode,
                "date_filter_toggle": date_filter_toggle,
        "selected_date": _selected_date,
        "btn": batch_btn,
        "progress_bar": batch_progress_bar,
        "progress_text": batch_progress_text,
        "cancel_btn": batch_cancel_btn,
        "progress_row": progress_row,
    }

    return container, batch_refs
