"""Tests for the table merge (表内合并) feature in excel_batch.py"""
import pandas as pd
import pytest
from func.excel_batch import (
    _add_default_shift,
    _aggregate_production_data,
    _left_merge,
)


# ---------------------------------------------------------------------------
# _add_default_shift
# ---------------------------------------------------------------------------

class TestAddDefaultShift:
    def test_adds_shift_to_sheet_without_column(self):
        sheets = {"电力消耗": pd.DataFrame({"日期": ["2025-01-01"], "设备名称": ["EX-001"], "电量": [100]})}
        result = _add_default_shift(sheets, "Night")
        assert "班次" in result["电力消耗"].columns
        assert result["电力消耗"]["班次"].iloc[0] == "Night"

    def test_does_not_overwrite_existing_shift(self):
        sheets = {"工时数据": pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"], "设备名称": ["CAT785"]})}
        result = _add_default_shift(sheets, "Night")
        assert result["工时数据"]["班次"].iloc[0] == "Day"

    def test_custom_default_value(self):
        sheets = {"test": pd.DataFrame({"col": [1]})}
        result = _add_default_shift(sheets, "Day")
        assert result["test"]["班次"].iloc[0] == "Day"

    def test_multiple_sheets(self):
        sheets = {
            "has_shift": pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"]}),
            "no_shift": pd.DataFrame({"日期": ["2025-01-01"], "设备名称": ["EX-001"]}),
        }
        result = _add_default_shift(sheets, "Night")
        assert result["has_shift"]["班次"].iloc[0] == "Day"
        assert result["no_shift"]["班次"].iloc[0] == "Night"


# ---------------------------------------------------------------------------
# _aggregate_production_data
# ---------------------------------------------------------------------------

class TestAggregateProductionData:
    def _make_prod_sheets(self, rows):
        """Helper to create production sheets dict."""
        prod_df = pd.DataFrame(rows)
        return {"生产数据": prod_df}

    def test_basic_aggregation(self):
        """Truck rows aggregate ore types into columns."""
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "CAT785", "挖机名称": "EX1",
             "矿石类型": "矿石A", "运次": 3, "产量": 90, "标准设备名称（矿卡）": "CAT785-01",
             "标准设备名称（挖机）": "EX1-01"},
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "CAT785", "挖机名称": "EX1",
             "矿石类型": "矿石B", "运次": 1, "产量": 30, "标准设备名称（矿卡）": "CAT785-01",
             "标准设备名称（挖机）": "EX1-01"},
        ]
        result = _aggregate_production_data(self._make_prod_sheets(rows))
        assert result is not None
        assert "标准设备名称" in result.columns
        assert "运次" in result.columns
        # Should have 2 rows: 1 truck + 1 excavator
        assert len(result) == 2

    def test_truck_trip_sum(self):
        """Truck trips are summed across all excavators and ore types."""
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T1", "挖机名称": "E1",
             "矿石类型": "A", "运次": 3, "产量": 90, "标准设备名称（矿卡）": "T1",
             "标准设备名称（挖机）": "E1"},
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T1", "挖机名称": "E2",
             "矿石类型": "A", "运次": 2, "产量": 60, "标准设备名称（矿卡）": "T1",
             "标准设备名称（挖机）": "E2"},
        ]
        result = _aggregate_production_data(self._make_prod_sheets(rows))
        truck_rows = result[result["标准设备名称"] == "T1"]
        assert len(truck_rows) == 1
        assert truck_rows["运次"].iloc[0] == 5  # 3 + 2

    def test_excavator_trip_sum(self):
        """Excavator trips are summed across all trucks."""
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T1", "挖机名称": "E1",
             "矿石类型": "A", "运次": 3, "产量": 90, "标准设备名称（矿卡）": "T1",
             "标准设备名称（挖机）": "E1"},
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T2", "挖机名称": "E1",
             "矿石类型": "A", "运次": 2, "产量": 60, "标准设备名称（矿卡）": "T2",
             "标准设备名称（挖机）": "E1"},
        ]
        result = _aggregate_production_data(self._make_prod_sheets(rows))
        excavator_rows = result[result["标准设备名称"] == "E1"]
        assert len(excavator_rows) == 1
        assert excavator_rows["运次"].iloc[0] == 5  # 3 + 2

    def test_ore_type_columns(self):
        """Different ore types become separate columns."""
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T1", "挖机名称": "E1",
             "矿石类型": "矿石A", "运次": 3, "产量": 90, "标准设备名称（矿卡）": "T1",
             "标准设备名称（挖机）": "E1"},
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T1", "挖机名称": "E1",
             "矿石类型": "矿石B", "运次": 1, "产量": 30, "标准设备名称（矿卡）": "T1",
             "标准设备名称（挖机）": "E1"},
        ]
        result = _aggregate_production_data(self._make_prod_sheets(rows))
        assert "矿石A" in result.columns
        assert "矿石B" in result.columns

    def test_empty_production(self):
        """Returns None when production sheet is empty."""
        result = _aggregate_production_data({"生产数据": pd.DataFrame()})
        assert result is None

    def test_missing_production_sheet(self):
        """Returns None when production sheet doesn't exist."""
        result = _aggregate_production_data({"运行数据": pd.DataFrame({"x": [1]})})
        assert result is None

    def test_fallback_to_original_names(self):
        """Falls back to 矿卡名称/挖机名称 when standard names missing."""
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "矿卡名称": "T1", "挖机名称": "E1",
             "矿石类型": "A", "运次": 2, "产量": 60},
        ]
        result = _aggregate_production_data(self._make_prod_sheets(rows))
        assert result is not None
        assert len(result) == 2  # 1 truck + 1 excavator


