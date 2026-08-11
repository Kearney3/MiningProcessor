"""
Excel 统一格式化输出工具

提供所有处理器共用的 Excel 写入与格式化能力：
- 表头加粗 + 蓝底白字
- 列宽自适应（支持中日韩宽字符）
- 日期列格式化（yyyy-mm-dd）
- 冻结首行 + 自动筛选

性能优化：使用 xlsxwriter 单遍流式写入（边写数据边应用格式），
替代旧版 openpyxl 两遍模式（先写数据再逐单元格格式化），大文件快 3-5 倍。
"""

import datetime
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ── 样式常量 ──────────────────────────────────────────────────────────────

HEADER_FILL = "4472C4"
HEADER_FONT_COLOR = "FFFFFF"
DATE_NUM_FORMAT = "yyyy-mm-dd"
MIN_COL_WIDTH = 8
MAX_COL_WIDTH = 50
WIDTH_PADDING = 2

# 双重表头第二行样式
_DUAL_HEADER_FILL = "D9E2F3"
_DUAL_HEADER_FONT_COLOR = "44546A"


# ── 内部工具 ──────────────────────────────────────────────────────────────


def _display_width(text: str) -> int:
    """估算字符串显示宽度，CJK 字符计为 2。"""
    width = 0
    for ch in text:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF       # CJK Unified
            or 0x3400 <= cp <= 0x4DBF    # CJK Extension A
            or 0xFF00 <= cp <= 0xFFEF    # Fullwidth Forms
            or 0x3000 <= cp <= 0x303F    # CJK Symbols
            or 0x2E80 <= cp <= 0x2EFF    # CJK Radicals
            or 0xF900 <= cp <= 0xFAFF    # CJK Compatibility
            or 0xFE30 <= cp <= 0xFE4F    # CJK Compatibility Forms
        ):
            width += 2
        else:
            width += 1
    return width


def _auto_column_widths(
    df: pd.DataFrame,
    min_width: int = MIN_COL_WIDTH,
    max_width: int = MAX_COL_WIDTH,
    padding: int = WIDTH_PADDING,
) -> list[int]:
    """计算每列的自适应宽度（字符数）。采样前 200 行平衡准确度与性能。"""
    widths = []
    for col in df.columns:
        header_w = _display_width(str(col)) + padding
        max_w = header_w
        for value in df[col].dropna().head(200):
            if isinstance(value, (pd.Timestamp, datetime.datetime, datetime.date)):
                cell_w = 12  # yyyy-mm-dd
            else:
                cell_w = _display_width(str(value)) + padding
            max_w = max(max_w, cell_w)
        widths.append(min(max(max_w, min_width), max_width))
    return widths


def _is_date_column(series: pd.Series) -> bool:
    """检测 Series 是否为日期列。"""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().head(20)
    if sample.empty:
        return False
    return sample.apply(
        lambda v: isinstance(v, (datetime.date, datetime.datetime, pd.Timestamp))
    ).any()


def _detect_date_columns(df: pd.DataFrame) -> set[int]:
    """返回所有日期列的索引集合。"""
    return {i for i, col in enumerate(df.columns) if _is_date_column(df[col])}


def _sanitize_value(value):
    """处理 NaN / NaT 等 xlsxwriter 不接受的值。"""
    if value is None:
        return None
    # pd.isna 会抛异常于某些类型（如 dict），安全处理
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime.datetime, datetime.date)):
        return value
    return value


