"""异常报告生成

输出 Excel 文件，包含：
- Sheet "异常汇总": 按规则统计触发次数和占比
- Sheet "异常明细": 逐条异常记录的完整信息
"""
from __future__ import annotations

import logging
import os
from collections import Counter

import pandas as pd

from func.anomaly.rules import AnomalyHit

logger = logging.getLogger(__name__)

# 数据类型中文名称
_DATA_TYPE_LABELS: dict[str, str] = {
    "fuel": "油耗数据",
    "fuel_engine": "发动机数据",
    "production_running": "运行数据",
    "production": "生产数据",
    "electrical": "电力消耗",
    "worktime": "工时数据",
}


def generate_anomaly_report(
    hits: list[AnomalyHit],
    df: pd.DataFrame,
    output_dir: str,
    data_type: str,
) -> str:
    """生成异常报告 Excel 文件。

    Parameters
    ----------
    hits : list[AnomalyHit]
        异常命中列表。
    df : pd.DataFrame
        原始数据（用于统计总数）。
    output_dir : str
        输出目录。
    data_type : str
        数据类型标识。

    Returns
    -------
    str
        输出文件路径。
    """
    label = _DATA_TYPE_LABELS.get(data_type, data_type)
    output_file = os.path.join(output_dir, f"异常报告_{label}.xlsx")

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        # Sheet 1: 异常汇总
        summary_df = _build_summary(hits, len(df))
        summary_df.to_excel(writer, sheet_name="异常汇总", index=False)

        # Sheet 2: 异常明细
        detail_df = _build_detail(hits, df)
        detail_df.to_excel(writer, sheet_name="异常明细", index=False)

    return output_file


def _build_summary(hits: list[AnomalyHit], total_rows: int) -> pd.DataFrame:
    """构建异常汇总表。"""
    counter: Counter[str] = Counter()
    for hit in hits:
        key = f"{hit.column} ({hit.method})"
        counter[key] += 1

    rows = []
    for rule_key, count in counter.most_common():
        ratio = f"{count / total_rows * 100:.1f}%" if total_rows > 0 else "N/A"
        rows.append({
            "检测规则": rule_key,
            "触发次数": count,
            "占总行数比例": ratio,
        })

    if not rows:
        rows.append({"检测规则": "无异常", "触发次数": 0, "占总行数比例": "0%"})

    return pd.DataFrame(rows)


def _build_detail(hits: list[AnomalyHit], df: pd.DataFrame) -> pd.DataFrame:
    """构建异常明细表。"""
    rows = []
    # 尝试保留上下文列
    context_cols = [c for c in ("日期", "班次", "设备名称", "设备编号") if c in df.columns]

    for hit in hits:
        row = {
            "行号": hit.row_index,
            "异常列": hit.column,
            "异常值": hit.value,
            "检测方法": hit.method,
            "说明": hit.message,
        }
        for col in context_cols:
            if hit.row_index in df.index:
                row[col] = df.at[hit.row_index, col]
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["行号", "异常列", "异常值", "检测方法", "说明"])

    # 固定列顺序：上下文列在前
    result = pd.DataFrame(rows)
    ordered = context_cols + [c for c in result.columns if c not in context_cols]
    return result[[c for c in ordered if c in result.columns]]
