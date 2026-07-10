"""维修记录 Excel 写入

使用 xlsxwriter 将统计 DataFrame 写入格式化的 Excel 文件。
"""
from datetime import date

import pandas as pd
import xlsxwriter


# ── 样式常量 ──────────────────────────────────────────────────

_DATE_FMT = "yyyy-mm-dd"
_PCT_FMT = "0.00%"
_HOUR_FMT = "0.0"
_HEADER_BG = "#4472C4"
_HEADER_FG = "#FFFFFF"
_ALT_ROW_BG = "#F2F7FB"


# ── xlsxwriter 样式工厂 ───────────────────────────────────────

def _make_formats(wb: xlsxwriter.Workbook) -> dict:
    """创建统一的格式集，避免重复定义。"""
    return {
        "header": wb.add_format({
            "bold": True, "font_color": _HEADER_FG, "bg_color": _HEADER_BG,
            "border": 1, "align": "center", "valign": "vcenter",
            "text_wrap": True,
        }),
        "date": wb.add_format({"num_format": _DATE_FMT, "border": 1, "align": "center"}),
        "pct": wb.add_format({"num_format": _PCT_FMT, "border": 1, "align": "center"}),
        "hour": wb.add_format({"num_format": _HOUR_FMT, "border": 1, "align": "center"}),
        "int": wb.add_format({"border": 1, "align": "center"}),
        "text": wb.add_format({"border": 1, "text_wrap": True, "valign": "top"}),
        "text_center": wb.add_format({"border": 1, "align": "center", "valign": "vcenter"}),
        "bold_int": wb.add_format({"bold": True, "border": 1, "align": "center"}),
        "bold_text": wb.add_format({"bold": True, "border": 1}),
        "alt_row": wb.add_format({"border": 1, "bg_color": _ALT_ROW_BG}),
        "alt_date": wb.add_format({
            "num_format": _DATE_FMT, "border": 1, "align": "center",
            "bg_color": _ALT_ROW_BG,
        }),
        "alt_pct": wb.add_format({
            "num_format": _PCT_FMT, "border": 1, "align": "center",
            "bg_color": _ALT_ROW_BG,
        }),
        "alt_hour": wb.add_format({
            "num_format": _HOUR_FMT, "border": 1, "align": "center",
            "bg_color": _ALT_ROW_BG,
        }),
        "alt_int": wb.add_format({
            "border": 1, "align": "center", "bg_color": _ALT_ROW_BG,
        }),
        "alt_text": wb.add_format({
            "border": 1, "text_wrap": True, "valign": "top", "bg_color": _ALT_ROW_BG,
        }),
        "alt_text_center": wb.add_format({
            "border": 1, "align": "center", "valign": "vcenter",
            "bg_color": _ALT_ROW_BG,
        }),
    }


# ── 列宽计算 ─────────────────────────────────────────────────

def _char_width(text: str) -> int:
    """计算字符串显示宽度（CJK 宽字符计 2）。"""
    w = 0
    for ch in str(text):
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF or 0x3000 <= cp <= 0x303F:
            w += 2
        else:
            w += 1
    return w


def _auto_col_width(headers: list[str], rows: list[tuple], min_w: int = 8, max_w: int = 50) -> list[int]:
    """计算自适应列宽（支持 CJK 宽字符）。"""
    widths = [_char_width(h) + 2 for h in headers]
    for row in rows[:500]:
        for i, val in enumerate(row):
            if val is None:
                continue
            cell_w = 12 if isinstance(val, (date, pd.Timestamp)) else _char_width(str(val)) + 2
            if i < len(widths):
                widths[i] = max(widths[i], cell_w)
    return [min(max(w, min_w), max_w) for w in widths]


# ── Sheet 写入 ────────────────────────────────────────────────

