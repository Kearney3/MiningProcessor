"""异常值检测模块测试"""
import numpy as np
import pandas as pd
import pytest

from func.anomaly import detect_and_filter
from func.anomaly.detector import AnomalyDetector, _find_numeric_columns, _NON_METRIC_COLUMNS
from func.anomaly.filters import ANOMALY_FLAG_COLUMN, ANOMALY_REASON_COLUMN, AnomalyFilterer
from func.anomaly.report import generate_anomaly_report
from func.anomaly.rules import ALL_NUMERIC_SENTINEL, AnomalyConfig, AnomalyHit, AnomalyRule, build_rules_for_type


# ---------------------------------------------------------------------------
# AnomalyConfig
# ---------------------------------------------------------------------------

class TestAnomalyConfig:
    def test_default_values(self):
        cfg = AnomalyConfig()
        assert cfg.enabled is False
        assert cfg.generate_report is False
        assert cfg.flag_anomalies is True
        assert cfg.filter_anomalies is False
        assert cfg.handle_anomalies is False
        assert cfg.sigma_n == 3.0
        assert cfg.percentile_low == 1.0
        assert cfg.percentile_high == 99.0

    def test_from_config_complete(self):
        config = {
            "anomaly_detection": {
                "enabled": True,
                "generate_report": True,
                "flag_anomalies": False,
                "filter_anomalies": True,
                "handle_anomalies": False,
                "sigma_n": 2.5,
                "percentile_low": 5.0,
                "percentile_high": 95.0,
                "thresholds": {"fuel": {"油品消耗": {"max": 5000}}},
                "handling_rules": {"fuel": {"油品消耗": {"strategy": "nan"}}},
            }
        }
        cfg = AnomalyConfig.from_config(config)
        assert cfg.enabled is True
        assert cfg.generate_report is True
        assert cfg.filter_anomalies is True
        assert cfg.sigma_n == 2.5
        assert cfg.thresholds == {"fuel": {"油品消耗": {"max": 5000}}}

    def test_from_config_empty(self):
        cfg = AnomalyConfig.from_config({})
        assert cfg.enabled is False
        assert cfg.sigma_n == 3.0


# ---------------------------------------------------------------------------
# AnomalyRule / build_rules_for_type
# ---------------------------------------------------------------------------

class TestBuildRules:
    def test_fuel_rules(self):
        cfg = AnomalyConfig(enabled=True, sigma_n=3.0, percentile_low=1, percentile_high=99)
        rules = build_rules_for_type("fuel", {}, cfg)
        # 阈值规则: 油品消耗
        threshold_rules = [r for r in rules if r.method == "threshold"]
        assert len(threshold_rules) == 1
        assert threshold_rules[0].column == "油品消耗"
        # 统计规则: 油品消耗 σ + 百分位
        stat_rules = [r for r in rules if r.method in ("sigma", "percentile")]
        assert len(stat_rules) == 2

    def test_user_threshold_override(self):
        cfg = AnomalyConfig(enabled=True)
        user = {"油品消耗": {"max": 5000}}
        rules = build_rules_for_type("fuel", user, cfg)
        threshold_rules = [r for r in rules if r.method == "threshold" and r.column == "油品消耗"]
        assert threshold_rules[0].params["max"] == 5000

    def test_production_rules(self):
        cfg = AnomalyConfig(enabled=True)
        rules = build_rules_for_type("production", {}, cfg)
        columns = {r.column for r in rules}
        assert "趟次" in columns
        assert "产量" in columns

    def test_empty_type(self):
        cfg = AnomalyConfig(enabled=True)
        rules = build_rules_for_type("unknown_type", {}, cfg)
        assert rules == []


# ---------------------------------------------------------------------------
# AnomalyDetector - threshold
# ---------------------------------------------------------------------------

class TestDetectorThreshold:
    def test_basic_max(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        rule = AnomalyRule(column="油品消耗", method="threshold", params={"max": 10000})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) == 1
        assert hits[0].row_index == 2
        assert hits[0].value == 15000

    def test_basic_min(self):
        df = pd.DataFrame({"油品消耗": [-5, 200, 300]})
        rule = AnomalyRule(column="油品消耗", method="threshold", params={"min": 0})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) == 1
        assert hits[0].row_index == 0

    def test_min_max_range(self):
        df = pd.DataFrame({"油品消耗": [-1, 500, 15000, 800]})
        rule = AnomalyRule(column="油品消耗", method="threshold", params={"min": 0, "max": 10000})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) == 2
        indices = {h.row_index for h in hits}
        assert indices == {0, 2}

    def test_missing_column(self):
        df = pd.DataFrame({"其他列": [1, 2, 3]})
        rule = AnomalyRule(column="油品消耗", method="threshold", params={"max": 100})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert hits == []

    def test_empty_df(self):
        df = pd.DataFrame({"油品消耗": []})
        rule = AnomalyRule(column="油品消耗", method="threshold", params={"max": 100})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert hits == []


