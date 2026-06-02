"""油品台账区域组件"""
import logging
import os
from pathlib import Path

import pandas as pd
import flet as ft

# 定位到当前项目的根目录

import func.oil_ledger as oil_ledger
from func.oil_ledger import OIL_LEDGER_COLUMNS
from func import config_loader

from .common import _log_message, _last_directory, _update_last_directory, SortState, create_sortable_columns
from .types import OilLedgerRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_oil_column_mapping_dialog(
    page: ft.Page,
    file_columns: list[str],
    on_confirm,
) -> ft.AlertDialog:
    """创建油品台账列映射对话框，让用户将 Excel 列映射到标准列"""

    STANDARD_COLS = [
        ("油品名称", "油品的原始名称（用于匹配）"),
        ("标准油品名称", "标准化后的油品名称"),
    ]

    mapping_controls = []
    dropdowns = {}

    for col_name, hint in STANDARD_COLS:
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
            height=300,
        ),
        actions=[
            ft.TextButton("取消", on_click=on_cancel),
            ft.TextButton("确认导入", on_click=on_ok, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color="#FFFFFF")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    return dialog


# ---------------------------------------------------------------------------
# 油品台账区域
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


def create_oil_ledger_section(page: ft.Page, log) -> tuple[ft.Container, "OilLedgerRefs"]:
    """创建油品台账区域，返回 (container, refs)"""
    PAGE_SIZE = 20
    oil_records = []
    _oil_page = [0]
    _oil_instance = [None]  # 当前加载的 OilLedger 实例
    _sort_state = SortState()  # 排序状态
    oil_path_label = ft.Text("未加载油品台账", size=12, color=ft.Colors.GREY)
    oil_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text(c)) for c in OIL_LEDGER_COLUMNS
        ],
        rows=[],
    )

    oil_page_label = ft.Text("0 / 0", size=12, color=theme.TEXT_SECONDARY)
    oil_prev_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT, tooltip="上一页", icon_size=18, disabled=True,
    )
    oil_next_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT, tooltip="下一页", icon_size=18, disabled=True,
    )
    oil_pagination = ft.Row(
        [oil_prev_btn, oil_page_label, oil_next_btn],
        spacing=4, alignment=ft.MainAxisAlignment.CENTER,
    )

    def _oil_total_pages():
        return max(1, (len(oil_records) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_oil_page_controls():
        total = _oil_total_pages()
        cur = _oil_page[0]
        oil_page_label.value = f"{cur + 1} / {total}"
        oil_prev_btn.disabled = cur <= 0
        oil_next_btn.disabled = cur >= total - 1

    _empty_state = ft.Column(
        [
            ft.Icon(ft.Icons.OIL_BARREL_OUTLINED, size=48, color=ft.Colors.GREY_300),
            ft.Text("暂无油品台账数据", size=14, color=theme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
            ft.Text("点击上方「导入台账」开始", size=12, color=ft.Colors.GREY_400),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
    )

    def build_table():
        if not oil_records:
            oil_table.rows = []
            oil_table.columns = [ft.DataColumn(ft.Text("暂无数据"))]
            _empty_state.visible = True
            _update_oil_page_controls()
            page.update()
            return

        _empty_state.visible = False

        # 应用排序
        df = pd.DataFrame(oil_records)
        df = _sort_state.apply_to_dataframe(df)
        sorted_records = df.to_dict("records")

        start = _oil_page[0] * PAGE_SIZE
        end = start + PAGE_SIZE
        page_records = sorted_records[start:end]

        # 创建可排序的列
        def on_sort_callback():
            _oil_page[0] = 0
            build_table()

        oil_table.columns = create_sortable_columns(
            OIL_LEDGER_COLUMNS, _sort_state, on_sort_callback
        )

        # 设置当前排序列的显示状态
        sort_col_idx = _sort_state.get_column_index(OIL_LEDGER_COLUMNS)
        if sort_col_idx is not None:
            oil_table.sort_column_index = sort_col_idx
            oil_table.sort_ascending = _sort_state.ascending
        else:
            oil_table.sort_column_index = None

        oil_table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(_cell_text(r.get(c)))) for c in OIL_LEDGER_COLUMNS]
            )
            for r in page_records
        ]
        _update_oil_page_controls()
        page.update()
        page.update()

    def _oil_prev(e):
        if _oil_page[0] > 0:
            _oil_page[0] -= 1
            build_table()

    def _oil_next(e):
        if _oil_page[0] < _oil_total_pages() - 1:
            _oil_page[0] += 1
            build_table()

    oil_prev_btn.on_click = _oil_prev
    oil_next_btn.on_click = _oil_next

    oil_table_wrapper = ft.Column(
        controls=[
            oil_table,
            _empty_state,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    oil_table.expand = True

    async def on_load(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="导入油品台账",
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] or None,
        )
        if not files:
            return
        path = files[0].path
        _update_last_directory(path)

        try:
            preview_df = pd.read_excel(path, nrows=0)
            file_columns = list(preview_df.columns)
        except Exception as ex:
            oil_path_label.value = f"读取文件失败: {ex}"
            oil_path_label.color = ft.Colors.RED
            _log_message(log, f"读取油品台账文件失败: {ex}", level=logging.ERROR)
            page.update()
            return

        def _do_import(column_mapping, skip_header):
            try:
                ledger = oil_ledger.OilLedger()
                ledger.load(path, column_mapping=column_mapping, skip_header=skip_header)
                nonlocal oil_records
                oil_records = ledger.to_dict()
                _oil_page[0] = 0
                _oil_instance[0] = ledger
                oil_path_label.value = os.path.basename(path)
                oil_path_label.color = ft.Colors.GREEN
                build_table()
                _log_message(log, f"已加载油品台账: {path} ({len(oil_records)} 条记录)")
                _update_default_btn_state()
            except Exception as ex:
                oil_path_label.value = f"加载失败: {ex}"
                oil_path_label.color = ft.Colors.RED
                _log_message(log, f"加载油品台账失败: {ex}", level=logging.ERROR)
            page.update()

        dialog = create_oil_column_mapping_dialog(page, file_columns, _do_import)
        page.show_dialog(dialog)
        page.update()

    async def on_export_template(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title="导出模板",
            file_name="油品台账模板.xlsx",
            allowed_extensions=["xlsx"],
            initial_directory=_last_directory[0] or None,
        )
        if not path:
            return
        _update_last_directory(path)
        try:
            ledger = oil_ledger.OilLedger()
            ledger.export_template(path)
            _log_message(log, f"已导出油品台账模板: {path}")
        except Exception as ex:
            _log_message(log, f"导出模板失败: {ex}", level=logging.ERROR)
        page.update()

    def on_clear(e):
        nonlocal oil_records
        oil_records = []
        _oil_instance[0] = None
        _oil_page[0] = 0
        oil_path_label.value = "未加载油品台账"
        oil_path_label.color = ft.Colors.GREY
        build_table()
        _log_message(log, "油品台账已清空")
        _update_default_btn_state()

    def on_save_default(e):
        if not oil_records:
            _log_message(log, "没有油品台账数据可保存", level=logging.WARNING)
            return
        try:
            config_loader.save_oil_ledger_cache(oil_records)
            _log_message(log, f"已保存为默认油品台账 ({len(oil_records)} 条记录)")
        except Exception as ex:
            _log_message(log, f"保存默认油品台账失败: {ex}", level=logging.ERROR)

    def on_cancel_default(e):
        try:
            config_loader.clear_oil_ledger_cache()
            _log_message(log, "已取消默认油品台账")
        except Exception as ex:
            _log_message(log, f"取消默认油品台账失败: {ex}", level=logging.ERROR)



    def _update_default_btn_state():
        """更新保存/取消默认按钮的可用性。"""
        save_default_btn.disabled = not oil_records
        cancel_default_btn.disabled = not config_loader.has_oil_ledger_cache()
        try:
            save_default_btn.update()
            cancel_default_btn.update()
        except (RuntimeError, AttributeError):
            pass

    def load_from_cache():
        """从缓存加载默认油品台账，启动时调用。"""
        cached = config_loader.load_oil_ledger_cache()
        if not cached:
            return False
        nonlocal oil_records
        oil_records = cached
        _oil_page[0] = 0
        oil_path_label.value = "默认油品台账 (缓存)"
        oil_path_label.color = ft.Colors.GREEN
        build_table()
        _log_message(log, f"已自动加载默认油品台账 ({len(oil_records)} 条记录)")
        _update_default_btn_state()
        return True

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("油品台账"),
                ft.Column(
                    [
                        ft.Row(
                            [
                                theme.secondary_btn("导入台账", icon=ft.Icons.UPLOAD, on_click=on_load),
                                theme.secondary_btn("清空台账", icon=ft.Icons.DELETE_SWEEP, on_click=on_clear),
                                theme.secondary_btn("导出模板", icon=ft.Icons.DOWNLOAD, on_click=on_export_template),
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                save_default_btn := theme.primary_btn("保存为默认", icon=ft.Icons.BOOKMARK, on_click=on_save_default, disabled=True),
                                cancel_default_btn := theme.secondary_btn("取消默认", icon=ft.Icons.BOOKMARK_REMOVE, on_click=on_cancel_default, disabled=not config_loader.has_oil_ledger_cache()),
                                oil_path_label,
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Container(
                    content=oil_table_wrapper,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    bgcolor=theme.SURFACE_HIGH,
                    expand=True,
                ),
                oil_pagination,
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
        "oil_table": oil_table,
        "oil_path_label": oil_path_label,
        "oil_records": oil_records,
        "get_oil_ledger": lambda: _oil_instance[0],
        "build_table": build_table,
        "load_from_cache": load_from_cache,
    }
    return container, refs
