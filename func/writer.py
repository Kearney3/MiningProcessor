"""维修记录统计 Excel 写入

用 xlsxwriter 将所有 sheet 写入格式化的 Excel 文件。
支持交替行底色、自适应列宽、冻结首行、自动筛选。
"""
import calendar
from datetime import date

import pandas as pd
import xlsxwriter

logger = __import__("logging").getLogger(__name__)


# ── 样式常量 ──────────────────────────────────────────────────

_HEADER_BG = "#4472C4"
_HEADER_FG = "#FFFFFF"
_ALT_ROW_BG = "#F2F7FB"
_DATE_FMT = "yyyy-mm-dd"
_PCT_FMT = "0.00%"
_HOUR_FMT = "0.0"


# ── sheet 调色板（不同 sheet 不同表头色）──
_SHEET_COLORS = [
    "#4472C4",  # 蓝
    "#548235",  # 绿
    "#BF8F00",  # 金
    "#843C0C",  # 棕
    "#44546A",  # 深灰
    "#E7792B",  # 橙
    "#3B7DD8",  # 亮蓝
    "#70AD47",  # 草绿
]


def _make_formats(wb: xlsxwriter.Workbook, header_bg: str) -> dict:
    """创建格式集。"""
    hdr = wb.add_format({
        "bold": True, "font_color": _HEADER_FG, "bg_color": header_bg,
        "border": 1, "align": "center", "valign": "vcenter",
        "text_wrap": True,
    })
    f_int = wb.add_format({"border": 1, "align": "center"})
    f_txt_center = wb.add_format({"border": 1, "align": "center", "valign": "vcenter"})
    f_txt = wb.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    f_date = wb.add_format({"num_format": _DATE_FMT, "border": 1, "align": "center"})
    f_pct = wb.add_format({"num_format": _PCT_FMT, "border": 1, "align": "center"})
    f_hour = wb.add_format({"num_format": _HOUR_FMT, "border": 1, "align": "center"})
    # 交替行
    bg_alt = _ALT_ROW_BG
    a_int = wb.add_format({"border": 1, "align": "center", "bg_color": bg_alt})
    a_txt_center = wb.add_format({"border": 1, "align": "center", "valign": "vcenter", "bg_color": bg_alt})
    a_txt = wb.add_format({"border": 1, "text_wrap": True, "valign": "top", "bg_color": bg_alt})
    a_date = wb.add_format({"num_format": _DATE_FMT, "border": 1, "align": "center", "bg_color": bg_alt})
    a_pct = wb.add_format({"num_format": _PCT_FMT, "border": 1, "align": "center", "bg_color": bg_alt})
    a_hour = wb.add_format({"num_format": _HOUR_FMT, "border": 1, "align": "center", "bg_color": bg_alt})
    return {
        "hdr": hdr,
        "int": f_int, "txt_center": f_txt_center, "txt": f_txt,
        "date": f_date, "pct": f_pct, "hour": f_hour,
        "a_int": a_int, "a_txt_center": a_txt_center, "a_txt": a_txt,
        "a_date": a_date, "a_pct": a_pct, "a_hour": a_hour,
    }


def _auto_col_width(headers: list[str], rows: list[tuple], min_w: int = 8, max_w: int = 50) -> list[int]:
    """计算自适应列宽（支持 CJK 宽字符）。"""
    def _width(text: str) -> int:
        w = 0
        for ch in str(text):
            cp = ord(ch)
            if 0x4E00 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF or 0x3000 <= cp <= 0x303F:
                w += 2
            else:
                w += 1
        return w
    widths = [_width(h) + 2 for h in headers]
    for row in rows[:500]:
        for i, val in enumerate(row):
            if val is None:
                continue
            cell_w = 12 if isinstance(val, (date, pd.Timestamp)) else _width(str(val)) + 2
            if i < len(widths):
                widths[i] = max(widths[i], cell_w)
    return [min(max(w, min_w), max_w) for w in widths]