def _write_sheet(
    wb: xlsxwriter.Workbook,
    sheet_name: str,
    headers: list[str],
    rows: list[tuple],
    fmts: dict,
    col_formats: list[str] | None = None,
    date_cols: set[int] | None = None,
    pct_cols: set[int] | None = None,
    hour_cols: set[int] | None = None,
    wrap_cols: set[int] | None = None,
):
    """通用 sheet 写入：表头 + 数据行 + 自适应列宽 + 冻结 + 筛选。"""
    ws = wb.add_worksheet(sheet_name)
    date_cols = date_cols or set()
    pct_cols = pct_cols or set()
    hour_cols = hour_cols or set()
    wrap_cols = wrap_cols or set()

    # 表头
    for col, h in enumerate(headers):
        ws.write(0, col, h, fmts["header"])

    # 数据行（交替底色）
    for row_idx, row in enumerate(rows):
        is_alt = row_idx % 2 == 1
        for col_idx, val in enumerate(row):
            if val is None:
                fmt = fmts["alt_text"] if is_alt else fmts["text"]
                ws.write(row_idx + 1, col_idx, "", fmt)
            elif col_idx in date_cols:
                fmt = fmts["alt_date"] if is_alt else fmts["date"]
                if isinstance(val, (date, pd.Timestamp)):
                    ws.write_datetime(row_idx + 1, col_idx, pd.Timestamp(val).to_pydatetime(), fmt)
                else:
                    ws.write(row_idx + 1, col_idx, str(val), fmt)
            elif col_idx in pct_cols:
                fmt = fmts["alt_pct"] if is_alt else fmts["pct"]
                ws.write_number(row_idx + 1, col_idx, float(val) if val else 0, fmt)
            elif col_idx in hour_cols:
                fmt = fmts["alt_hour"] if is_alt else fmts["hour"]
                ws.write_number(row_idx + 1, col_idx, float(val) if val else 0, fmt)
            elif col_idx in wrap_cols:
                fmt = fmts["alt_text"] if is_alt else fmts["text"]
                ws.write(row_idx + 1, col_idx, str(val), fmt)
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                fmt = fmts["alt_int"] if is_alt else fmts["int"]
                ws.write_number(row_idx + 1, col_idx, float(val), fmt)
            else:
                fmt = fmts["alt_text_center"] if is_alt else fmts["text_center"]
                ws.write(row_idx + 1, col_idx, str(val) if val is not None else "", fmt)

    # 列宽
    widths = _auto_col_width(headers, rows)
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)

    # 冻结首行 + 自动筛选
    ws.freeze_panes(1, 0)
    if rows:
        last_col = len(headers) - 1
        ws.autofilter(0, 0, len(rows), last_col)


# ── 数据驱动 Excel 输出 ──────────────────────────────────────

# (sheet_name, date_col_indices, pct_col_indices, hour_col_indices, wrap_col_indices)
_SHEET_SPECS: list[tuple[str, set[int], set[int], set[int], set[int]]] = [
    ("维修明细",         {0},     set(),  set(),  {9}),
    ("大类汇总",         set(),   {4, 5}, {3},    set()),
    ("大类×小类",        set(),   {5},    {4},    set()),
    ("按设备统计",       {2, 3},  {8},    {7},    set()),
    ("按设备型号统计",   set(),   {7},    {4},    set()),
    ("大类×年月",        set(),   set(),  {4},    set()),
    ("设备名称×大类小类", set(),  {6},    {5},    set()),
    ("型号×大类小类",    set(),   {7},    {6},    set()),
    ("设备名称×原因",    {4, 5},  {10},   {9},    set()),
    ("发动机故障深挖",   {2},     set(),  set(),  {5}),
]


def write_excel(output_file: str, sheets: dict[str, pd.DataFrame]) -> None:
    """用 xlsxwriter 将所有 sheet 写入 Excel。

    Args:
        output_file: 输出文件路径。
        sheets: {sheet_name: DataFrame} 字典。
    """
    wb = xlsxwriter.Workbook(output_file, {"strings_to_urls": False, "nan_inf_to_errors": True})
    fmts = _make_formats(wb)

    for name, date_cols, pct_cols, hour_cols, wrap_cols in _SHEET_SPECS:
        if name not in sheets:
            continue
        df = sheets[name]
        headers = list(df.columns)
        rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
        _write_sheet(
            wb, name, headers, rows, fmts,
            date_cols=date_cols, pct_cols=pct_cols,
            hour_cols=hour_cols, wrap_cols=wrap_cols,
        )

    wb.close()
