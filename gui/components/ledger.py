"""设备台账区域组件"""
import logging
import os
from pathlib import Path

import pandas as pd
import flet as ft

# 定位到当前项目的根目录

import func.equipment_ledger as equipment_ledger
from func.equipment_ledger import LEDGER_COLUMNS

from .common import _log_message
from .types import LedgerRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_column_mapping_dialog(
    page: ft.Page,
    file_columns: list[str],
    on_confirm,
) -> ft.AlertDialog:
    """创建列映射对话框，让用户将 Excel 列映射到标准列"""

    # 标准列名及其中文提示
    STANDARD_COLS = [
        ("设备名称", "设备的原始名称（用于匹配）"),
        ("设备编号", "设备的原始编号"),
        ("公司", "设备所属公司"),
        ("标准设备名称", "标准化后的设备名称"),
        ("标准设备编号", "标准化后的设备编号"),
        ("标准公司名称", "标准化后的公司名称"),
    ]

    mapping_controls = []
    dropdowns = {}

    for col_name, hint in STANDARD_COLS:
        # 自动匹配：如果 Excel 中有同名列，预选它
        default_value = col_name if col_name in file_columns else None
        dd = ft.Dropdown(
            label=col_name,
            hint_text=hint,
            options=[ft.dropdown.Option(c) for c in file_columns],
            value=default_value,
            width=280,
            dense=True,
        )
        dropdowns[col_name] = dd
        mapping_controls.append(dd)

    skip_header_checkbox = ft.Checkbox(
        label="第一行为标题行（排除）",
        value=True,
    )

    def on_cancel(e):
        page.pop_dialog()
        page.update()

    def on_ok(e):
        mapping = {}
        for std_col, dd in dropdowns.items():
            val = dd.value
            if val:
                mapping[std_col] = val
        page.pop_dialog()
        page.update()
        on_confirm(mapping, skip_header_checkbox.value)

    dialog = ft.AlertDialog(
        title=ft.Text("列映射配置"),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text("请将 Excel 文件的列映射到标准列：", size=13),
                    *mapping_controls,
                    ft.Divider(),
                    skip_header_checkbox,
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=320,
            height=400,
        ),
        actions=[
            ft.TextButton("取消", on_click=on_cancel),
            ft.TextButton("确认导入", on_click=on_ok, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color="#FFFFFF")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    return dialog


# ---------------------------------------------------------------------------
# 台账区域
# ---------------------------------------------------------------------------
def _cell_text(value) -> str:
    """将单元格值转为显示文本，NaN/None 显示为空字符串"""
    if value is None:
        return ""
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def create_ledger_section(page: ft.Page, log) -> tuple[ft.Container, "LedgerRefs"]:
    """创建设备台账区域，返回 (container, refs)"""
    PAGE_SIZE = 20
    ledger_records = []
    _ledger_page = [0]
    _ledger_instance = [None]  # 当前加载的 EquipmentLedger 实例
    _last_directory = [""]  # 记住上次文件选择器的目录
    ledger_path_label = ft.Text("未加载台账", size=12, color=ft.Colors.GREY)
    ledger_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text(c)) for c in LEDGER_COLUMNS
        ],
        rows=[],
    )

    ledger_page_label = ft.Text("0 / 0", size=12, color=theme.TEXT_SECONDARY)
    ledger_prev_btn = ft.IconButton(
        icon=ft.icons.Icons.CHEVRON_LEFT, tooltip="上一页", icon_size=18, disabled=True,
    )
    ledger_next_btn = ft.IconButton(
        icon=ft.icons.Icons.CHEVRON_RIGHT, tooltip="下一页", icon_size=18, disabled=True,
    )
    ledger_pagination = ft.Row(
        [ledger_prev_btn, ledger_page_label, ledger_next_btn],
        spacing=4, alignment=ft.MainAxisAlignment.CENTER,
    )

    def _ledger_total_pages():
        return max(1, (len(ledger_records) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_ledger_page_controls():
        total = _ledger_total_pages()
        cur = _ledger_page[0]
        ledger_page_label.value = f"{cur + 1} / {total}"
        ledger_prev_btn.disabled = cur <= 0
        ledger_next_btn.disabled = cur >= total - 1

    _empty_state = ft.Column(
        [
            ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=48, color=ft.Colors.GREY_300),
            ft.Text("暂无设备台账数据", size=14, color=theme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
            ft.Text("点击上方「导入台账」开始", size=12, color=ft.Colors.GREY_400),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
    )

    def build_table():
        start = _ledger_page[0] * PAGE_SIZE
        end = start + PAGE_SIZE
        page_records = ledger_records[start:end]
        if not ledger_records:
            ledger_table.rows = []
            ledger_table.columns = [ft.DataColumn(ft.Text("暂无数据"))]
            _empty_state.visible = True
        else:
            _empty_state.visible = False
            ledger_table.columns = [ft.DataColumn(ft.Text(c)) for c in LEDGER_COLUMNS]
            ledger_table.rows = [
                ft.DataRow(
                    cells=[ft.DataCell(ft.Text(_cell_text(r.get(c)))) for c in LEDGER_COLUMNS]
                )
                for r in page_records
            ]
        _update_ledger_page_controls()
        page.update()

    def _ledger_prev(e):
        if _ledger_page[0] > 0:
            _ledger_page[0] -= 1
            build_table()

    def _ledger_next(e):
        if _ledger_page[0] < _ledger_total_pages() - 1:
            _ledger_page[0] += 1
            build_table()

    ledger_prev_btn.on_click = _ledger_prev
    ledger_next_btn.on_click = _ledger_next

    ledger_table_wrapper = ft.Column(
        controls=[
            ft.Row(
                controls=[ledger_table],
                scroll=ft.ScrollMode.AUTO,
            ),
            _empty_state,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    async def on_load(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="导入设备台账",
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] or None,
        )
        if not files:
            return
        path = files[0].path
        _last_directory[0] = str(Path(path).parent)

        try:
            # 先读取文件的列名用于映射对话框
            preview_df = pd.read_excel(path, nrows=0)
            file_columns = list(preview_df.columns)
        except Exception as ex:
            ledger_path_label.value = f"读取文件失败: {ex}"
            ledger_path_label.color = ft.Colors.RED
            _log_message(log, f"读取台账文件失败: {ex}", level=logging.ERROR)
            page.update()
            return

        def _do_import(column_mapping, skip_header):
            try:
                ledger = equipment_ledger.EquipmentLedger()
                ledger.load(path, column_mapping=column_mapping, skip_header=skip_header)
                nonlocal ledger_records
                ledger_records = ledger.to_dict()
                _ledger_page[0] = 0
                _ledger_instance[0] = ledger
                ledger_path_label.value = os.path.basename(path)
                ledger_path_label.color = ft.Colors.GREEN
                build_table()
                _log_message(log, f"已加载台账: {path} ({len(ledger_records)} 条记录)")
            except Exception as ex:
                ledger_path_label.value = f"加载失败: {ex}"
                ledger_path_label.color = ft.Colors.RED
                _log_message(log, f"加载台账失败: {ex}", level=logging.ERROR)
            page.update()

        # 弹出列映射对话框
        dialog = create_column_mapping_dialog(page, file_columns, _do_import)
        page.show_dialog(dialog)
        page.update()

    async def on_export_template(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title="导出模板",
            file_name="设备台账模板.xlsx",
            allowed_extensions=["xlsx"],
            initial_directory=_last_directory[0] or None,
        )
        if not path:
            return
        _last_directory[0] = str(Path(path).parent)
        try:
            ledger = equipment_ledger.EquipmentLedger()
            ledger.export_template(path)
            _log_message(log, f"已导出模板: {path}")
        except Exception as ex:
            _log_message(log, f"导出模板失败: {ex}", level=logging.ERROR)
        page.update()

    def on_clear(e):
        nonlocal ledger_records
        ledger_records = []
        _ledger_instance[0] = None
        _ledger_page[0] = 0
        ledger_path_label.value = "未加载台账"
        ledger_path_label.color = ft.Colors.GREY
        build_table()
        _log_message(log, "台账已清空")

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("设备台账"),
                ft.Row(
                    [
                        theme.secondary_btn("导入台账", icon=ft.icons.Icons.UPLOAD, on_click=on_load),
                        theme.secondary_btn("清空台账", icon=ft.icons.Icons.DELETE_SWEEP, on_click=on_clear),
                        theme.secondary_btn("导出模板", icon=ft.icons.Icons.DOWNLOAD, on_click=on_export_template),
                        ledger_path_label,
                    ],
                    spacing=8,
                ),
                ft.Container(
                    content=ledger_table_wrapper,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    bgcolor=theme.SURFACE_HIGH,
                    expand=True,
                ),
                ledger_pagination,
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

    refs = {
        "ledger_table": ledger_table,
        "ledger_path_label": ledger_path_label,
        "ledger_records": ledger_records,
        "get_ledger": lambda: _ledger_instance[0],
        "build_table": build_table,
    }
    return container, refs
