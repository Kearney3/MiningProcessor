"""
异常行警告导出 & 试运行预览导出模块
"""
from pathlib import Path
from typing import Any

import pandas as pd

from func.logger import get_logger
from func.time_utils import local_now

logger = get_logger(__name__)

# 数据类型中文映射
DATA_TYPE_LABELS: dict[str, str] = {
    "fuel": "油耗数据",
    "electrical": "电耗数据",
    "operation": "设备运行",
    "production": "生产数据",
    "work_efficiency": "工作效率",
}

# 内部元数据列，预览 Excel 中不展示
_INTERNAL_KEYS = {"_row_num"}


def export_warnings_to_excel(
    warnings: list[dict[str, Any]],
    output_path: str | Path | None = None,
    input_dir: str | Path | None = None,
) -> str:
    """将异常行警告列表导出为 Excel 文件。

    Args:
        warnings: 警告条目列表，每个条目包含 data_type/type, row, field, value, message。
        output_path: 目标导出文件路径。若未指定，在 input_dir 下自动生成 异常行明细_YYYYMMDD_HHMMSS.xlsx。
        input_dir: 基础目录，用于生成默认文件名。

    Returns:
        导出的 Excel 文件绝对路径字符串。
    """
    if not output_path:
        base_dir = Path(input_dir) if input_dir else Path.cwd()
        timestamp = local_now().strftime("%Y%m%d_%H%M%S")
        output_path = base_dir / f"异常行明细_{timestamp}.xlsx"

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in warnings:
        # 支持 (data_type, warning_dict) 或 flat dict
        if isinstance(item, tuple) and len(item) == 2:
            dt_key, w = item
        elif isinstance(item, dict):
            dt_key = item.get("data_type") or item.get("type") or ""
            w = item
        else:
            continue

        raw_val = w.get("value")
        if raw_val is None or raw_val == "" or (isinstance(raw_val, float) and pd.isna(raw_val)):
            display_val = "（空）"
        else:
            display_val = str(raw_val)

        rows.append({
            "数据类型": DATA_TYPE_LABELS.get(dt_key, dt_key),
            "行号": w.get("row", "?"),
            "字段": w.get("field", ""),
            "原始值": display_val,
            "问题说明": w.get("message", ""),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["数据类型", "行号", "字段", "原始值", "问题说明"])

    from func.excel_formatter import write_formatted_excel
    write_formatted_excel(str(out_file), {"异常行明细": df})

    logger.info("已成功导出 %d 条异常行数据至: %s", len(rows), out_file)
    return str(out_file)


# ---------------------------------------------------------------------------
# 试运行预览导出
# ---------------------------------------------------------------------------


def export_dry_run_to_excel(
    dry_run_rows: dict[str, list[dict[str, Any]]],
    warnings: list[dict[str, Any]] | None = None,
    column_mapping: dict[str, dict[str, str]] | None = None,
    output_path: str | Path | None = None,
    input_dir: str | Path | None = None,
) -> str:
    """将试运行预览数据导出为多 sheet Excel 文件。

    每个数据类型生成一个独立 sheet，包含双重表头（源列名 + 数据库字段名）；
    另外生成"汇总"sheet 展示各类型行数统计。

    Args:
        dry_run_rows: {data_type: [row_dict, ...]} 的字典。
        warnings: 可选警告列表（来自台账匹配等阶段）。
        column_mapping: 列映射配置 {data_type_or_table: {源列名: 目标字段名}}，
                        用于生成第二行表头。未提供时只显示字段名。
        output_path: 目标导出文件路径。若未指定，自动生成。
        input_dir: 基础目录，用于生成默认文件名。

    Returns:
        导出的 Excel 文件绝对路径字符串。
    """
    if not output_path:
        base_dir = Path(input_dir) if input_dir else Path.cwd()
        timestamp = local_now().strftime("%Y%m%d_%H%M%S")
        output_path = base_dir / f"同步预览_{timestamp}.xlsx"

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # 构建反向映射：{data_type: {目标字段名 → 源列名}}
    reverse_mapping = _build_reverse_mapping(column_mapping) if column_mapping else {}

    sheets: dict[str, pd.DataFrame] = {}
    second_headers: dict[str, list[str]] = {}

    # 各数据类型 sheet
    summary_rows = []
    for data_type, rows in dry_run_rows.items():
        label = DATA_TYPE_LABELS.get(data_type, data_type)
        if rows:
            clean_rows = [
                {k: v for k, v in row.items() if k not in _INTERNAL_KEYS}
                for row in rows
            ]
            df = pd.DataFrame(clean_rows)
        else:
            df = pd.DataFrame()

        # 双重表头：将 DataFrame 列名改为源列名，第二行存储字段名
        rev = reverse_mapping.get(data_type, {})
        if rev and not df.empty:
            new_cols = {}
            row2 = []
            for col in df.columns:
                src_name = rev.get(col, col)
                new_cols[col] = src_name
                row2.append(col)
            df = df.rename(columns=new_cols)
            second_headers[label] = row2

        sheets[label] = df

        summary_rows.append({
            "数据类型": label,
            "表名": data_type,
            "记录数": len(rows),
        })

    # 汇总 sheet
    sheets["汇总"] = pd.DataFrame(summary_rows)

    # 异常行 sheet（如果有警告）
    if warnings:
        warning_rows = []
        for item in warnings:
            if isinstance(item, tuple) and len(item) == 2:
                dt_key, w = item
            elif isinstance(item, dict):
                dt_key = item.get("data_type") or item.get("type") or ""
                w = item
            else:
                continue

            raw_val = w.get("value")
            if raw_val is None or raw_val == "" or (isinstance(raw_val, float) and pd.isna(raw_val)):
                display_val = "（空）"
            else:
                display_val = str(raw_val)

            warning_rows.append({
                "数据类型": DATA_TYPE_LABELS.get(dt_key, dt_key),
                "行号": w.get("row", "?"),
                "字段": w.get("field", ""),
                "原始值": display_val,
                "问题说明": w.get("message", ""),
            })

        if warning_rows:
            sheets["异常行"] = pd.DataFrame(warning_rows)

    # 将"汇总"放在第一个 sheet
    ordered_sheets = {"汇总": sheets.pop("汇总")}
    ordered_sheets.update(sheets)

    from func.excel_formatter import write_dual_header_sheet
    write_dual_header_sheet(str(out_file), ordered_sheets, second_headers=second_headers)

    total_rows = sum(len(rows) for rows in dry_run_rows.values())
    logger.info("已导出试运行预览: %d 条记录 → %s", total_rows, out_file)
    return str(out_file)


def _build_reverse_mapping(
    column_mapping: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """从列映射配置构建反向映射。

    输入: {data_type_or_table: {源列名: 目标字段名}}
    输出: {data_type: {目标字段名: 源列名}}
    """
    from func.sync.constants import DATA_TYPE_REGISTRY

    result: dict[str, dict[str, str]] = {}
    for data_type, info in DATA_TYPE_REGISTRY.items():
        table = info["table"]
        # 尝试 data_type key 和 table key
        mapping = column_mapping.get(data_type) or column_mapping.get(table, {})
        if mapping:
            result[data_type] = {v: k for k, v in mapping.items()}
    return result