# ---------------------------------------------------------------------------
# _left_merge
# ---------------------------------------------------------------------------

class TestLeftMerge:
    def test_basic_merge(self):
        base = pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"], "标准设备名称": ["T1"], "a": [1]})
        right = pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"], "标准设备名称": ["T1"], "b": [2]})
        result = _left_merge(base, right, "test", ["日期", "班次", "标准设备名称"])
        assert "b" in result.columns
        assert len(result) == 1
        assert result["b"].iloc[0] == 2

    def test_no_match_preserves_base_rows(self):
        """Left merge keeps all base rows even when no match."""
        base = pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"], "标准设备名称": ["T1"], "a": [1]})
        right = pd.DataFrame({"日期": ["2025-01-01"], "班次": ["Day"], "标准设备名称": ["T999"], "b": [2]})
        result = _left_merge(base, right, "test", ["日期", "班次", "标准设备名称"])
        assert len(result) == 1
        assert pd.isna(result["b"].iloc[0])

    def test_semantic_suffix_on_conflict(self):
        """Conflicting non-key columns get semantic suffix."""
        base = pd.DataFrame({"日期": ["2025-01-01"], "标准设备名称": ["T1"], "电量": [100]})
        right = pd.DataFrame({"日期": ["2025-01-01"], "标准设备名称": ["T1"], "电量": [200]})
        result = _left_merge(base, right, "电力", ["日期", "标准设备名称"])
        assert "电量" in result.columns
        assert "电量_电力" in result.columns
        assert result["电量"].iloc[0] == 100
        assert result["电量_电力"].iloc[0] == 200

    def test_ledger_duplicates_dropped(self):
        """标准设备编号 and 标准公司名称 from right are dropped."""
        base = pd.DataFrame({
            "日期": ["2025-01-01"], "标准设备名称": ["T1"],
            "标准设备编号": ["ID001"], "标准公司名称": ["公司A"],
        })
        right = pd.DataFrame({
            "日期": ["2025-01-01"], "标准设备名称": ["T1"],
            "标准设备编号": ["ID002"], "标准公司名称": ["公司B"],
            "其他数据": [42],
        })
        result = _left_merge(base, right, "test", ["日期", "标准设备名称"])
        # 标准设备编号 and 标准公司名称 should only appear once (from base)
        assert result.columns.tolist().count("标准设备编号") == 1
        assert result.columns.tolist().count("标准公司名称") == 1
        assert "其他数据" in result.columns

    def test_merge_multiple_rows(self):
        """1:N merge when right has multiple matching rows."""
        base = pd.DataFrame({"日期": ["2025-01-01"], "标准设备名称": ["T1"], "a": [1]})
        right = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-01"],
            "标准设备名称": ["T1", "T1"],
            "b": [10, 20],
        })
        result = _left_merge(base, right, "test", ["日期", "标准设备名称"])
        assert len(result) == 2  # base row duplicated