def _write_sheet_xlsxwriter(
    ws,
    df: pd.DataFrame,
    header_fmt,
    date_fmt,
    col_widths: list[int],
    is_date_col: set[int],
    has_second_header: bool = False,
    second_header_values: list[str] | None = None,
    second_header_fmt=None,
    data_start_row: int = 1,
):
    """用 xlsxwriter 单遍写入一个 sheet（表头 + 数据 + 格式）。"""
    ncols = len(df.columns)

    # 表头行
    for col_idx, col_name in enumerate(df.columns):
        ws.write(0, col_idx, str(col_name), header_fmt)
    current_row = 1

    # 第二行表头（双重表头模式）
    if has_second_header and second_header_values:
        for col_idx, val in enumerate(second_header_values[:ncols]):
            ws.write(1, col_idx, str(val), second_header_fmt)
        current_row = 2

    # 列宽
    for idx, width in enumerate(col_widths):
        ws.set_column(idx, idx, width)

    # 日期列格式（xlsxwriter 按列设置，无需逐单元格）
    for col_idx in is_date_col:
        # 为整个日期列设置格式（覆盖表头以外的区域）
        ws.set_column(col_idx, col_idx, col_widths[col_idx], date_fmt)
        # 重写表头以恢复表头格式（set_column 的格式会被表头覆盖，但保险起见）
        ws.write(0, col_idx, str(df.columns[col_idx]), header_fmt)
        if has_second_header and second_header_values:
            ws.write(1, col_idx, str(second_header_values[col_idx]), second_header_fmt)

    # 数据行（流式写入，不缓存）
    for row_idx in range(len(df)):
        row = df.iloc[row_idx]
        for col_idx in range(ncols):
            clean_val = _sanitize_value(row.iat[col_idx])
            if clean_val is not None:
                ws.write(current_row, col_idx, clean_val)
        current_row += 1

    # 冻结首行（或前两行）
    if has_second_header:
        ws.freeze_panes(2, 0)
    else:
        ws.freeze_panes(1, 0)

    # 自动筛选
    last_row = current_row - 1
    if last_row >= 0 and ncols > 0:
        ws.autofilter(0, 0, last_row, ncols - 1)


# ── 公开 API ──────────────────────────────────────────────────────────────


def _apply_date_only(df: pd.DataFrame) -> pd.DataFrame:
    """将 DataFrame 中的日期列统一转为 date-only 值（去除时间部分）。

    支持两种情况：
    1. 已是 datetime64 dtype → 转为 date 对象
    2. 字符串列含日期格式（如 '2024-01-15T00:00:00'）→ 解析后转为 date 对象

    返回新 DataFrame，不修改原 df。
    """
    import warnings

    changed = False
    result = df
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if not changed:
                result = df.copy()
                changed = True
            result[col] = result[col].apply(
                lambda v: v.date() if pd.notna(v) else v
            )
        elif pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            # 尝试解析字符串日期列
            sample = df[col].dropna().head(20)
            if sample.empty:
                continue
            # Excel 工时表的数值列经常因混有空值而被 pandas 读成 object。
            # 这些列不能参与日期解析，否则 720 分钟会被当作 Excel 日期序列，
            # 导出的分项工时数据会变成 1970-01-01。
            if not sample.map(lambda value: isinstance(value, str)).all():
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().mean() >= 0.8:
                    if not changed:
                        result = df.copy()
                        changed = True
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        result[col] = pd.to_datetime(result[col], errors="coerce").apply(
                            lambda v: v.date() if pd.notna(v) else v
                        )
            except (ValueError, TypeError):
                pass
    return result


