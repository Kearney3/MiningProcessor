"""日报导出区域。"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import flet as ft

from func.daily_report import export_daily_report
from gui.components.common import _get_initial_directory, to_local_dt

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_daily_report_section(page: ft.Page, log, ledger_refs: dict, model_ledger_refs: dict) -> tuple[ft.Container, dict]:
    source_path = ft.TextField(
        hint_text="选择数据目录",
        value=_get_initial_directory(),
        expand=True,
    )
    selected_dates = {
        "start": date.today() - timedelta(days=1),
        "end": date.today() - timedelta(days=1),
    }
    date_labels = {
        key: ft.Text(value.strftime("%Y-%m-%d"), size=13, color=theme.TEXT_PRIMARY)
        for key, value in selected_dates.items()
    }
    result_text = ft.Text("", size=13, color=theme.TEXT_SECONDARY, visible=False)

    eq_toggle = ft.Checkbox(label="设备台账匹配", value=True, active_color=theme.PRIMARY)
    model_toggle = ft.Checkbox(label="型号台账匹配", value=False, active_color=theme.PRIMARY)
    skip_hidden_rows = ft.Checkbox(label="跳过隐藏行", value=False, active_color=theme.PRIMARY)
    skip_hidden_cols = ft.Checkbox(label="跳过隐藏列", value=False, active_color=theme.PRIMARY)
    filter_zero_engine_hours = ft.Checkbox(label="过滤零小时数", value=False, active_color=theme.PRIMARY)
    filter_zero_work_hours = ft.Checkbox(label="过滤零运行小时数", value=False, active_color=theme.PRIMARY)
    filter_zero_hours_meter = ft.Checkbox(label="过滤零小时仪表", value=False, active_color=theme.PRIMARY)
    filter_zero_km_meter = ft.Checkbox(label="过滤零公里仪表", value=False, active_color=theme.PRIMARY)
    filter_zero_run_hours = ft.Checkbox(label="过滤零运行小时数", value=False, active_color=theme.PRIMARY)
    filter_zero_run_km = ft.Checkbox(label="过滤零运行里程", value=False, active_color=theme.PRIMARY)

    def on_equipment_toggle(e):
        model_toggle.disabled = not bool(eq_toggle.value)
        if not eq_toggle.value:
            model_toggle.value = False
        model_toggle.update()

    eq_toggle.on_change = on_equipment_toggle
    model_toggle.disabled = not bool(eq_toggle.value)

    picker = ft.FilePicker()
    page.services.append(picker)

    async def browse_source(e):
        selected = await picker.get_directory_path(dialog_title="选择日报数据目录")
        if selected:
            source_path.value = selected
            source_path.update()

    source_path.suffix = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        tooltip="选择文件夹",
        on_click=browse_source,
    )

    def update_date_label(key: str):
        date_labels[key].value = selected_dates[key].strftime("%Y-%m-%d")
        try:
            date_labels[key].update()
        except (RuntimeError, AttributeError):
            pass

    def pick_date(key: str):
        date_picker = ft.DatePicker(
            first_date=datetime(2015, 1, 1),
            last_date=datetime(2040, 12, 31),
            current_date=to_local_dt(selected_dates[key]),
        )

        def on_date_picked(e):
            if date_picker.value:
                selected_dates[key] = date_picker.value.astimezone().date()
                update_date_label(key)
            page.pop_dialog()

        date_picker.on_change = on_date_picked
        date_picker.on_dismiss = lambda e: page.pop_dialog()
        page.show_dialog(date_picker)

    def date_control(key: str, label: str):
        return ft.Row(
            [
                ft.Text(label, size=12, color=theme.TEXT_SECONDARY, width=42),
                date_labels[key],
                theme.secondary_btn(
                    "选择",
                    icon=ft.Icons.CALENDAR_MONTH,
                    height=32,
                    on_click=lambda e, selected_key=key: pick_date(selected_key),
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def set_yesterday(e):
        yesterday = date.today() - timedelta(days=1)
        selected_dates["start"] = yesterday
        selected_dates["end"] = yesterday
        update_date_label("start")
        update_date_label("end")

    async def export(e):
        path = (source_path.value or "").strip()
        if not path:
            result_text.value, result_text.color, result_text.visible = "请选择数据目录", theme.ERROR, True
            result_text.update()
            return
        if model_toggle.value and not eq_toggle.value:
            result_text.value, result_text.color, result_text.visible = "型号台账匹配需要设备台账", theme.ERROR, True
            result_text.update()
            return
        if selected_dates["end"] < selected_dates["start"]:
            result_text.value, result_text.color, result_text.visible = "结束日期早于起始日期", theme.ERROR, True
            result_text.update()
            return

        output = str(Path(path) / f"每日报表_{selected_dates['start']:%Y-%m-%d}_{selected_dates['end']:%Y-%m-%d}.xlsx")
        try:
            eq = ledger_refs.get("get_ledger", lambda: None)() if eq_toggle.value else None
            model = model_ledger_refs.get("get_model_ledger", lambda: None)() if model_toggle.value else None
            result = await asyncio.to_thread(
                export_daily_report,
                path,
                output,
                selected_dates["start"].isoformat(),
                selected_dates["end"].isoformat(),
                equipment_ledger=eq,
                model_ledger=model,
                preprocess_options={
                    "skip_hidden_rows": bool(skip_hidden_rows.value),
                    "skip_hidden_cols": bool(skip_hidden_cols.value),
                    "filter_zero_engine_hours": bool(filter_zero_engine_hours.value),
                    "filter_zero_work_hours": bool(filter_zero_work_hours.value),
                    "filter_zero_hours_meter": bool(filter_zero_hours_meter.value),
                    "filter_zero_km_meter": bool(filter_zero_km_meter.value),
                    "filter_zero_run_hours": bool(filter_zero_run_hours.value),
                    "filter_zero_run_km": bool(filter_zero_run_km.value),
                },
            )
            result_text.value = f"已保存至当前目录，{len(result.report)} 行，警告 {len(result.warnings)} 条"
            result_text.color = theme.WARNING if result.warnings else theme.SUCCESS
            result_text.visible = True
            log(result_text.value, logging.WARNING if result.warnings else logging.INFO)
            result_text.update()
        except Exception as ex:
            log(f"日报导出失败: {ex}", logging.ERROR)
            result_text.value, result_text.color, result_text.visible = f"日报导出失败: {ex}", theme.ERROR, True
            result_text.update()

    export_btn = theme.primary_btn("导出每日报表", icon=ft.Icons.DOWNLOAD)
    export_btn.on_click = export

    date_range = ft.ResponsiveRow(
        [
            ft.Container(date_control("start", "起始"), col={"xs": 12, "md": 6}),
            ft.Container(date_control("end", "结束"), col={"xs": 12, "md": 6}),
            ft.Container(
                ft.Row(
                    [
                        theme.secondary_btn("昨日", icon=ft.Icons.CALENDAR_TODAY, height=32, on_click=set_yesterday),
                    ],
                    spacing=8,
                ),
                col={"xs": 12},
            ),
        ],
        run_spacing=4,
    )

    options = ft.ResponsiveRow(
        [
            ft.Container(eq_toggle, col={"xs": 12, "md": 6}),
            ft.Container(model_toggle, col={"xs": 12, "md": 6}),
            ft.Container(skip_hidden_rows, col={"xs": 12, "md": 6}),
            ft.Container(skip_hidden_cols, col={"xs": 12, "md": 6}),
        ],
        run_spacing=4,
    )

    filters = ft.Column(
        [
            ft.Text("油耗处理", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.ResponsiveRow(
                [
                    ft.Container(filter_zero_engine_hours, col={"xs": 12, "md": 6}),
                    ft.Container(filter_zero_work_hours, col={"xs": 12, "md": 6}),
                ],
                run_spacing=4,
            ),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("运行数据", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.ResponsiveRow(
                [
                    ft.Container(filter_zero_hours_meter, col={"xs": 12, "md": 6}),
                    ft.Container(filter_zero_km_meter, col={"xs": 12, "md": 6}),
                    ft.Container(filter_zero_run_hours, col={"xs": 12, "md": 6}),
                    ft.Container(filter_zero_run_km, col={"xs": 12, "md": 6}),
                ],
                run_spacing=4,
            ),
        ],
        spacing=6,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("每日报表"),
                theme.module_card([ft.Row([source_path], spacing=8)], label="数据目录"),
                theme.module_card([date_range], label="日期范围"),
                theme.module_card([options], label="处理选项"),
                theme.module_card([filters], label="数据过滤"),
                ft.Row(
                    [export_btn, result_text],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            ],
            spacing=theme.SPACING_MD,
        ),
        padding=ft.Padding.symmetric(horizontal=0, vertical=8),
    )
    return container, {
        "btn": export_btn,
        "result_text": result_text,
        "eq_toggle": eq_toggle,
        "model_toggle": model_toggle,
        "skip_hidden_rows": skip_hidden_rows,
        "skip_hidden_cols": skip_hidden_cols,
        "filter_zero_engine_hours": filter_zero_engine_hours,
        "filter_zero_work_hours": filter_zero_work_hours,
        "filter_zero_hours_meter": filter_zero_hours_meter,
        "filter_zero_km_meter": filter_zero_km_meter,
        "filter_zero_run_hours": filter_zero_run_hours,
        "filter_zero_run_km": filter_zero_run_km,
    }