# ---------------------------------------------------------------------------
# _aggregate_fuel_data
# ---------------------------------------------------------------------------

from func.excel_batch import _aggregate_fuel_data, _reorder_columns


class TestAggregateFuelData:
    def _make_fuel_sheets(self, rows):
        return {"油耗信息": pd.DataFrame(rows)}

    def test_basic_aggregation(self):
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "标准设备名称": "CAT785-01",
             "设备名称": "CAT785", "设备编号": "T001", "油品消耗": 100},
            {"日期": "2025-01-01", "班次": "Day", "标准设备名称": "CAT785-01",
             "设备名称": "CAT785", "设备编号": "T001", "油品消耗": 50},
        ]
        result = _aggregate_fuel_data(self._make_fuel_sheets(rows))
        assert result is not None
        assert len(result) == 1
        assert result["油品消耗"].iloc[0] == 150  # summed

    def test_preserves_device_info(self):
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "标准设备名称": "CAT785-01",
             "设备名称": "CAT785", "设备编号": "T001", "油品消耗": 100},
        ]
        result = _aggregate_fuel_data(self._make_fuel_sheets(rows))
        assert "设备名称" in result.columns
        assert "设备编号" in result.columns
        assert result["设备名称"].iloc[0] == "CAT785"

    def test_multiple_devices(self):
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "标准设备名称": "CAT785-01",
             "设备名称": "CAT785", "设备编号": "T001", "油品消耗": 100},
            {"日期": "2025-01-01", "班次": "Day", "标准设备名称": "NTE240-01",
             "设备名称": "NTE240", "设备编号": "T002", "油品消耗": 200},
        ]
        result = _aggregate_fuel_data(self._make_fuel_sheets(rows))
        assert len(result) == 2

    def test_empty_sheet(self):
        result = _aggregate_fuel_data({"油耗信息": pd.DataFrame()})
        assert result is None

    def test_missing_sheet(self):
        result = _aggregate_fuel_data({"设备信息": pd.DataFrame({"x": [1]})})
        assert result is None

    def test_drops_shift_rank(self):
        rows = [
            {"日期": "2025-01-01", "班次": "Day", "标准设备名称": "T1",
             "设备名称": "T1", "设备编号": "001", "油品消耗": 100, "shift_rank": 1},
        ]
        result = _aggregate_fuel_data(self._make_fuel_sheets(rows))
        assert "shift_rank" not in result.columns


# ---------------------------------------------------------------------------
# _reorder_columns
# ---------------------------------------------------------------------------

class TestReorderColumns:
    def test_priority_columns_first(self):
        df = pd.DataFrame({"油品消耗": [1], "班次": ["Day"], "日期": ["2025-01-01"],
                           "标准设备名称": ["T1"], "其他": [42]})
        result = _reorder_columns(df)
        cols = result.columns.tolist()
        assert cols[0] == "日期"
        assert cols[1] == "班次"
        assert cols[2] == "标准设备名称"

    def test_all_priority_cols_present(self):
        df = pd.DataFrame({
            "日期": ["2025-01-01"], "班次": ["Day"], "标准设备名称": ["T1"],
            "标准设备编号": ["ID001"], "标准公司名称": ["公司A"],
            "设备名称": ["T1"], "油品消耗": [100],
        })
        result = _reorder_columns(df)
        cols = result.columns.tolist()[:5]
        assert cols == ["日期", "班次", "标准设备名称", "标准设备编号", "标准公司名称"]

    def test_missing_priority_cols_ok(self):
        df = pd.DataFrame({"其他": [1], "班次": ["Day"]})
        result = _reorder_columns(df)
        assert result.columns.tolist()[0] == "班次"
