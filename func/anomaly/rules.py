"""异常检测规则定义

规则类型：
- threshold: 绝对阈值（用户配置的 min/max）
- sigma: σ 异常（基于标准差）
- percentile: 百分位异常
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

class AnomalyConfig:
    """异常检测配置，从 config_loader 加载或手动构造。"""

    __slots__ = (
        "enabled", "generate_report", "flag_anomalies",
        "filter_anomalies", "handle_anomalies",
        "use_threshold", "use_sigma", "use_percentile",
        "sigma_n", "percentile_low", "percentile_high",
        "thresholds", "handling_rules",
    )

    def __init__(
        self,
        *,
        enabled: bool = False,
        generate_report: bool = False,
        flag_anomalies: bool = True,
        filter_anomalies: bool = False,
        handle_anomalies: bool = False,
        use_threshold: bool = True,
        use_sigma: bool = True,
        use_percentile: bool = True,
        sigma_n: float = 3.0,
        percentile_low: float = 1.0,
        percentile_high: float = 99.0,
        thresholds: dict[str, dict[str, float]] | None = None,
        handling_rules: dict[str, dict[str, Any]] | None = None,
    ):
        self.enabled = enabled
        self.generate_report = generate_report
        self.flag_anomalies = flag_anomalies
        self.filter_anomalies = filter_anomalies
        self.handle_anomalies = handle_anomalies
        self.use_threshold = use_threshold
        self.use_sigma = use_sigma
        self.use_percentile = use_percentile
        self.sigma_n = sigma_n
        self.percentile_low = percentile_low
        self.percentile_high = percentile_high
        self.thresholds = thresholds or {}
        self.handling_rules = handling_rules or {}

    @classmethod
    def from_config(cls, config: dict) -> "AnomalyConfig":
        """从 config_loader.load_config() 返回的配置构造。"""
        ad = config.get("anomaly_detection", {})
        return cls(
            enabled=ad.get("enabled", False),
            generate_report=ad.get("generate_report", False),
            flag_anomalies=ad.get("flag_anomalies", True),
            filter_anomalies=ad.get("filter_anomalies", False),
            handle_anomalies=ad.get("handle_anomalies", False),
            use_threshold=ad.get("use_threshold", True),
            use_sigma=ad.get("use_sigma", True),
            use_percentile=ad.get("use_percentile", True),
            sigma_n=ad.get("sigma_n", 3.0),
            percentile_low=ad.get("percentile_low", 1.0),
            percentile_high=ad.get("percentile_high", 99.0),
            thresholds=ad.get("thresholds", {}),
            handling_rules=ad.get("handling_rules", {}),
        )


# ---------------------------------------------------------------------------
# 规则与命中
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnomalyRule:
    """单条异常检测规则。"""
    column: str
    method: str   # "threshold" | "sigma" | "percentile"
    params: dict   # 方法参数，如 {"max": 10000} 或 {"n": 3}

    def __repr__(self):
        return f"AnomalyRule({self.column!r}, {self.method}, {self.params})"


@dataclass(frozen=True)
class AnomalyHit:
    """一条异常命中记录。"""
    column: str
    method: str
    row_index: Any    # DataFrame index value
    value: Any
    message: str


# ---------------------------------------------------------------------------
# 默认阈值（各数据类型的推荐值）
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS: dict[str, dict[str, dict[str, float]]] = {
    "fuel": {
        "油品消耗": {"min": 0, "max": 50000},
    },
    "fuel_engine": {
        "发动机小时数开始": {"min": 0},
        "发动机小时数结束": {"min": 0},
        "运行小时数": {"min": 0, "max": 14},
    },
    "production_running": {
        "运行里程": {"min": 0, "max": 500},
        "运行小时数": {"min": 0, "max": 14},
        "趟次": {"min": 0, "max": 50},
    },
    "production": {
        "趟次": {"min": 0, "max": 50},
        "产量": {"min": 0, "max": 50000},
    },
    "electrical": {
        "电力消耗": {"min": 0, "max": 50000},
    },
    "worktime": {
        "__all_numeric__": {"min": 0, "max": 720},
    },
}

# 特殊标记：对 DataFrame 中所有数值列应用阈值检测
ALL_NUMERIC_SENTINEL = "__all_numeric__"


# ---------------------------------------------------------------------------
# 规则工厂
# ---------------------------------------------------------------------------

# 每个数据类型中可用于统计检测的数值列
_STATISTICAL_COLUMNS: dict[str, list[str]] = {
    "fuel": ["油品消耗"],
    "fuel_engine": ["运行小时数"],
    "production_running": ["运行里程", "运行小时数", "趟次"],
    "production": ["趟次", "产量"],
    "electrical": ["电力消耗"],
    "worktime": [],  # 工时数据使用 __all_numeric__ 模式，不指定具体列
}


def build_rules_for_type(
    data_type: str,
    user_thresholds: dict[str, dict[str, float]],
    config: AnomalyConfig,
) -> list[AnomalyRule]:
    """为指定数据类型构建规则列表。

    合并默认阈值和用户自定义阈值，并添加统计检测规则。
    根据 config 中的 use_threshold/use_sigma/use_percentile 开关过滤。
    """
    rules: list[AnomalyRule] = []

    # 1. 合并阈值：默认值 + 用户覆盖
    merged = dict(DEFAULT_THRESHOLDS.get(data_type, {}))
    for col, bounds in user_thresholds.items():
        if col in merged:
            merged[col] = {**merged[col], **bounds}
        else:
            merged[col] = bounds

    # 2. 阈值规则（受 use_threshold 开关控制）
    if config.use_threshold:
        for col, bounds in merged.items():
            if bounds:
                rules.append(AnomalyRule(column=col, method="threshold", params=dict(bounds)))

    # 3. 统计规则（σ + 百分位，分别受开关控制）
    stat_cols = _STATISTICAL_COLUMNS.get(data_type, [])
    for col in stat_cols:
        if config.use_sigma:
            rules.append(AnomalyRule(
                column=col, method="sigma", params={"n": config.sigma_n},
            ))
        if config.use_percentile:
            rules.append(AnomalyRule(
                column=col, method="percentile",
                params={"low": config.percentile_low, "high": config.percentile_high},
            ))

    return rules
