"""异常值检测与处理模块

提供三种检测方式：
- 绝对阈值：用户配置的 min/max 范围
- σ 异常：基于标准差的统计离群检测
- 百分位：基于百分位数的极端值检测

四种处理模式：
- 输出报告：仅生成异常报告 Excel
- 标记异常值：DataFrame 新增「异常值」和「异常值原因」列
- 过滤异常值：移除异常行
- 处理异常值：按用户配置替换异常值
"""
import logging

from func.anomaly.detector import AnomalyDetector
from func.anomaly.filters import (
    ANOMALY_FLAG_COLUMN,
    ANOMALY_REASON_COLUMN,
    AnomalyFilterer,
)
from func.anomaly.report import generate_anomaly_report
from func.anomaly.rules import (
    ALL_NUMERIC_SENTINEL,
    AnomalyConfig,
    AnomalyHit,
    AnomalyRule,
    build_rules_for_type,
)

__all__ = [
    "ALL_NUMERIC_SENTINEL",
    "ANOMALY_FLAG_COLUMN",
    "ANOMALY_REASON_COLUMN",
    "AnomalyConfig",
    "AnomalyDetector",
    "AnomalyFilterer",
    "AnomalyHit",
    "AnomalyRule",
    "build_rules_for_type",
    "detect_and_filter",
    "generate_anomaly_report",
]

_logger = logging.getLogger(__name__)

# 数据类型中文标签
_DATA_TYPE_LABELS: dict[str, str] = {
    "fuel": "油耗信息",
    "fuel_engine": "设备信息",
    "production_running": "运行数据",
    "production": "生产数据",
    "electrical": "电力消耗",
    "worktime": "工时数据",
}


def detect_and_filter(
    df,
    data_type,
    config=None,
    thresholds=None,
    handling_rules=None,
    output_dir=None,
):
    """一站式异常值检测与处理。

    Parameters
    ----------
    df : pd.DataFrame
        待检测的数据。
    data_type : str
        数据类型: "fuel", "fuel_engine", "production_running",
        "production", "electrical", "worktime"。
    config : AnomalyConfig, optional
        异常检测配置。为 None 时从 config_loader 加载。
    thresholds : dict, optional
        用户配置的绝对阈值，格式: {"列名": {"min": x, "max": y}}。
    handling_rules : dict, optional
        处理异常值的策略，格式: {"列名": {"strategy": "default_value", "default": v}}。
    output_dir : str, optional
        报告输出目录。为 None 时使用数据文件所在目录。

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame | None]
        (result_df, anomalies_df)。
        result_df: 根据模式处理后的 DataFrame。
        anomalies_df: 异常明细（供报告；无异常时为 None）。
    """
    from func import config_loader

    if config is None:
        config = AnomalyConfig.from_config(config_loader.load_config())

    if not config.enabled:
        return df, None

    # 构建规则：从 config.thresholds 中提取当前 data_type 的阈值，再合并用户传入的
    type_thresholds = dict(config.thresholds.get(data_type, {}))
    if thresholds:
        type_thresholds.update(thresholds)

    rules = build_rules_for_type(data_type, type_thresholds, config)
    if not rules:
        return df, None

    # 检测
    detector = AnomalyDetector(rules)
    hits = detector.detect(df)

    if not hits:
        return df, None

    # 统计受影响的行数（去重）
    affected_rows = len({h.row_index for h in hits})
    label = _DATA_TYPE_LABELS.get(data_type, data_type)
    _logger.info("[%s] 检测到 %d 个异常值（共 %d 条数据）", label, affected_rows, len(df))

    # 构建异常明细 DataFrame
    anomalies_df = _build_anomalies_df(df, hits)

    # 处理
    effective_rules = handling_rules or config.handling_rules
    # config.handling_rules 按数据类型嵌套，需提取当前类型的规则
    if effective_rules and data_type in effective_rules:
        effective_rules = effective_rules[data_type]
    if config.handle_anomalies and effective_rules:
        result_df = AnomalyFilterer.handle(df, hits, effective_rules)
        _logger.info("[%s] 异常值已设置为默认值", label)
    elif config.filter_anomalies:
        result_df = AnomalyFilterer.remove(df, hits)
        _logger.info("[%s] 已过滤 %d 条异常数据", label, affected_rows)
    elif config.flag_anomalies:
        result_df = AnomalyFilterer.flag(df, hits)
        _logger.info("[%s] 异常值已标记", label)
    else:
        result_df = df

    # 生成报告
    if config.generate_report and output_dir:
        report_path = generate_anomaly_report(hits, df, output_dir, data_type)
        _logger.info("异常报告已生成: %s", report_path)

    return result_df, anomalies_df


def _build_anomalies_df(df, hits):
    """根据检测结果构建异常明细 DataFrame。"""
    import pandas as pd

    rows = []
    for hit in hits:
        row = {"行号": hit.row_index, "异常列": hit.column, "异常值": hit.value,
               "检测方法": hit.method, "说明": hit.message}
        # 保留原始行的关键信息
        for col in ("日期", "班次", "设备名称", "设备编号"):
            if col in df.columns and hit.row_index in df.index:
                row[col] = df.at[hit.row_index, col]
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
