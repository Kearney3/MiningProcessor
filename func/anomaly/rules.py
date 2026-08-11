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
        "thresholds", "statistical_columns", "handling_rules",
        "_anomaly_counts", "_anomaly_records",
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
        statistical_columns: dict[str, dict[str, Any]] | None = None,
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
        self.statistical_columns = statistical_columns or {}
        self.handling_rules = handling_rules or {}
        self._anomaly_counts: list[tuple[str, int]] | None = None
        # 运行时收集异常明细，供 GUI 表格展示；不参与检测规则计算。
        self._anomaly_records: list[dict] | None = None

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
            statistical_columns=ad.get("statistical_columns", {}),
            handling_rules=ad.get("handling_rules", {}),
        )

    @classmethod
    def build_from_ui(
        cls,
        enabled: bool = False,
        generate_report: bool = False,
        mode: str = "flag",
    ) -> "AnomalyConfig":
        """从 UI 参数构建 AnomalyConfig，逐列检测阈值从 config.user.json 读取。

        共享入口，供 Flet GUI 和 Tauri bridge 统一使用。

        Args:
            enabled: 是否启用异常检测
            generate_report: 是否生成异常报告
            mode: 处理模式 ("flag" | "filter" | "handle")

        Returns:
            AnomalyConfig 实例；enabled=False 时返回 disabled config
        """
        if not enabled:
            return cls(enabled=False)

        from func.config_loader import get_anomaly_detection_config
        ad_config = get_anomaly_detection_config()

        return cls(
            enabled=True,
            generate_report=generate_report,
            flag_anomalies=(mode == "flag"),
            filter_anomalies=(mode == "filter"),
            handle_anomalies=(mode == "handle"),
            use_threshold=ad_config.get("use_threshold", True),
            use_sigma=ad_config.get("use_sigma", True),
            use_percentile=ad_config.get("use_percentile", True),
            sigma_n=ad_config.get("sigma_n", 3.0),
            percentile_low=ad_config.get("percentile_low", 1.0),
            percentile_high=ad_config.get("percentile_high", 99.0),
            thresholds=ad_config.get("thresholds", {}),
            statistical_columns=ad_config.get("statistical_columns", {}),
            handling_rules=ad_config.get("handling_rules", {}),
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
    每项列名/标记可通过 ``"enabled": false`` 关闭。
    """
    rules: list[AnomalyRule] = []

    # 1. 合并阈值：默认值 + 用户覆盖
    merged = dict(DEFAULT_THRESHOLDS.get(data_type, {}))
    for col, bounds in user_thresholds.items():
        if col in merged:
            merged[col] = {**merged[col], **bounds}
        else:
            merged[col] = bounds

    # 2. 阈值规则（受 use_threshold 开关和 per-column enabled 控制）
    if config.use_threshold:
        for col, bounds in merged.items():
            if not bounds.get("enabled", True):
                continue
            # 去掉 enabled 元数据，只保留 min/max 等阈值参数
            rule_params = {k: v for k, v in bounds.items() if k != "enabled"}
            if rule_params:
                rules.append(AnomalyRule(column=col, method="threshold", params=rule_params))

    # 3. 统计规则（σ + 百分位，分别受开关和 per-column enabled 控制）
    #    stat_cols 来自 config.statistical_columns（config_loader 提供），
    #    若配置中无此字段则回退到模块级 _STATISTICAL_COLUMNS。
    cfg_stat: dict[str, dict[str, Any]] = getattr(config, "statistical_columns", None) or {}
    stat_cfg = cfg_stat.get(data_type) or _STATISTICAL_COLUMNS.get(data_type, {})
    stat_cols: list[str] = []
    if isinstance(stat_cfg, dict):
        for col, col_cfg in stat_cfg.items():
            if isinstance(col_cfg, dict):
                if col_cfg.get("enabled", True):
                    stat_cols.append(col)
            else:
                stat_cols.append(col)
    else:
        # 旧格式 list[str]：全部启用
        stat_cols = list(stat_cfg)

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
