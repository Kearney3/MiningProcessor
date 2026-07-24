"""
异常行警告导出模块
"""
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from func.logger import get_logger

logger = get_logger(__name__)

# 数据类型中文映射
DATA_TYPE_LABELS: dict[str, str] = {
    "fuel": "油耗数据",
    "electrical": "电耗数据",
    "operation": "设备运行",
    "production": "生产数据",
    "work_efficiency": "工作效率",
}


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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