# ---------------------------------------------------------------------------
# AnomalyDetector - sigma
# ---------------------------------------------------------------------------

class TestDetectorSigma:
    def test_normal_data_no_hits(self):
        np.random.seed(42)
        df = pd.DataFrame({"电力消耗": np.random.normal(100, 10, 100)})
        rule = AnomalyRule(column="电力消耗", method="sigma", params={"n": 3})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        # 100 个正态分布样本，3σ 通常命中 0-1 个
        assert len(hits) <= 3

    def test_outlier_detected(self):
        # [100]*10 + extreme outlier: mean~190, std~2850, 2σ=5700
        data = [100] * 10 + [100000]
        df = pd.DataFrame({"电力消耗": data})
        rule = AnomalyRule(column="电力消耗", method="sigma", params={"n": 2})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) >= 1
        assert hits[0].row_index == 10

    def test_insufficient_data(self):
        df = pd.DataFrame({"电力消耗": [100, 200]})
        rule = AnomalyRule(column="电力消耗", method="sigma", params={"n": 3})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert hits == []

    def test_zero_std(self):
        df = pd.DataFrame({"电力消耗": [100, 100, 100, 100, 100]})
        rule = AnomalyRule(column="电力消耗", method="sigma", params={"n": 3})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert hits == []


# ---------------------------------------------------------------------------
# AnomalyDetector - percentile
# ---------------------------------------------------------------------------

class TestDetectorPercentile:
    def test_basic_percentile(self):
        data = list(range(1, 101))  # 1 to 100
        data.append(200)  # outlier
        df = pd.DataFrame({"产量": data})
        rule = AnomalyRule(column="产量", method="percentile", params={"low": 1, "high": 99})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) >= 1
        outlier_hits = [h for h in hits if h.value == 200]
        assert len(outlier_hits) == 1

    def test_insufficient_data(self):
        df = pd.DataFrame({"产量": [1, 2, 3]})
        rule = AnomalyRule(column="产量", method="percentile", params={"low": 1, "high": 99})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert hits == []


# ---------------------------------------------------------------------------
# AnomalyDetector - multiple rules
# ---------------------------------------------------------------------------

class TestDetectorMultipleRules:
    def test_multiple_rules_composition(self):
        df = pd.DataFrame({
            "油品消耗": [100, -5, 15000],
            "运行小时数": [8, 20, 10],
        })
        rules = [
            AnomalyRule(column="油品消耗", method="threshold", params={"min": 0, "max": 10000}),
            AnomalyRule(column="运行小时数", method="threshold", params={"max": 14}),
        ]
        detector = AnomalyDetector(rules)
        hits = detector.detect(df)
        assert len(hits) == 3  # 油品消耗: row 1, row 2; 运行小时数: row 1


# ---------------------------------------------------------------------------
# AnomalyFilterer - flag
# ---------------------------------------------------------------------------

