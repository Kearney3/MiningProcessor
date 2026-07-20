"""异常值检测引擎

对 DataFrame 应用规则列表，输出 AnomalyHit 列表。
检测方法：阈值（min/max）、σ 异常、百分位异常。
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from func.anomaly.rules import ALL_NUMERIC_SENTINEL, AnomalyHit, AnomalyRule

logger = logging.getLogger(__name__)


def _find_numeric_columns(df: pd.DataFrame) -> list[str]:
    """找到 DataFrame 中所有可转为数值的列（排除纯 NaN 列）。"""
    cols = []
    for col in df.columns:
        series = pd.to_numeric(df[col], errors="coerce")
        if not series.isna().all():
            cols.append(col)
    return cols


# 非度量列：这些列即使包含数值也不参与异常检测
_NON_METRIC_COLUMNS = frozenset({"日期", "班次", "序号"})


class AnomalyDetector:
    """应用规则到 DataFrame，输出 AnomalyHit 列表。"""

    __slots__ = ("_rules",)

    def __init__(self, rules: list[AnomalyRule]):
        self._rules = tuple(rules)

    def detect(self, df: pd.DataFrame) -> list[AnomalyHit]:
        """对 df 应用所有规则，返回命中列表。"""
        if df.empty or not self._rules:
            return []

        hits: list[AnomalyHit] = []
        for rule in self._rules:
            # __all_numeric__ 模式：对所有数值列应用同一规则
            if rule.column == ALL_NUMERIC_SENTINEL:
                for col in _find_numeric_columns(df):
                    if col in _NON_METRIC_COLUMNS:
                        continue
                    expanded = AnomalyRule(column=col, method=rule.method, params=rule.params)
                    series = pd.to_numeric(df[col], errors="coerce")
                    hits.extend(self._apply_rule(df, series, expanded))
                continue

            if rule.column not in df.columns:
                continue

            series = pd.to_numeric(df[rule.column], errors="coerce")
            hits.extend(self._apply_rule(df, series, rule))

        return hits

    def _apply_rule(
        self, df: pd.DataFrame, series: pd.Series, rule: AnomalyRule
    ) -> list[AnomalyHit]:
        """对单列应用单条规则。"""
        if series.isna().all():
            return []

        if rule.method == "threshold":
            return self._check_threshold(df, series, rule)
        elif rule.method == "sigma":
            return self._check_sigma(df, series, rule)
        elif rule.method == "percentile":
            return self._check_percentile(df, series, rule)
        else:
            logger.warning("未知检测方法: %s", rule.method)
            return []

    # ------------------------------------------------------------------
    # 阈值检测
    # ------------------------------------------------------------------

    @staticmethod
    def _check_threshold(
        df: pd.DataFrame, series: pd.Series, rule: AnomalyRule
    ) -> list[AnomalyHit]:
        """绝对阈值检测：值超出 [min, max] 范围。"""
        hits: list[AnomalyHit] = []
        min_val = rule.params.get("min")
        max_val = rule.params.get("max")

        mask = pd.Series(False, index=df.index)
        if min_val is not None:
            mask = mask | (series < min_val)
        if max_val is not None:
            mask = mask | (series > max_val)

        for idx in df[mask].index:
            val = series[idx]
            bounds_desc = []
            if min_val is not None and val < min_val:
                bounds_desc.append(f"低于下限 {min_val}")
            if max_val is not None and val > max_val:
                bounds_desc.append(f"超过上限 {max_val}")
            message = f"{rule.column}={val} {'且'.join(bounds_desc)}"
            hits.append(AnomalyHit(
                column=rule.column, method="threshold",
                row_index=idx, value=val, message=message,
            ))

        return hits

    # ------------------------------------------------------------------
    # σ 异常检测
    # ------------------------------------------------------------------

    @staticmethod
    def _check_sigma(
        df: pd.DataFrame, series: pd.Series, rule: AnomalyRule
    ) -> list[AnomalyHit]:
        """σ 异常检测：|x - μ| > n * σ。"""
        hits: list[AnomalyHit] = []
        n = rule.params.get("n", 3.0)

        valid = series.dropna()
        if len(valid) < 3:
            return hits

        mu = valid.mean()
        sigma = valid.std()
        if sigma == 0 or np.isnan(sigma):
            return hits

        threshold = n * sigma
        mask = (series - mu).abs() > threshold

        for idx in df[mask].index:
            val = series[idx]
            deviation = abs(val - mu) / sigma
            message = f"{rule.column}={val} 偏离均值 {deviation:.1f}σ (μ={mu:.1f}, σ={sigma:.1f})"
            hits.append(AnomalyHit(
                column=rule.column, method="sigma",
                row_index=idx, value=val, message=message,
            ))

        return hits

    # ------------------------------------------------------------------
    # 百分位异常检测
    # ------------------------------------------------------------------

    @staticmethod
    def _check_percentile(
        df: pd.DataFrame, series: pd.Series, rule: AnomalyRule
    ) -> list[AnomalyHit]:
        """百分位异常检测：值低于 P_low 或高于 P_high。"""
        hits: list[AnomalyHit] = []
        low_pct = rule.params.get("low", 1.0)
        high_pct = rule.params.get("high", 99.0)

        valid = series.dropna()
        if len(valid) < 5:
            return hits

        p_low = np.percentile(valid, low_pct)
        p_high = np.percentile(valid, high_pct)

        mask = (series < p_low) | (series > p_high)

        for idx in df[mask].index:
            val = series[idx]
            if val < p_low:
                message = f"{rule.column}={val} 低于 P{low_pct:.0f} ({p_low:.1f})"
            else:
                message = f"{rule.column}={val} 高于 P{high_pct:.0f} ({p_high:.1f})"
            hits.append(AnomalyHit(
                column=rule.column, method="percentile",
                row_index=idx, value=val, message=message,
            ))

        return hits
