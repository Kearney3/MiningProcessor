"""异常值过滤器

三种处理模式，均不可变（返回新 DataFrame）：
- flag:   新增「异常值」(bool) 和「异常值原因」(str) 列
- remove: 移除异常行
- handle: 按用户配置替换异常值（default_value）
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from func.anomaly.rules import ALL_NUMERIC_SENTINEL, AnomalyHit

logger = logging.getLogger(__name__)


# 标记列名
ANOMALY_FLAG_COLUMN = "异常值"
ANOMALY_REASON_COLUMN = "异常值原因"


class AnomalyFilterer:
    """对 DataFrame 进行不可变异常处理。"""

    @staticmethod
    def flag(df: pd.DataFrame, hits: list[AnomalyHit]) -> pd.DataFrame:
        """标记模式：新增「异常值」(bool) 和「异常值原因」(str) 列。不删除任何行。"""
        if not hits:
            return df

        # 按行索引聚合异常信息
        row_reasons: dict[Any, list[str]] = {}
        for hit in hits:
            row_reasons.setdefault(hit.row_index, []).append(hit.message)

        result = df.copy()
        result[ANOMALY_FLAG_COLUMN] = False
        result[ANOMALY_REASON_COLUMN] = ""
        for idx, reasons in row_reasons.items():
            if idx in result.index:
                result.at[idx, ANOMALY_FLAG_COLUMN] = True
                result.at[idx, ANOMALY_REASON_COLUMN] = "; ".join(reasons)

        return result

    @staticmethod
    def remove(df: pd.DataFrame, hits: list[AnomalyHit]) -> pd.DataFrame:
        """过滤模式：移除异常行，返回新 DataFrame。"""
        if not hits:
            return df

        indices_to_remove = set()
        for hit in hits:
            indices_to_remove.add(hit.row_index)

        return df.drop(index=list(indices_to_remove & set(df.index)))

    @staticmethod
    def handle(
        df: pd.DataFrame,
        hits: list[AnomalyHit],
        rules: dict[str, dict[str, Any]],
    ) -> pd.DataFrame:
        """处理模式：按用户配置替换异常值。

        Parameters
        ----------
        df : pd.DataFrame
            原始数据。
        hits : list[AnomalyHit]
            异常命中列表。
        rules : dict
            处理策略，格式: {"列名": {"strategy": "...", ...}}。

            strategy 类型：
            - "default_value": 替换为指定默认值 {"default": v}
            - "clip": 裁剪到 [min, max] 范围 {"min": x, "max": y}
            - "nan": 替换为 NaN
        """
        if not hits:
            return df

        result = df.copy()

        # 按 (行索引, 列名) 分组
        # 优先匹配列名规则，回退到 __all_numeric__ 通配规则
        fallback_rule = rules.get(ALL_NUMERIC_SENTINEL)
        for hit in hits:
            col_rule = rules.get(hit.column, fallback_rule)
            if col_rule is None:
                continue

            strategy = col_rule.get("strategy", "nan")
            idx = hit.row_index

            if idx not in result.index:
                continue

            if strategy == "default_value":
                result.at[idx, hit.column] = col_rule.get("default", 0)
            elif strategy == "clip":
                min_val = col_rule.get("min")
                max_val = col_rule.get("max")
                val = result.at[idx, hit.column]
                try:
                    val = float(val)
                    if min_val is not None:
                        val = max(val, min_val)
                    if max_val is not None:
                        val = min(val, max_val)
                    result.at[idx, hit.column] = val
                except (ValueError, TypeError):
                    pass
            elif strategy == "nan":
                result.at[idx, hit.column] = np.nan
            else:
                logger.warning("未知异常处理策略: %s", strategy)

        return result