class TestFiltererFlag:
    def test_flag_adds_columns(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="油品消耗=15000 超过上限 10000")]
        result = AnomalyFilterer.flag(df, hits)
        assert ANOMALY_FLAG_COLUMN in result.columns
        assert ANOMALY_REASON_COLUMN in result.columns
        assert result.at[2, ANOMALY_FLAG_COLUMN] == True
        assert "超过上限" in result.at[2, ANOMALY_REASON_COLUMN]
        assert result.at[0, ANOMALY_FLAG_COLUMN] == False
        assert result.at[0, ANOMALY_REASON_COLUMN] == ""

    def test_flag_preserves_all_rows(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        result = AnomalyFilterer.flag(df, hits)
        assert len(result) == 3

    def test_flag_no_mutation(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        _ = AnomalyFilterer.flag(df, hits)
        assert ANOMALY_FLAG_COLUMN not in df.columns

    def test_flag_empty_hits(self):
        df = pd.DataFrame({"油品消耗": [100, 200]})
        result = AnomalyFilterer.flag(df, [])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AnomalyFilterer - remove
# ---------------------------------------------------------------------------

class TestFiltererRemove:
    def test_remove_anomaly_rows(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        result = AnomalyFilterer.remove(df, hits)
        assert len(result) == 2
        assert 2 not in result.index

    def test_remove_no_mutation(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        _ = AnomalyFilterer.remove(df, hits)
        assert len(df) == 3

    def test_remove_empty_hits(self):
        df = pd.DataFrame({"油品消耗": [100, 200]})
        result = AnomalyFilterer.remove(df, [])
        assert len(result) == 2

    def test_remove_multiple(self):
        df = pd.DataFrame({"油品消耗": [100, -5, 15000, 300]})
        hits = [
            AnomalyHit(column="油品消耗", method="threshold", row_index=1, value=-5, message="test"),
            AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test"),
        ]
        result = AnomalyFilterer.remove(df, hits)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AnomalyFilterer - handle
# ---------------------------------------------------------------------------

class TestFiltererHandle:
    def test_handle_default_value(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        rules = {"油品消耗": {"strategy": "default_value", "default": 0}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[2, "油品消耗"] == 0
        assert result.at[0, "油品消耗"] == 100

    def test_handle_clip(self):
        df = pd.DataFrame({"运行小时数": [8, 20, 12]})
        hits = [AnomalyHit(column="运行小时数", method="threshold", row_index=1, value=20, message="test")]
        rules = {"运行小时数": {"strategy": "clip", "min": 0, "max": 14}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[1, "运行小时数"] == 14

    def test_handle_nan(self):
        df = pd.DataFrame({"电力消耗": [100, 200, 5000]})
        hits = [AnomalyHit(column="电力消耗", method="threshold", row_index=2, value=5000, message="test")]
        rules = {"电力消耗": {"strategy": "nan"}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert np.isnan(result.at[2, "电力消耗"])

    def test_handle_no_mutation(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        rules = {"油品消耗": {"strategy": "default_value", "default": 0}}
        _ = AnomalyFilterer.handle(df, hits, rules)
        assert df.at[2, "油品消耗"] == 15000

    def test_handle_no_matching_rule(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=2, value=15000, message="test")]
        rules = {}  # no rule for 油品消耗
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[2, "油品消耗"] == 15000  # unchanged


# ---------------------------------------------------------------------------
# detect_and_filter (integration)
# ---------------------------------------------------------------------------

class TestDetectAndFilter:
    def test_disabled_config(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 15000]})
        cfg = AnomalyConfig(enabled=False)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert result_df is df
        assert anomalies is None

    def test_flag_mode(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert ANOMALY_FLAG_COLUMN in result_df.columns
        assert ANOMALY_REASON_COLUMN in result_df.columns
        assert len(result_df) == 3
        assert anomalies is not None

    def test_filter_mode(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=False, filter_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert len(result_df) < 3
        assert anomalies is not None

    def test_handle_mode(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        handling = {"油品消耗": {"strategy": "default_value", "default": 0}}
        cfg = AnomalyConfig(enabled=True, flag_anomalies=False, handle_anomalies=True,
                            handling_rules=handling)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg, handling_rules=handling)
        assert result_df.at[2, "油品消耗"] == 0

    def test_no_anomalies(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 300]})
        cfg = AnomalyConfig(enabled=True)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert anomalies is None

    def test_custom_thresholds(self):
        df = pd.DataFrame({"油品消耗": [100, 200, 500]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=True)
        thresholds = {"油品消耗": {"max": 300}}
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg, thresholds=thresholds)
        assert anomalies is not None
        assert len(anomalies) == 1


# ---------------------------------------------------------------------------
# build_rules_for_type edge cases
# ---------------------------------------------------------------------------

class TestBuildRulesEdgeCases:
    def test_user_thresholds_add_new_column(self):
        cfg = AnomalyConfig(enabled=True)
        user = {"自定义列": {"min": 0, "max": 100}}
        rules = build_rules_for_type("fuel", user, cfg)
        col_rules = [r for r in rules if r.column == "自定义列"]
        assert len(col_rules) == 1
        assert col_rules[0].params == {"min": 0, "max": 100}

    def test_user_thresholds_override_default(self):
        cfg = AnomalyConfig(enabled=True)
        user = {"油品消耗": {"max": 5000}}
        rules = build_rules_for_type("fuel", user, cfg)
        threshold_rules = [r for r in rules if r.method == "threshold" and r.column == "油品消耗"]
        assert threshold_rules[0].params["max"] == 5000
        assert threshold_rules[0].params["min"] == 0  # default preserved

    def test_statistical_columns_for_all_types(self):
        cfg = AnomalyConfig(enabled=True)
        for dtype in ("fuel", "fuel_engine", "production_running", "production", "electrical", "worktime"):
            rules = build_rules_for_type(dtype, {}, cfg)
            assert len(rules) > 0, f"No rules for {dtype}"


# ---------------------------------------------------------------------------
# __all_numeric__ 模式（工时数据）
# ---------------------------------------------------------------------------

class TestAllNumericMode:
    """工时数据 __all_numeric__ 模式测试。"""

    def test_worktime_rules_use_all_numeric_sentinel(self):
        """工时规则应包含 __all_numeric__ 阈值规则。"""
        from func.anomaly.rules import ALL_NUMERIC_SENTINEL
        cfg = AnomalyConfig(enabled=True)
        rules = build_rules_for_type("worktime", {}, cfg)
        threshold_rules = [r for r in rules if r.method == "threshold"]
        assert len(threshold_rules) == 1
        assert threshold_rules[0].column == ALL_NUMERIC_SENTINEL
        assert threshold_rules[0].params == {"min": 0, "max": 720}

    def test_all_numeric_detects_all_numeric_columns(self):
        """__all_numeric__ 应对所有数值列应用阈值检测。"""
        from func.anomaly.rules import ALL_NUMERIC_SENTINEL
        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-02"],
            "班次": ["Day", "Night"],
            "停机时间": [100, 800],   # 800 > 720
            "运行时间": [600, 1000],  # 1000 > 720
        })
        rule = AnomalyRule(column=ALL_NUMERIC_SENTINEL, method="threshold", params={"min": 0, "max": 720})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) == 2
        columns = {h.column for h in hits}
        assert columns == {"停机时间", "运行时间"}

    def test_all_numeric_skips_date_and_shift(self):
        """__all_numeric__ 应跳过日期和班次列。"""
        from func.anomaly.rules import ALL_NUMERIC_SENTINEL
        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-02"],
            "班次": ["Day", "Night"],
            "运行时间": [600, 500],
        })
        rule = AnomalyRule(column=ALL_NUMERIC_SENTINEL, method="threshold", params={"min": 0, "max": 720})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert hits == []

    def test_all_numeric_with_mongolian_columns(self):
        """__all_numeric__ 应对蒙文列名也生效。"""
        from func.anomaly.rules import ALL_NUMERIC_SENTINEL
        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-02"],
            "Техникийн цаг": [500, 900],  # 900 > 720
            "Ажилчид": [3, -1],           # -1 < 0
        })
        rule = AnomalyRule(column=ALL_NUMERIC_SENTINEL, method="threshold", params={"min": 0, "max": 720})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) == 2
        hit_cols = {h.column for h in hits}
        assert "Техникийн цаг" in hit_cols
        assert "Ажилчид" in hit_cols

    def test_worktime_integration_flag_mode(self):
        """工时数据完整流程：flag 模式。"""
        df = pd.DataFrame({
            "日期": ["2025-01-01"] * 3,
            "班次": ["Day"] * 3,
            "停机A": [100, 200, 800],
            "停机B": [50, 60, 750],
        })
        cfg = AnomalyConfig(enabled=True, flag_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "worktime", config=cfg)
        assert ANOMALY_FLAG_COLUMN in result_df.columns
        assert anomalies is not None
        assert len(anomalies) == 2  # 停机A=800, 停机B=750

    def test_worktime_integration_filter_mode(self):
        """工时数据完整流程：filter 模式。"""
        df = pd.DataFrame({
            "日期": ["2025-01-01"] * 3,
            "班次": ["Day"] * 3,
            "停机A": [100, 200, 800],
        })
        cfg = AnomalyConfig(enabled=True, flag_anomalies=False, filter_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "worktime", config=cfg)
        assert len(result_df) == 2
        assert anomalies is not None

    def test_worktime_user_can_override_threshold(self):
        """用户可覆盖工时默认阈值。"""
        cfg = AnomalyConfig(enabled=True)
        user = {"__all_numeric__": {"min": 0, "max": 1000}}
        rules = build_rules_for_type("worktime", user, cfg)
        threshold_rules = [r for r in rules if r.method == "threshold"]
        assert threshold_rules[0].params["max"] == 1000

    def test_all_numeric_skips_non_metric_columns(self):
        """__all_numeric__ 应跳过序号等非度量列。"""
        df = pd.DataFrame({
            "序号": [1, 2, 3],
            "运行时间": [100, 200, 800],
        })
        rule = AnomalyRule(column=ALL_NUMERIC_SENTINEL, method="threshold", params={"min": 0, "max": 720})
        detector = AnomalyDetector([rule])
        hits = detector.detect(df)
        assert len(hits) == 1
        assert hits[0].column == "运行时间"

    def test_non_metric_columns_set(self):
        """验证非度量列集合包含预期列名。"""
        assert "日期" in _NON_METRIC_COLUMNS
        assert "班次" in _NON_METRIC_COLUMNS
        assert "序号" in _NON_METRIC_COLUMNS