def _detect_stats(headers: list[str], rows: list[tuple]) -> tuple[set[int], set[int], set[int], set[int]]:
    """自动检测日期/百分比/小时/wrap 列的索引。"""
    date_cols: set[int] = set()
    pct_cols: set[int] = set()
    hour_cols: set[int] = set()
    wrap_cols: set[int] = set()
    for i, h in enumerate(headers):
        if "日期" in h and "占比" not in h and "占比" not in h:
            date_cols.add(i)
        if "占比" in h or "故障率" in h:
            pct_cols.add(i)
        if "小时" in h:
            hour_cols.add(i)
        if "维修内容" in h:
            wrap_cols.add(i)
    return date_cols, pct_cols, hour_cols, wrap_cols


def _write_sheet(wb: xlsxwriter.Workbook, ws_name: str, df: pd.DataFrame, color_idx: int):
    """写入一个 sheet。"""
    if df is None or df.empty:
        return
    ws = wb.add_worksheet(ws_name)
    fmts = _make_formats(wb, _SHEET_COLORS[color_idx % len(_SHEET_COLORS)])

    headers = list(df.columns)
    rows = df.values.tolist()
    date_cols, pct_cols, hour_cols, wrap_cols = _detect_stats(headers, rows)

    # 表头
    for col, h in enumerate(headers):
        ws.write(0, col, h, fmts["hdr"])

    # 数据行
    for row_idx, row in enumerate(rows):
        is_alt = row_idx % 2 == 1
        for col_idx, val in enumerate(row):
            if val is None:
                ws.write(row_idx + 1, col_idx, "", fmts["a_txt"] if is_alt else fmts["txt"])
            elif col_idx in date_cols and isinstance(val, (date, pd.Timestamp)):
                ws.write_datetime(row_idx + 1, col_idx, pd.Timestamp(val).to_pydatetime(), fmts["a_date"] if is_alt else fmts["date"])
            elif col_idx in pct_cols:
                ws.write_number(row_idx + 1, col_idx, float(val) if val else 0, fmts["a_pct"] if is_alt else fmts["pct"])
            elif col_idx in hour_cols:
                ws.write_number(row_idx + 1, col_idx, float(val) if val else 0, fmts["a_hour"] if is_alt else fmts["hour"])
            elif col_idx in wrap_cols:
                ws.write(row_idx + 1, col_idx, str(val), fmts["a_txt"] if is_alt else fmts["txt"])
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                ws.write_number(row_idx + 1, col_idx, float(val), fmts["a_int"] if is_alt else fmts["int"])
            else:
                ws.write(row_idx + 1, col_idx, str(val) if val is not None else "", fmts["a_txt_center"] if is_alt else fmts["txt_center"])

    # 列宽
    widths = _auto_col_width(headers, rows)
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)

    # 冻结首行 + 自动筛选
    ws.freeze_panes(1, 0)
    if rows:
        ws.autofilter(0, 0, len(rows), len(headers) - 1)


def write_excel(output_file: str, sheets: dict[str, pd.DataFrame]) -> None:
    """将所有 sheet 写入格式化的 Excel 文件。

    sheet 写入顺序：
    1. 维修明细
    2. 每月设备故障统计
    3. 全周期设备故障统计
    4. 全周期设备故障汇总
    5. 每月设备型号故障统计
    6. 全周期设备型号故障统计
    7. 全周期设备故障汇总(型号)
    8. 故障类型统计
    """
    ORDER = [
        "维修明细",
        "每月设备故障统计",
        "全周期设备故障统计",
        "全周期设备故障汇总",
        "每月设备型号故障统计",
        "全周期设备型号故障统计",
        "全周期设备故障汇总(型号)",
        "故障类型统计",
    ]
    wb = xlsxwriter.Workbook(output_file, {"strings_to_urls": False, "nan_inf_to_errors": True})
    for idx, name in enumerate(ORDER):
        if name in sheets:
            _write_sheet(wb, name, sheets[name], idx)
    wb.close()
    logger.info("输出完成: %s (8 sheets)", output_file)
