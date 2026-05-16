"""台账匹配工具区域组件"""
import asyncio
import logging
import math
import sys
import threading
from pathlib import Path

import pandas as pd
import flet as ft

root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root))

from .common import _log_message

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def _cell_text(value) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def create_ledger_match_section(
    page: ft.Page, log, ledger_refs: dict, oil_ledger_refs: dict
) -> tuple[ft.Container, dict]:
    """创建台账匹配工具区域，返回 (container, refs)"""

    PAGE_SIZE = 20
    _all_sheets: dict[str, pd.DataFrame] = {}  # sheet_name -> DataFrame (原始数据)
    _filtered_df: list[pd.DataFrame] = [None]  # 当前 sheet 经过排序/筛选后的视图
    _current_sheet = [""]
    _page = [0]
    _columns: list[str] = []
    _sort_column: list[str] = [None]  # 当前排序列
    _sort_ascending: list[bool] = [True]  # 排序方向
    _col_width: list[int] = [120]  # 列宽

    # --- 控件 ---
    file_label = ft.Text("未导入文件", size=12, color=ft.Colors.GREY)

    sheet_dropdown = ft.Dropdown(
        label="Sheet",
        width=200,
        dense=True,
        options=[],
    )

    name_dropdown = ft.Dropdown(
        label="设备名称列",
        hint_text="（可选）",
        width=180,
        dense=True,
        options=[],
    )
    id_dropdown = ft.Dropdown(
        label="设备编号列",
        hint_text="（可选）",
        width=180,
        dense=True,
        options=[],
    )
    oil_dropdown = ft.Dropdown(
        label="油品列",
        hint_text="（可选）",
        width=180,
        dense=True,
        options=[],
    )

    match_btn = theme.primary_btn("执行匹配", icon=ft.Icons.SEARCH, disabled=True)
    export_btn = theme.secondary_btn("导出结果", icon=ft.Icons.DOWNLOAD, disabled=True)

    status_label = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    col_width_field = ft.TextField(
        label="列宽",
        hint_text="像素 (如 120)",
        width=100,
        dense=True,
        value="120",
    )
    col_width_apply_btn = theme.secondary_btn("应用列宽", icon=ft.Icons.FIT_SCREEN, disabled=True)

    _import_progress_bar = ft.ProgressBar(
        value=0, height=6, visible=False, expand=True,
    )
    _import_progress_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY, visible=False)
    _cancel_btn = ft.IconButton(
        icon=ft.Icons.CANCEL, tooltip="取消导入", icon_size=18,
        visible=False,
    )
    _import_cancelled = threading.Event()

    # --- 表格 ---
    data_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("等待导入数据..."))],
        rows=[],
        expand=True,
    )

    page_label = ft.Text("0 / 0", size=12, color=theme.TEXT_SECONDARY)
    prev_btn = ft.IconButton(
        icon=ft.icons.Icons.CHEVRON_LEFT, tooltip="上一页", icon_size=18, disabled=True,
    )
    next_btn = ft.IconButton(
        icon=ft.icons.Icons.CHEVRON_RIGHT, tooltip="下一页", icon_size=18, disabled=True,
    )

    # ========================================================================
    # 内部工具函数
    # ========================================================================
    def _get_current_df() -> pd.DataFrame | None:
        name = _current_sheet[0]
        if not name or name not in _all_sheets:
            return None
        return _all_sheets[name]

    def _apply_filter_and_sort():
        """对当前 sheet 的 DataFrame 应用排序，更新 _filtered_df"""
        df = _get_current_df()
        if df is None:
            _filtered_df[0] = None
            return

        result = df.copy()

        # 排序
        col = _sort_column[0]
        if col and col in result.columns:
            ascending = _sort_ascending[0]
            try:
                result = result.sort_values(by=col, ascending=ascending, kind="stable")
            except Exception:
                pass

        _filtered_df[0] = result

    def _total_pages():
        df = _filtered_df[0]
        if df is None or df.empty:
            return 1
        return max(1, (len(df) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_page_controls():
        total = _total_pages()
        cur = _page[0]
        page_label.value = f"{cur + 1} / {total}"
        prev_btn.disabled = cur <= 0
        next_btn.disabled = cur >= total - 1

    def _show_import_progress(total: int):
        """显示导入进度 UI"""
        _import_cancelled.clear()
        _import_progress_bar.value = 0
        _import_progress_bar.visible = True
        _import_progress_text.value = f"正在解析 0/{total} 个 sheet..."
        _import_progress_text.visible = True
        _cancel_btn.visible = True
        match_btn.disabled = True

    def _update_import_progress(current: int, total: int, sheet_name: str):
        """更新导入进度"""
        _import_progress_bar.value = current / total if total > 0 else 0
        _import_progress_text.value = f"正在解析 {current}/{total}: {sheet_name}"

    def _hide_import_progress():
        """隐藏导入进度 UI"""
        _import_progress_bar.visible = False
        _import_progress_text.visible = False
        _cancel_btn.visible = False
        _import_progress_bar.value = 0

    def _on_cancel_import(e):
        _import_cancelled.set()
        _log_message(log, "正在取消导入...")

    _cancel_btn.on_click = _on_cancel_import

    def _sort_indicator(col_name: str) -> str:
        """返回排序指示箭头"""
        if col_name == _sort_column[0]:
            return " ▲" if _sort_ascending[0] else " ▼"
        return ""

    def _rebuild_columns(cols: list[str]):
        nonlocal _columns
        _columns = cols
        w = _col_width[0]

        def on_sort_handler(col_name):
            def handler(e):
                if _sort_column[0] == col_name:
                    _sort_ascending[0] = not _sort_ascending[0]
                else:
                    _sort_column[0] = col_name
                    _sort_ascending[0] = True
                _apply_filter_and_sort()
                _page[0] = 0
                build_table()
            return handler

        if cols:
            data_table.columns = [
                ft.DataColumn(
                    ft.Container(
                        ft.Text(c + _sort_indicator(c), size=13, no_wrap=True),
                        width=w,
                    ),
                    on_sort=on_sort_handler(c),
                )
                for c in cols
            ]
        else:
            data_table.columns = [ft.DataColumn(ft.Text("等待导入数据..."))]

    def build_table():
        _apply_filter_and_sort()
        df = _filtered_df[0]
        if df is None or df.empty:
            data_table.rows = []
            data_table.columns = [ft.DataColumn(ft.Text("等待导入数据..."))]
            _update_page_controls()
            page.update()
            return

        cols = list(df.columns)
        _rebuild_columns(cols)

        start = _page[0] * PAGE_SIZE
        end = start + PAGE_SIZE
        page_df = df.iloc[start:end]

        rows = []
        for row_idx, row in page_df.iterrows():
            cells = []
            for c in cols:
                cell_value = _cell_text(row[c])
                cells.append(ft.DataCell(ft.Text(cell_value, size=13, selectable=True)))
            rows.append(ft.DataRow(cells=cells))

        data_table.rows = rows
        _update_page_controls()
        page.update()

    def _prev(e):
        if _page[0] > 0:
            _page[0] -= 1
            build_table()

    def _next(e):
        if _page[0] < _total_pages() - 1:
            _page[0] += 1
            build_table()

    prev_btn.on_click = _prev
    next_btn.on_click = _next

    def _on_col_width_apply(e):
        try:
            w = int(col_width_field.value)
            if w < 30:
                w = 30
            if w > 600:
                w = 600
        except (ValueError, TypeError):
            w = 120
        _col_width[0] = w
        build_table()

    col_width_apply_btn.on_click = _on_col_width_apply

    # ========================================================================
    # Sheet 切换 & 列名自动匹配
    # ========================================================================
    def _update_column_dropdowns(cols: list[str]):
        options = [ft.dropdown.Option(c) for c in cols]
        for dd in [name_dropdown, id_dropdown, oil_dropdown]:
            old_val = dd.value
            dd.options = options
            if old_val and old_val in cols:
                dd.value = old_val
            else:
                dd.value = None
        if not name_dropdown.value:
            for c in cols:
                if c in ("设备名称", "矿卡名称"):
                    name_dropdown.value = c
                    break
        if not id_dropdown.value:
            for c in cols:
                if c == "设备编号":
                    id_dropdown.value = c
                    break
        if not oil_dropdown.value:
            for c in cols:
                if c in ("油品种类", "油品名称"):
                    oil_dropdown.value = c
                    break

    def _on_sheet_change(sheet_name: str):
        if not sheet_name or sheet_name not in _all_sheets:
            return
        _current_sheet[0] = sheet_name
        _page[0] = 0
        _sort_column[0] = None
        _sort_ascending[0] = True
        df = _all_sheets[sheet_name]
        _update_column_dropdowns(list(df.columns))
        build_table()

    sheet_dropdown.on_change = lambda e: _on_sheet_change(e.control.value)

    # ========================================================================
    # 文件导入
    # ========================================================================
    async def on_import(e):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="导入 Excel 文件",
            allowed_extensions=["xlsx", "xls"],
        )
        if not files:
            return
        path = files[0].path

        # 快速读取 sheet 名（不解析数据）
        try:
            xl = pd.ExcelFile(path)
        except Exception as ex:
            file_label.value = f"读取失败: {ex}"
            file_label.color = ft.Colors.RED
            _log_message(log, f"读取文件失败: {ex}", level=logging.ERROR)
            page.update()
            return

        sheet_names = xl.sheet_names
        total = len(sheet_names)
        if total == 0:
            _log_message(log, "文件中没有 sheet", level=logging.WARNING)
            return

        # 显示进度条
        _show_import_progress(total)
        page.update()

        # 后台线程逐 sheet 解析
        parsed_sheets: dict[str, pd.DataFrame] = {}

        def _parse_in_background():
            for i, sname in enumerate(sheet_names):
                if _import_cancelled.is_set():
                    break
                try:
                    df = xl.parse(sname)
                except Exception:
                    df = pd.DataFrame()
                parsed_sheets[sname] = df
                try:
                    page.run_thread(lambda _i=i, _s=sname: _update_and_refresh(_i + 1, total, _s))
                except Exception:
                    pass

        def _update_and_refresh(current, total_val, sname):
            _update_import_progress(current, total_val, sname)
            page.update()

        worker = threading.Thread(target=_parse_in_background, daemon=True)
        worker.start()

        # 等待后台线程完成
        while worker.is_alive():
            await asyncio.sleep(0.1)

        _hide_import_progress()

        if _import_cancelled.is_set():
            _log_message(log, f"导入已取消（已解析 {len(parsed_sheets)}/{total} 个 sheet）")
            if not parsed_sheets:
                page.update()
                return

        # 使用已解析的数据
        _all_sheets.clear()
        _all_sheets.update(parsed_sheets)

        file_label.value = Path(path).name
        file_label.color = ft.Colors.GREEN

        sheet_dropdown.options = [ft.dropdown.Option(s) for s in sheet_names]
        if sheet_names:
            first = sheet_names[0]
            sheet_dropdown.value = first
            _current_sheet[0] = first
            _page[0] = 0
            df = _all_sheets.get(first, pd.DataFrame())
            _update_column_dropdowns(list(df.columns))
        else:
            _current_sheet[0] = ""

        match_btn.disabled = False
        col_width_apply_btn.disabled = False
        build_table()
        loaded = len(parsed_sheets)
        _log_message(log, f"已导入: {path} ({loaded}/{total} 个 sheet)")
        page.update()

    def on_clear(e):
        _hide_import_progress()
        _all_sheets.clear()
        _filtered_df[0] = None
        _current_sheet[0] = ""
        _page[0] = 0
        _sort_column[0] = None
        _sort_ascending[0] = True
        file_label.value = "未导入文件"
        file_label.color = ft.Colors.GREY
        sheet_dropdown.options = []
        sheet_dropdown.value = None
        name_dropdown.options = []
        name_dropdown.value = None
        id_dropdown.options = []
        id_dropdown.value = None
        oil_dropdown.options = []
        oil_dropdown.value = None
        match_btn.disabled = True
        export_btn.disabled = True
        col_width_apply_btn.disabled = True
        status_label.value = ""
        data_table.columns = [ft.DataColumn(ft.Text("等待导入数据..."))]
        data_table.rows = []
        _log_message(log, "已清空")
        page.update()

    # ========================================================================
    # 执行匹配
    # ========================================================================
    def on_match(e):
        df = _get_current_df()
        if df is None or df.empty:
            _log_message(log, "没有数据可匹配", level=logging.WARNING)
            return

        eq_ledger = ledger_refs.get("get_ledger", lambda: None)()
        oil_ledger = oil_ledger_refs.get("get_oil_ledger", lambda: None)()

        if not eq_ledger and not oil_ledger:
            _log_message(log, "请先在设备台账或油品台账页导入台账", level=logging.WARNING)
            return

        name_col = name_dropdown.value
        id_col = id_dropdown.value
        oil_col = oil_dropdown.value

        if not name_col and not id_col and not oil_col:
            _log_message(log, "未选择任何匹配列，跳过匹配")
            return

        result_df = df.copy()
        matched_count = 0

        # 设备匹配
        if eq_ledger and (name_col or id_col):
            std_names, std_ids, std_companies = [], [], []
            for _, row in result_df.iterrows():
                n = str(row[name_col]) if name_col and name_col in result_df.columns and not pd.isna(row.get(name_col)) else None
                i = str(row[id_col]) if id_col and id_col in result_df.columns and not pd.isna(row.get(id_col)) else None
                r = eq_ledger.match_device(name=n, device_id=i)
                if r:
                    std_names.append(r.get("标准设备名称", ""))
                    std_ids.append(r.get("标准设备编号", ""))
                    std_companies.append(r.get("标准公司名称", ""))
                    matched_count += 1
                else:
                    std_names.append("")
                    std_ids.append("")
                    std_companies.append("")
            result_df["标准设备名称"] = std_names
            result_df["标准设备编号"] = std_ids
            result_df["标准公司名称"] = std_companies

        # 油品匹配
        oil_matched = 0
        if oil_ledger and oil_col and oil_col in result_df.columns:
            std_oils = []
            for _, row in result_df.iterrows():
                v = row[oil_col]
                r = oil_ledger.match(str(v)) if not pd.isna(v) else None
                if r:
                    std_oils.append(r["标准名称"])
                    oil_matched += 1
                else:
                    std_oils.append("")
            result_df["标准油品名称"] = std_oils

        _all_sheets[_current_sheet[0]] = result_df
        _page[0] = 0
        export_btn.disabled = False
        build_table()

        parts = []
        if eq_ledger and (name_col or id_col):
            total = len(result_df)
            parts.append(f"设备匹配: {matched_count}/{total}")
        if oil_ledger and oil_col:
            total = len(result_df)
            parts.append(f"油品匹配: {oil_matched}/{total}")
        status_label.value = "  |  ".join(parts)
        _log_message(log, f"匹配完成: {status_label.value}")
        page.update()

    # ========================================================================
    # 导出
    # ========================================================================
    async def on_export(e):
        if not _all_sheets:
            _log_message(log, "没有数据可导出", level=logging.WARNING)
            return
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title="导出匹配结果",
            file_name="匹配结果.xlsx",
            allowed_extensions=["xlsx"],
        )
        if not path:
            return
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                for sname, sdf in _all_sheets.items():
                    sdf.to_excel(writer, sheet_name=sname, index=False)
            _log_message(log, f"已导出: {path}")
        except Exception as ex:
            _log_message(log, f"导出失败: {ex}", level=logging.ERROR)
        page.update()

    match_btn.on_click = on_match
    export_btn.on_click = on_export

    # ========================================================================
    # 布局
    # ========================================================================
    table_wrapper = ft.Column(
        controls=[
            ft.Row(
                controls=[data_table],
                scroll=ft.ScrollMode.AUTO,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        height=450,
        expand=True,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("台账匹配"),
                ft.Row(
                    [
                        theme.secondary_btn("导入文件", icon=ft.icons.Icons.UPLOAD, on_click=on_import),
                        theme.secondary_btn("清空", icon=ft.icons.Icons.DELETE_SWEEP, on_click=on_clear),
                        file_label,
                        ft.Container(width=16),
                        col_width_field,
                        col_width_apply_btn,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row([sheet_dropdown], spacing=8),
                ft.Row(
                    [_import_progress_bar, _import_progress_text, _cancel_btn],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text("设备匹配:", size=13, color=theme.TEXT_SECONDARY),
                        name_dropdown,
                        id_dropdown,
                        ft.Text("油品匹配:", size=13, color=theme.TEXT_SECONDARY),
                        oil_dropdown,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [match_btn, export_btn, status_label],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=table_wrapper,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    bgcolor=theme.SURFACE_HIGH,
                    expand=True,
                ),
                ft.Row(
                    [prev_btn, page_label, next_btn],
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
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

    refs = {}
    return container, refs