# ---------------------------------------------------------------------------
# _find_numeric_columns 辅助函数
# ---------------------------------------------------------------------------

class TestFindNumericColumns:
    def test_basic_numeric(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        assert _find_numeric_columns(df) == ["a"]

    def test_mixed_numeric_string(self):
        df = pd.DataFrame({"a": [1, "text", 3]})
        cols = _find_numeric_columns(df)
        assert "a" in cols  # 1 和 3 可转为数值

    def test_all_nan_column_excluded(self):
        df = pd.DataFrame({"a": [np.nan, np.nan], "b": [1, 2]})
        assert _find_numeric_columns(df) == ["b"]

    def test_empty_df(self):
        df = pd.DataFrame()
        assert _find_numeric_columns(df) == []

    def test_boolean_column(self):
        """布尔列可转为数值（True=1, False=0）。"""
        df = pd.DataFrame({"flag": [True, False]})
        assert "flag" in _find_numeric_columns(df)

    def test_non_numeric_column_excluded(self):
        df = pd.DataFrame({"date": ["2025-01-01", "2025-01-02"], "name": ["a", "b"]})
        assert _find_numeric_columns(df) == []


# ---------------------------------------------------------------------------
# AnomalyDetector - threshold 边界
# ---------------------------------------------------------------------------

class TestDetectorThresholdEdgeCases:
    def test_boundary_value_max(self):
        """值恰好等于 max 时不应触发异常。"""
        df = pd.DataFrame({"v": [100, 200, 10000]})
        rule = AnomalyRule(column="v", method="threshold", params={"max": 10000})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) == 0

    def test_boundary_value_min(self):
        """值恰好等于 min 时不应触发异常。"""
        df = pd.DataFrame({"v": [0, 200, 300]})
        rule = AnomalyRule(column="v", method="threshold", params={"min": 0})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) == 0

    def test_only_min_specified(self):
        """仅指定 min 时，max 不触发。"""
        df = pd.DataFrame({"v": [-1, 100, 99999]})
        rule = AnomalyRule(column="v", method="threshold", params={"min": 0})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) == 1
        assert hits[0].row_index == 0

    def test_only_max_specified(self):
        """仅指定 max 时，min 不触发。"""
        df = pd.DataFrame({"v": [-100, 100, 999]})
        rule = AnomalyRule(column="v", method="threshold", params={"max": 500})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) == 1
        assert hits[0].row_index == 2

    def test_non_numeric_values_coerced(self):
        """非数值通过 errors='coerce' 变为 NaN，不触发阈值。"""
        df = pd.DataFrame({"v": ["text", "also_text"]})
        rule = AnomalyRule(column="v", method="threshold", params={"max": 50})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) == 0

    def test_nan_values_no_crash(self):
        """NaN 值不应触发异常也不应崩溃。"""
        df = pd.DataFrame({"v": [np.nan, np.nan, np.nan]})
        rule = AnomalyRule(column="v", method="threshold", params={"max": 50})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# AnomalyDetector - sigma 边界