def write_formatted_excel(
    output_file: str,
    sheets: dict[str, pd.DataFrame],
    *,
    header_fill: str = HEADER_FILL,
    header_font_color: str = HEADER_FONT_COLOR,
    date_format: str = DATE_NUM_FORMAT,
    freeze_header: bool = True,
    auto_filter: bool = True,
    min_col_width: int = MIN_COL_WIDTH,
    max_col_width: int = MAX_COL_WIDTH,
    date_only: bool = False,
) -> str:
    """写入带格式的 Excel 文件（xlsxwriter 单遍流式）。

    对每个 sheet 应用统一格式：
    - 表头：加粗、蓝底白字
    - 列宽：按内容自适应（支持 CJK 宽字符）
    - 日期列：格式化为 yyyy-mm-dd（按列设置，无逐单元格循环）
    - 冻结首行 + 自动筛选

    Args:
        output_file: 输出文件路径。
        sheets: {sheet_name: DataFrame} 映射。
        header_fill: 表头背景色（hex）。
        header_font_color: 表头字体颜色（hex）。
        date_format: 日期列的数字格式。
        freeze_header: 是否冻结首行。
        auto_filter: 是否启用自动筛选。
        min_col_width: 最小列宽（字符数）。
        max_col_width: 最大列宽（字符数）。
        date_only: 为 True 时，日期列去除时间部分（支持字符串日期）。

    Returns:
        输出文件路径。
    """
    import xlsxwriter

    output_file = str(output_file)
    wb = xlsxwriter.Workbook(output_file, {"constant_memory": True})

    header_fmt = wb.add_format({
        "bold": True,
        "font_color": header_font_color,
        "bg_color": header_fill,
        "align": "center",
        "valign": "vcenter",
    })
    date_fmt = wb.add_format({"num_format": date_format})

    for sheet_name, df in sheets.items():
        ws = wb.add_worksheet(sheet_name)
        # date_only mode: convert date columns to date-only values
        if date_only:
            df = _apply_date_only(df)
        col_widths = _auto_column_widths(df, min_col_width, max_col_width)
        date_cols = _detect_date_columns(df)
        _write_sheet_xlsxwriter(ws, df, header_fmt, date_fmt, col_widths, date_cols)

    wb.close()

    logger.info("格式化输出完成: %s", output_file)
    return output_file


# ── 双重表头支持 ─────────────────────────────────────────────────────────


def write_dual_header_sheet(
    output_file: str,
    sheets: dict[str, pd.DataFrame],
    *,
    second_headers: dict[str, list[str]],
    header_fill: str = HEADER_FILL,
    header_font_color: str = HEADER_FONT_COLOR,
    date_format: str = DATE_NUM_FORMAT,
    min_col_width: int = MIN_COL_WIDTH,
    max_col_width: int = MAX_COL_WIDTH,
) -> str:
    """写入带双重表头的 Excel 文件（xlsxwriter 单遍流式）。

    第一行为源列名（蓝底白字），第二行为目标字段名（浅灰底深灰字），
    第三行起为数据。仅对 sheets 中存在于 second_headers 的 sheet 应用双重表头，
    其余 sheet 仍使用单行表头格式。

    Args:
        output_file: 输出文件路径。
        sheets: {sheet_name: DataFrame} 映射。
        second_headers: {sheet_name: [第二行表头文本, ...]} 映射。
                        列表长度需与对应 DataFrame 的列数一致。

    Returns:
        输出文件路径。
    """
    import xlsxwriter

    output_file = str(output_file)
    wb = xlsxwriter.Workbook(output_file, {"constant_memory": True})

    header_fmt = wb.add_format({
        "bold": True,
        "font_color": header_font_color,
        "bg_color": header_fill,
        "align": "center",
        "valign": "vcenter",
    })
    second_fmt = wb.add_format({
        "font_color": _DUAL_HEADER_FONT_COLOR,
        "bg_color": _DUAL_HEADER_FILL,
        "font_size": 9,
        "align": "center",
        "valign": "vcenter",
    })
    date_fmt = wb.add_format({"num_format": date_format})

    for sheet_name, df in sheets.items():
        ws = wb.add_worksheet(sheet_name)
        col_widths = _auto_column_widths(df, min_col_width, max_col_width)
        date_cols = _detect_date_columns(df)
        is_dual = sheet_name in second_headers

        # 如果是双重表头，需要把第二行表头宽度也纳入列宽计算
        if is_dual:
            hdr2 = second_headers[sheet_name]
            for idx, hdr in enumerate(hdr2):
                w = _display_width(str(hdr)) + WIDTH_PADDING
                if idx < len(col_widths):
                    col_widths[idx] = max(col_widths[idx], min(w, max_col_width))

        _write_sheet_xlsxwriter(
            ws, df, header_fmt, date_fmt, col_widths, date_cols,
            has_second_header=is_dual,
            second_header_values=second_headers.get(sheet_name),
            second_header_fmt=second_fmt,
        )

    wb.close()

    logger.info("格式化输出完成（含双重表头）: %s", output_file)
    return output_file
