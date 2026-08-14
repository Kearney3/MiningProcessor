"""MineBase 数据同步区域组件"""
from datetime import date, datetime, timedelta

import flet as ft

from func.config_loader import get_minebase_mode

from .common import (
    _get_initial_directory,
    _last_directory,
    _show_path_confirm,
    _update_last_directory,
    ChipToggle,
    HeaderModeConfig,
    create_anomaly_controls,
    to_local_dt,
    year_options,
    month_options,
)
from func.time_utils import local_today
from gui.i18n import t

try:
    from . import theme
except ImportError:
    import gui.theme as theme


# 数据类型定义（委托给共享常量模块）
from func.data_types import SYNC_DATA_TYPES as DATA_TYPES

# 年份/月份选项（委托给共享工具函数）
_YEAR_OPTIONS = year_options(-30, 30)
_MONTH_OPTIONS = month_options()


def create_sync_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建 MineBase 数据同步区域，返回 (container, refs_dict)"""

    # --- 目录路径 ---
    sync_path = ft.TextField(
        label=t("components:sync_minebase.输出目录_0d81"),
        hint_text=t("components:sync_minebase.选择MiningProcess_3a7d"),
        expand=True,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        value=_get_initial_directory(),
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip=t("components:sync_minebase.浏览_9c5c"),
        ),
    )

    _browse_picker = ft.FilePicker()
    _save_warnings_picker = ft.FilePicker()
    page.services.append(_browse_picker)
    page.services.append(_save_warnings_picker)

    async def on_browse(e):
        result = await _browse_picker.get_directory_path(dialog_title=t("components:sync_minebase.选择输出目录_c690"))
        if result:
            sync_path.value = result
            _update_last_directory(result, is_dir=True)
            _show_path_confirm(sync_path)
            sync_path.update()

    sync_path.suffix.on_click = on_browse

    # --- 同步模式 ---
    mode_toggle = ChipToggle(
        options=[("api", t("components:sync_minebase.API模式_6169")), ("database", t("components:sync_minebase.直连数据库_8b9a"))],
        initial=get_minebase_mode(),
    )

    # --- 冲突策略 ---
    conflict_policy = ChipToggle(
        options=[("SKIP", t("components:sync_minebase.跳过重复_5cd1")), ("UPDATE", t("components:sync_minebase.覆盖更新_db4f")), ("REJECT", t("components:sync_minebase.拒绝全部_ecc4"))],
        initial="SKIP",
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
        label=t("components:sync_minebase.全选_66ee"),
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
        label=t("components:sync_minebase.预览模式（不实际推送）_bb8f"),
        value=False,
        active_color=theme.PRIMARY,
    )

    # --- 工时表头映射 & 台账匹配 ---
    _sync_hmc = HeaderModeConfig(
        label=t("components:sync_minebase.应用工时表头映射_e047"),
        tooltip=t("components:sync_minebase.对工作效率表应用列名映射配置_0b8b"),
    )

    equipment_ledger_check = ft.Checkbox(
        label=t("components:sync_minebase.设备台账匹配_5a23"),
        value=False,
        active_color=theme.PRIMARY,
        tooltip=t("components:sync_minebase.使用设备台账标准化设备名称_f03f"),
    )
    oil_ledger_check = ft.Checkbox(
        label=t("components:sync_minebase.油品台账匹配_8663"),
        value=True,
        active_color=theme.PRIMARY,
        tooltip=t("components:sync_minebase.使用油品台账标准化油品名称_3659"),
    )
    skip_hidden_rows_check = ft.Checkbox(
        label=t("components:sync_minebase.跳过隐藏行_bc25"),
        value=True,
        active_color=theme.PRIMARY,
        tooltip=t("components:sync_minebase.勾选后，Excel中被隐藏的行_ecd7"),
    )
    skip_hidden_cols_check = ft.Checkbox(
        label=t("components:sync_minebase.跳过隐藏列_3ed3"),
        value=False,
        active_color=theme.PRIMARY,
        tooltip=t("components:sync_minebase.勾选后，Excel中被隐藏的列_398b"),
    )

    # --- 过滤开关 ---
    filter_zero_hours = ft.Checkbox(label=t("components:sync_minebase.过滤零小时数_549f"), value=True, active_color=theme.PRIMARY)
    filter_zero_work_hours = ft.Checkbox(label=t("components:sync_minebase.过滤零运行小时数_eaf1"), value=False, active_color=theme.PRIMARY)
    filter_zero_hours_meter = ft.Checkbox(label=t("components:sync_minebase.过滤零小时仪表_99e8"), value=True, active_color=theme.PRIMARY)
    filter_zero_km_meter = ft.Checkbox(label=t("components:sync_minebase.过滤零公里仪表_2e3c"), value=True, active_color=theme.PRIMARY)
    filter_zero_run_hours = ft.Checkbox(label=t("components:sync_minebase.过滤零运行小时数_eaf1"), value=False, active_color=theme.PRIMARY)
    filter_zero_run_km = ft.Checkbox(label=t("components:sync_minebase.过滤零运行里程_d55d"), value=False, active_color=theme.PRIMARY)

    # --- 异常值检测 ---
    _anomaly = create_anomaly_controls()

    # --- 年份/月份 ---
    year_dropdown = ft.Dropdown(
        label=t("components:sync_minebase.年份_8f30"),
        options=_YEAR_OPTIONS,
        value=str(local_today().year),
        width=120,
        dense=True,
    )

    month_dropdown = ft.Dropdown(
        label=t("components:sync_minebase.月份_8190"),
        options=_MONTH_OPTIONS,
        value=str(local_today().month),
        width=100,
        dense=True,
    )

    # --- 表头起始行 ---
    header_row_field = ft.TextField(
        label=t("components:sync_minebase.表头起始行_7c63"),
        hint_text=t("components:sync_minebase.自动检测_ac65"),
        width=120,
        dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # --- 日期范围 ---
    today = local_today()
    yesterday = today - timedelta(days=1)

    date_filter_check = ft.Checkbox(
        label=t("components:sync_minebase.日期范围过滤_a6a9"),
        value=True,
        active_color=theme.PRIMARY,
        tooltip=t("components:sync_minebase.开启后只同步所选日期范围内的数_d174"),
    )

    class _DateValue:
        """简单的值容器，兼容 logic.py 中 refs['date_start'].value 的读取方式"""
        def __init__(self, init: str = ""):
            self.value = init

    _date_start_val = _DateValue(yesterday.isoformat())
    _date_end_val = _DateValue(yesterday.isoformat())

    _start_display = ft.Text(
        _date_start_val.value, size=13, weight=ft.FontWeight.W_500,
    )
    _end_display = ft.Text(
        _date_end_val.value, size=13, weight=ft.FontWeight.W_500,
    )

    def _update_displays():
        _start_display.value = _date_start_val.value or t("components:sync_minebase.未设置_fe2d")
        _end_display.value = _date_end_val.value or t("components:sync_minebase.未设置_fe2d")
        try:
            _start_display.update()
            _end_display.update()
        except (RuntimeError, AttributeError):
            pass

    def _make_on_pick(target_val: _DateValue):
        async def _on_pick(e):
            ref_date = date.fromisoformat(target_val.value) if target_val.value else yesterday
            dp = ft.DatePicker(
                first_date=datetime(2015, 1, 1),
                last_date=datetime(2040, 12, 31),
                current_date=to_local_dt(ref_date),
            )
            def _on_picked(ev):
                if dp.value:
                    # dp.value 是 UTC datetime，需先转为本地时间再取日期
                    target_val.value = dp.value.astimezone().date().isoformat()
                    _update_displays()
                page.pop_dialog()
            dp.on_change = _on_picked
            dp.on_dismiss = lambda ev: page.pop_dialog()
            page.show_dialog(dp)
        return _on_pick

    _pick_start_btn = theme.secondary_btn(
        t("components:sync_minebase.选择_153f"), icon=ft.Icons.CALENDAR_MONTH, height=32,
    )
    _pick_start_btn.on_click = _make_on_pick(_date_start_val)

    _pick_end_btn = theme.secondary_btn(
        t("components:sync_minebase.选择_153f"), icon=ft.Icons.CALENDAR_MONTH, height=32,
    )
    _pick_end_btn.on_click = _make_on_pick(_date_end_val)

    def on_yesterday_click(e):
        _date_start_val.value = yesterday.isoformat()
        _date_end_val.value = yesterday.isoformat()
        _update_displays()

    yesterday_btn = ft.Button(
        t("components:sync_minebase.昨日_23c9"),
        icon=ft.Icons.CALENDAR_TODAY,
        on_click=on_yesterday_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM),
        ),
    )

    def on_clear_date(e):
        _date_start_val.value = ""
        _date_end_val.value = ""
        _update_displays()

    clear_date_btn = ft.Button(
        t("components:sync_minebase.清除_4403"),
        icon=ft.Icons.CLEAR_ALL,
        on_click=on_clear_date,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM),
        ),
    )

    date_range_row = ft.ResponsiveRow(
        [
            ft.Container(
                ft.Row([ft.Text(t("components:sync_minebase.起始_859e"), size=12, color=theme.TEXT_SECONDARY), _start_display, _pick_start_btn], spacing=6),
                col={"xs": 12, "md": 6},
            ),
            ft.Container(
                ft.Row([ft.Text(t("components:sync_minebase.结束_12f1"), size=12, color=theme.TEXT_SECONDARY), _end_display, _pick_end_btn], spacing=6),
                col={"xs": 12, "md": 6},
            ),
            ft.Container(
                ft.Row([yesterday_btn, clear_date_btn], spacing=8),
                col={"xs": 12},
            ),
        ],
        run_spacing=4,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=date_filter_check.value,
    )

    def _on_date_filter_toggle(e):
        date_range_row.visible = date_filter_check.value
        try:
            date_range_row.update()
        except (RuntimeError, AttributeError):
            pass

    date_filter_check.on_change = _on_date_filter_toggle

    # --- 同步按钮 ---
    sync_btn = theme.primary_btn(t("components:sync_minebase.同步到MineBase_59e0"), icon=ft.Icons.CLOUD_UPLOAD)

    # --- 结果显示 ---
    result_text = ft.Text(
        "",
        size=13,
        color=theme.TEXT_SECONDARY,
        visible=False,
    )

    # --- 异常行表格 ---
    warnings_count_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    export_warnings_btn = theme.secondary_btn(t("components:sync_minebase.导出Excel_7d57"), icon=ft.Icons.DOWNLOAD, height=28)
    warnings_list = ft.Column([], spacing=2, scroll=ft.ScrollMode.AUTO, height=200)
    warnings_container = ft.Container(
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=theme.WARNING, size=16),
                        ft.Text(t("components:sync_minebase.异常行_6c1c"), size=13, weight=ft.FontWeight.W_500, color=theme.WARNING),
                        warnings_count_text,
                        ft.Container(expand=True),
                        export_warnings_btn,
                    ],
                    spacing=6,
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                warnings_list,
            ],
            spacing=6,
        ),
        bgcolor=theme.SURFACE,
        border=ft.Border.all(1, theme.WARNING),
        border_radius=theme.RADIUS_SM,
        padding=theme.SPACING_SM,
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
                theme.section_title(t("components:sync_minebase.MineBase数据同步_cf2d")),

                # ── 目录 + 同步模式 + 冲突策略 ──
                theme.module_card([
                    ft.Row([sync_path], spacing=8),
                    mode_toggle.row,
                    conflict_policy.row,
                ], label=t("components:sync_minebase.目录与模式_b3cf")),

                # ── 日期参数 ──
                theme.module_card([
                    ft.ResponsiveRow(
                        [
                            ft.Container(year_dropdown, col={"xs": 6, "md": 3}),
                            ft.Container(month_dropdown, col={"xs": 6, "md": 3}),
                            ft.Container(header_row_field, col={"xs": 6, "md": 3}),
                        ],
                        run_spacing=4,
                    ),
                    date_filter_check,
                    date_range_row,
                ], label=t("components:sync_minebase.日期参数_6ee8")),

                # ── 数据类型 ──
                theme.module_card([
                    type_row,
                ], label=t("components:sync_minebase.数据类型_185f")),

                # ── 处理选项 ──
                theme.module_card([
                    ft.ResponsiveRow(
                        [
                            ft.Container(dry_run_check, col={"xs": 6}),
                            ft.Container(_sync_hmc.toggle, col={"xs": 6}),
                            ft.Container(_sync_hmc.mode.row, col={"xs": 12}),
                            ft.Container(equipment_ledger_check, col={"xs": 6}),
                            ft.Container(oil_ledger_check, col={"xs": 6}),
                            ft.Container(skip_hidden_rows_check, col={"xs": 6}),
                            ft.Container(skip_hidden_cols_check, col={"xs": 6}),
                        ],
                        run_spacing=4,
                    ),
                ], label=t("components:sync_minebase.处理选项_6ad1")),

                # ── 数据过滤 ──
                theme.module_card([
                    ft.Text(t("components:sync_minebase.油耗处理_1a41"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                    ft.ResponsiveRow(
                        [
                            ft.Container(filter_zero_hours, col={"xs": 6}),
                            ft.Container(filter_zero_work_hours, col={"xs": 6}),
                        ],
                        run_spacing=4,
                    ),
                    ft.Divider(height=1, color=theme.BORDER),
                    ft.Text(t("components:sync_minebase.生产数据_9fb6"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                    ft.ResponsiveRow(
                        [
                            ft.Container(filter_zero_hours_meter, col={"xs": 6}),
                            ft.Container(filter_zero_km_meter, col={"xs": 6}),
                            ft.Container(filter_zero_run_hours, col={"xs": 6}),
                            ft.Container(filter_zero_run_km, col={"xs": 6}),
                        ],
                        run_spacing=4,
                    ),
                ], label=t("components:sync_minebase.数据过滤_8626")),

                # ── 异常值检测 ──
                theme.module_card([
                    _anomaly["container"],
                ], label=t("components:sync_minebase.异常值检测_699f")),

                # ── 操作 + 结果 ──
                ft.Row(
                    [sync_btn, result_text],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                warnings_container,
            ],
            spacing=theme.SPACING_MD,
        ),
        padding=ft.Padding.symmetric(horizontal=0, vertical=8),
    )

    refs = {
        "path": sync_path,
        "mode": mode_toggle,
        "conflict_policy": conflict_policy,
        "types": type_checks,
        "dry_run": dry_run_check,
        "btn": sync_btn,
        "result_text": result_text,
        "year": year_dropdown,
        "month": month_dropdown,
        "header_row": header_row_field,
        "date_start": _date_start_val,
        "date_end": _date_end_val,
        "date_filter_toggle": date_filter_check,
        "apply_header": _sync_hmc.toggle,
        "header_mode": _sync_hmc.mode,
        "use_equipment_ledger": equipment_ledger_check,
        "use_oil_ledger": oil_ledger_check,
        "skip_hidden": skip_hidden_rows_check,
        "skip_hidden_rows": skip_hidden_rows_check,
        "skip_hidden_cols": skip_hidden_cols_check,
        "_filter_zero_hours_toggle": filter_zero_hours,
        "_filter_zero_work_hours_toggle": filter_zero_work_hours,
        "_filter_zero_hours_meter_toggle": filter_zero_hours_meter,
        "_filter_zero_km_meter_toggle": filter_zero_km_meter,
        "_filter_zero_run_hours_toggle": filter_zero_run_hours,
        "_filter_zero_run_km_toggle": filter_zero_run_km,
        "_anomaly_enabled": _anomaly["_anomaly_enabled"],
        "_anomaly_report": _anomaly["_anomaly_report"],
        "_anomaly_mode": _anomaly["_anomaly_mode"],
        "warnings_container": warnings_container,
        "warnings_list": warnings_list,
        "warnings_count_text": warnings_count_text,
        "export_warnings_btn": export_warnings_btn,
        "save_warnings_picker": _save_warnings_picker,
    }

    return container, refs