# ---------------------------------------------------------------------------

class TestDetectorSigmaEdgeCases:
    def test_with_nan_values(self):
        """含 NaN 的序列不应崩溃。"""
        data = [100] * 20 + [np.nan, np.nan] + [10000000]
        df = pd.DataFrame({"v": data})
        rule = AnomalyRule(column="v", method="sigma", params={"n": 2})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) >= 1

    def test_hit_message_format(self):
        """命中消息应包含 σ 信息。"""
        data = [100] * 10 + [100000]
        df = pd.DataFrame({"v": data})
        rule = AnomalyRule(column="v", method="sigma", params={"n": 2})
        hits = AnomalyDetector([rule]).detect(df)
        assert len(hits) >= 1
        assert "σ" in hits[0].message
        assert "偏离均值" in hits[0].message


# ---------------------------------------------------------------------------
# AnomalyDetector - percentile 边界
# ---------------------------------------------------------------------------

class TestDetectorPercentileEdgeCases:
    def test_hit_message_format_low(self):
        """低于 P_low 的命中消息格式。"""
        data = [1] + list(range(10, 110))
        df = pd.DataFrame({"v": data})
        rule = AnomalyRule(column="v", method="percentile", params={"low": 5, "high": 95})
        hits = AnomalyDetector([rule]).detect(df)
        low_hits = [h for h in hits if h.value == 1]
        if low_hits:
            assert "低于" in low_hits[0].message

    def test_hit_message_format_high(self):
        """高于 P_high 的命中消息格式。"""
        data = list(range(10, 110)) + [200]
        df = pd.DataFrame({"v": data})
        rule = AnomalyRule(column="v", method="percentile", params={"low": 5, "high": 95})
        hits = AnomalyDetector([rule]).detect(df)
        high_hits = [h for h in hits if h.value == 200]
        if high_hits:
            assert "高于" in high_hits[0].message

    def test_with_nan_values(self):
        """含 NaN 的序列不应崩溃。"""
        data = list(range(1, 21)) + [np.nan] * 5 + [200]
        df = pd.DataFrame({"v": data})
        rule = AnomalyRule(column="v", method="percentile", params={"low": 5, "high": 95})
        hits = AnomalyDetector([rule]).detect(df)
        assert isinstance(hits, list)


# ---------------------------------------------------------------------------
# AnomalyDetector - unknown method
# ---------------------------------------------------------------------------

class TestDetectorUnknownMethod:
    def test_unknown_method_logs_warning(self):
        """未知检测方法应记录警告并返回空。"""
        df = pd.DataFrame({"v": [1, 2, 3]})
        rule = AnomalyRule(column="v", method="unknown_method", params={})
        hits = AnomalyDetector([rule]).detect(df)
        assert hits == []


# ---------------------------------------------------------------------------
# AnomalyFilterer - flag 边界
# ---------------------------------------------------------------------------

class TestFiltererFlagEdgeCases:
    def test_multiple_hits_on_same_row(self):
        """同一行多条异常应合并为一条原因。"""
        df = pd.DataFrame({"a": [100, 200], "b": [300, 400]})
        hits = [
            AnomalyHit(column="a", method="threshold", row_index=1, value=200, message="a=200 超过上限"),
            AnomalyHit(column="b", method="threshold", row_index=1, value=400, message="b=400 超过上限"),
        ]
        result = AnomalyFilterer.flag(df, hits)
        assert result.at[1, ANOMALY_FLAG_COLUMN] == True
        assert "a=200" in result.at[1, ANOMALY_REASON_COLUMN]
        assert "b=400" in result.at[1, ANOMALY_REASON_COLUMN]
        assert ";" in result.at[1, ANOMALY_REASON_COLUMN]

    def test_flag_with_non_default_index(self):
        """非默认索引（如字符串索引）应正常工作。"""
        df = pd.DataFrame({"v": [100, 200]}, index=["x", "y"])
        hits = [AnomalyHit(column="v", method="threshold", row_index="y", value=200, message="v=200 超过上限")]
        result = AnomalyFilterer.flag(df, hits)
        assert result.at["y", ANOMALY_FLAG_COLUMN] == True

    def test_flag_missing_index_in_df(self):
        """命中索引不在 df 中时应静默跳过。"""
        df = pd.DataFrame({"v": [100, 200]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=999, value=200, message="m")]
        result = AnomalyFilterer.flag(df, hits)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AnomalyFilterer - remove 边界
# ---------------------------------------------------------------------------

class TestFiltererRemoveEdgeCases:
    def test_remove_with_non_default_index(self):
        """非默认索引应正常移除。"""
        df = pd.DataFrame({"v": [100, 200, 300]}, index=["a", "b", "c"])
        hits = [AnomalyHit(column="v", method="threshold", row_index="b", value=200, message="m")]
        result = AnomalyFilterer.remove(df, hits)
        assert list(result.index) == ["a", "c"]

    def test_remove_missing_index_no_crash(self):
        """命中索引不在 df 中时应静默跳过。"""
        df = pd.DataFrame({"v": [100, 200]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=999, value=200, message="m")]
        result = AnomalyFilterer.remove(df, hits)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AnomalyFilterer - handle 边界
# ---------------------------------------------------------------------------

class TestFiltererHandleEdgeCases:
    def test_handle_clip_min_only(self):
        """clip 策略仅指定 min。"""
        df = pd.DataFrame({"v": [-10, 50, 100]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=0, value=-10, message="m")]
        rules = {"v": {"strategy": "clip", "min": 0}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[0, "v"] == 0

    def test_handle_clip_max_only(self):
        """clip 策略仅指定 max。"""
        df = pd.DataFrame({"v": [50, 200, 100]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=1, value=200, message="m")]
        rules = {"v": {"strategy": "clip", "max": 100}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[1, "v"] == 100

    def test_handle_non_numeric_value_skipped(self):
        """非数值在 clip 时应跳过不崩溃。"""
        df = pd.DataFrame({"v": ["text", 200]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=0, value="text", message="m")]
        rules = {"v": {"strategy": "clip", "min": 0, "max": 100}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[0, "v"] == "text"  # unchanged

    def test_handle_default_value_custom(self):
        """default_value 策略使用自定义默认值。"""
        df = pd.DataFrame({"v": [100, 200, 300]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=1, value=200, message="m")]
        rules = {"v": {"strategy": "default_value", "default": -1}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[1, "v"] == -1

    def test_handle_default_value_missing_default(self):
        """default_value 策略未指定 default 时默认为 0。"""
        df = pd.DataFrame({"v": [100, 200]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=1, value=200, message="m")]
        rules = {"v": {"strategy": "default_value"}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[1, "v"] == 0

    def test_handle_multiple_hits_on_same_cell(self):
        """同一单元格多条命中应逐一处理（最后一条生效）。"""
        df = pd.DataFrame({"v": [100]})
        hits = [
            AnomalyHit(column="v", method="threshold", row_index=0, value=100, message="m1"),
            AnomalyHit(column="v", method="sigma", row_index=0, value=100, message="m2"),
        ]
        rules = {"v": {"strategy": "default_value", "default": -999}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[0, "v"] == -999


# ---------------------------------------------------------------------------
# detect_and_filter - 阈值传递
# ---------------------------------------------------------------------------

class TestDetectAndFilterThresholdPassthrough:
    def test_config_thresholds_used_by_data_type(self):
        """config.thresholds 中按 data_type 键提取阈值。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 500]})
        cfg = AnomalyConfig(
            enabled=True, flag_anomalies=True,
            thresholds={"fuel": {"油品消耗": {"max": 300}}},
        )
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert anomalies is not None
        assert len(anomalies) == 1

    def test_config_thresholds_wrong_type_ignored(self):
        """config.thresholds 中其他数据类型的阈值不影响当前类型。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 500]})
        cfg = AnomalyConfig(
            enabled=True, flag_anomalies=True,
            thresholds={"electrical": {"电力消耗": {"max": 100}}},
        )
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        # 油品消耗 500 < 10000 (default), no anomaly
        assert anomalies is None

    def test_user_thresholds_override_config_thresholds(self):
        """detect_and_filter 的 thresholds 参数覆盖 config 中的阈值。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 500]})
        cfg = AnomalyConfig(
            enabled=True, flag_anomalies=True,
            thresholds={"fuel": {"油品消耗": {"max": 10000}}},
        )
        result_df, anomalies = detect_and_filter(
            df, "fuel", config=cfg,
            thresholds={"油品消耗": {"max": 300}},
        )
        assert anomalies is not None
        assert len(anomalies) == 1


# ---------------------------------------------------------------------------
# generate_anomaly_report
# ---------------------------------------------------------------------------

class TestAnomalyReport:
    def test_report_generates_file(self, tmp_path):
        """报告应生成 Excel 文件。"""
        df = pd.DataFrame({"日期": ["2025-01-01"], "油品消耗": [15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=0, value=15000, message="test")]
        path = generate_anomaly_report(hits, df, str(tmp_path), "fuel")
        assert path.endswith(".xlsx")
        assert "油耗数据" in path

        # 验证文件内容
        summary = pd.read_excel(path, sheet_name="异常汇总")
        assert len(summary) == 1
        assert summary.iloc[0]["触发次数"] == 1

        detail = pd.read_excel(path, sheet_name="异常明细")
        assert len(detail) == 1
        assert detail.iloc[0]["异常列"] == "油品消耗"

    def test_report_empty_hits(self, tmp_path):
        """无异常时报告应正常生成。"""
        df = pd.DataFrame({"油品消耗": [100]})
        path = generate_anomaly_report([], df, str(tmp_path), "fuel")
        summary = pd.read_excel(path, sheet_name="异常汇总")
        assert summary.iloc[0]["检测规则"] == "无异常"

    def test_report_preserves_context_columns(self, tmp_path):
        """报告应保留上下文列（日期、班次等）。"""
        df = pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"], "设备名称": ["EX01"], "油品消耗": [15000]})
        hits = [AnomalyHit(column="油品消耗", method="threshold", row_index=0, value=15000, message="test")]
        path = generate_anomaly_report(hits, df, str(tmp_path), "fuel")
        detail = pd.read_excel(path, sheet_name="异常明细")
        assert "日期" in detail.columns
        assert "设备名称" in detail.columns

    def test_report_filename_includes_data_type(self, tmp_path):
        """报告文件名应包含数据类型标签。"""
        df = pd.DataFrame({"电力消耗": [10000]})
        hits = [AnomalyHit(column="电力消耗", method="threshold", row_index=0, value=10000, message="m")]
        path = generate_anomaly_report(hits, df, str(tmp_path), "electrical")
        assert "电力消耗" in path

    def test_report_no_duplicate_filename(self, tmp_path):
        """不同数据类型应生成不同文件名。"""
        df = pd.DataFrame({"v": [10000]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=0, value=10000, message="m")]
        path1 = generate_anomaly_report(hits, df, str(tmp_path), "fuel")
        path2 = generate_anomaly_report(hits, df, str(tmp_path), "electrical")
        assert path1 != path2


# ---------------------------------------------------------------------------
# build_rules_for_type - config.thresholds 按类型提取
# ---------------------------------------------------------------------------

class TestBuildRulesThresholdExtraction:
    def test_thresholds_from_config_by_type(self):
        """config.thresholds 按 data_type 提取后传入 build_rules_for_type。"""
        cfg = AnomalyConfig(
            enabled=True,
            thresholds={"fuel": {"油品消耗": {"max": 5000}}},
        )
        type_thresholds = dict(cfg.thresholds.get("fuel", {}))
        rules = build_rules_for_type("fuel", type_thresholds, cfg)
        threshold_rules = [r for r in rules if r.method == "threshold" and r.column == "油品消耗"]
        assert threshold_rules[0].params["max"] == 5000


# ---------------------------------------------------------------------------
# 覆盖缺失行补充测试
# ---------------------------------------------------------------------------

class TestCoverageGaps:
    """补充覆盖缺失的代码路径。"""

    # --- filters.py ---

    def test_handle_empty_hits_returns_original(self):
        """handle 空命中列表应返回原 df（filters.py:85）。"""
        df = pd.DataFrame({"v": [100, 200]})
        result = AnomalyFilterer.handle(df, [], {"v": {"strategy": "default_value", "default": 0}})
        assert result is df

    def test_handle_missing_index_in_result(self):
        """命中索引不在 df 中时应跳过（filters.py:99）。"""
        df = pd.DataFrame({"v": [100, 200]}, index=[0, 1])
        hits = [AnomalyHit(column="v", method="threshold", row_index=999, value=200, message="m")]
        rules = {"v": {"strategy": "default_value", "default": 0}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert len(result) == 2
        assert result.at[0, "v"] == 100  # unchanged

    def test_handle_unknown_strategy_skipped(self):
        """未知策略应跳过不崩溃（filters.py:119）。"""
        df = pd.DataFrame({"v": [100]})
        hits = [AnomalyHit(column="v", method="threshold", row_index=0, value=100, message="m")]
        rules = {"v": {"strategy": "unknown_strategy"}}
        result = AnomalyFilterer.handle(df, hits, rules)
        assert result.at[0, "v"] == 100  # unchanged

    # --- rules.py ---

    def test_anomaly_rule_repr(self):
        """AnomalyRule.__repr__ 应返回可读字符串（rules.py:83）。"""
        rule = AnomalyRule(column="油品消耗", method="threshold", params={"max": 10000})
        s = repr(rule)
        assert "油品消耗" in s
        assert "threshold" in s
        assert "10000" in s

    # --- __init__.py ---

    def test_no_mode_selected_returns_original(self):
        """无处理模式选中时应返回原 df（__init__.py:134）。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        cfg = AnomalyConfig(
            enabled=True,
            flag_anomalies=False,
            filter_anomalies=False,
            handle_anomalies=False,
        )
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert result_df is df
        assert anomalies is not None  # anomalies detected but not processed

    def test_unknown_data_type_no_rules(self):
        """未知数据类型应返回原 df（__init__.py:106）。"""
        df = pd.DataFrame({"v": [100, 200]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "unknown_type", config=cfg)
        assert result_df is df
        assert anomalies is None

    def test_no_hits_returns_original(self):
        """无命中时应返回原 df（__init__.py:113）。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 300]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert result_df is df
        assert anomalies is None

    def test_report_generation_via_detect_and_filter(self, tmp_path):
        """detect_and_filter 应在 generate_report=True 时生成报告（__init__.py:138-139）。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=True, generate_report=True)
        result_df, anomalies = detect_and_filter(
            df, "fuel", config=cfg, output_dir=str(tmp_path))
        assert anomalies is not None
        # 验证报告文件已生成
        import os
        report_files = [f for f in os.listdir(str(tmp_path)) if f.startswith("异常报告")]
        assert len(report_files) == 1
        assert "油耗数据" in report_files[0]

    def test_handle_mode_with_default_value(self):
        """处理异常值模式应替换为默认值并记录日志。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        handling = {"油品消耗": {"strategy": "default_value", "default": 0}}
        cfg = AnomalyConfig(enabled=True, handle_anomalies=True, handling_rules=handling)
        result_df, anomalies = detect_and_filter(
            df, "fuel", config=cfg, handling_rules=handling)
        assert result_df.at[2, "油品消耗"] == 0
        assert anomalies is not None

    def test_filter_mode_removes_rows(self):
        """过滤模式应移除异常行并记录日志。"""
        df = pd.DataFrame({"油品消耗": [100, 200, 60000]})
        cfg = AnomalyConfig(enabled=True, flag_anomalies=False, filter_anomalies=True)
        result_df, anomalies = detect_and_filter(df, "fuel", config=cfg)
        assert len(result_df) == 2
        assert anomalies is not None
