"""func/excel_utils.py 共享工具函数测试"""
import datetime
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.excel_utils import (
    MODULE_OUTPUT_FILES,
    clean_split_dataframe,
    dedup_dataframe,
    get_output_filename,
    resolve_shift,
    sort_by_date_shift,
    split_day_night_shifts,
    strip_date_column,
)


# ---------------------------------------------------------------------------
# get_output_filename
# ---------------------------------------------------------------------------
class TestGetOutputFilename:
    def test_fuel(self):
        assert get_output_filename("fuel") == "Fuel.xlsx"

    def test_electrical(self):
        assert get_output_filename("electrical") == "电力消耗统计.xlsx"

    def test_production(self):
        assert get_output_filename("production") == "合并产量.xlsx"

    def test_worktime_default(self):
        result = get_output_filename("worktime")
        assert result == "202501_工作效率表.xlsx"

    def test_worktime_custom_year_month(self):
        result = get_output_filename("worktime", year=2024, month=12)
        assert result == "202412_工作效率表.xlsx"

    def test_unknown_type_returns_none(self):
        assert get_output_filename("unknown") is None

    def test_module_output_files_contains_expected_keys(self):
        assert set(MODULE_OUTPUT_FILES.keys()) == {"fuel", "electrical", "production"}


# ---------------------------------------------------------------------------
# resolve_shift
# ---------------------------------------------------------------------------
class TestResolveShift:
    def test_exact_match(self):
        mapping = {5: "Day", 10: "Night"}
        assert resolve_shift(mapping, 5) == "Day"
        assert resolve_shift(mapping, 10) == "Night"

    def test_forward_search(self):
        mapping = {6: "Day"}
        assert resolve_shift(mapping, 5) == "Day"

    def test_backward_search(self):
        mapping = {3: "Night"}
        assert resolve_shift(mapping, 5) == "Night"

    def test_no_match_returns_none(self):
        mapping = {100: "Day"}
        assert resolve_shift(mapping, 5, max_lookahead=3) is None

    def test_num_cols_limits_forward_search(self):
        mapping = {8: "Day"}
        # num_cols=7 means forward search stops at 7, so idx 8 is unreachable
        assert resolve_shift(mapping, 5, num_cols=7) is None

    def test_empty_mapping(self):
        assert resolve_shift({}, 5) is None

    def test_forward_takes_precedence_over_backward(self):
        mapping = {3: "Night", 7: "Day"}
        # target=5: forward finds 7 ("Day") before backward finds 3 ("Night")
        assert resolve_shift(mapping, 5) == "Day"

    def test_backward_search_stops_at_index_3(self):
        mapping = {2: "Night"}
        # backward search stops at range(target-1, 2, -1), so index 2 is not checked
        assert resolve_shift(mapping, 5) is None


# ---------------------------------------------------------------------------
# strip_date_column
# ---------------------------------------------------------------------------
class TestStripDateColumn:
    def test_strips_time_component(self):
        df = pd.DataFrame({
            "日期": ["2025-03-15 08:30:00", "2025-03-16 14:00:00"],
            "值": [1, 2],
        })
        result = strip_date_column(df)
        assert all(isinstance(d, datetime.date) for d in result["日期"])
        assert result["日期"].iloc[0] == datetime.date(2025, 3, 15)

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({
            "日期": ["2025-03-15 08:30:00"],
            "值": [1],
        })
        original_values = df["日期"].copy()
        strip_date_column(df)
        pd.testing.assert_series_equal(df["日期"], original_values)

    def test_returns_new_object(self):
        df = pd.DataFrame({"日期": ["2025-03-15"], "值": [1]})
        result = strip_date_column(df)
        assert result is not df

    def test_target_year_override(self):
        df = pd.DataFrame({"日期": ["2023-06-01"], "值": [1]})
        result = strip_date_column(df, target_year=2025)
        assert result["日期"].iloc[0] == datetime.date(2025, 6, 1)

    def test_missing_date_column_returns_original(self):
        df = pd.DataFrame({"其他": [1, 2]})
        result = strip_date_column(df)
        assert result is df

    def test_empty_dataframe(self):
        df = pd.DataFrame({"日期": pd.Series([], dtype=str)})
        result = strip_date_column(df)
        assert result is df

    def test_custom_date_column_name(self):
        df = pd.DataFrame({"时间": ["2025-01-01 12:00"], "值": [1]})
        result = strip_date_column(df, date_column="时间")
        assert result["时间"].iloc[0] == datetime.date(2025, 1, 1)


# ---------------------------------------------------------------------------
# sort_by_date_shift
# ---------------------------------------------------------------------------
class TestSortByDateShift:
    def test_sorts_by_date_then_shift(self):
        df = pd.DataFrame({
            "日期": [datetime.date(2025, 3, 16), datetime.date(2025, 3, 15), datetime.date(2025, 3, 15)],
            "班次": ["Day", "Night", "Day"],
            "值": [3, 2, 1],
        })
        result = sort_by_date_shift(df)
        assert list(result["值"]) == [1, 2, 3]

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({
            "日期": [datetime.date(2025, 3, 16), datetime.date(2025, 3, 15)],
            "班次": ["Day", "Night"],
        })
        original_order = list(df["日期"])
        sort_by_date_shift(df)
        assert list(df["日期"]) == original_order

    def test_returns_new_object(self):
        df = pd.DataFrame({"日期": [datetime.date(2025, 1, 1)], "班次": ["Day"]})
        result = sort_by_date_shift(df)
        assert result is not df

    def test_missing_sort_columns_returns_original(self):
        df = pd.DataFrame({"其他": [3, 1, 2]})
        result = sort_by_date_shift(df)
        assert result is df

    def test_custom_sort_columns(self):
        df = pd.DataFrame({"A": [3, 1, 2], "B": ["x", "y", "z"]})
        result = sort_by_date_shift(df, sort_columns=["A"])
        assert list(result["A"]) == [1, 2, 3]

    def test_partial_sort_columns(self):
        df = pd.DataFrame({"日期": [2, 1], "其他": ["a", "b"]})
        result = sort_by_date_shift(df)
        assert list(result["日期"]) == [1, 2]


# ---------------------------------------------------------------------------
# split_day_night_shifts
# ---------------------------------------------------------------------------
class TestSplitDayNightShifts:
    def _make_raw_df(self):
        """构造模拟工时报表原始 DataFrame（header=None 读入）"""
        return pd.DataFrame([
            ["其他", "其他", "其他"],       # row 0: ignored
            ["日期", "工时", "备注"],       # row 1: header
            ["Day行", 8, "正常"],          # row 2: day data
            ["Day行", 6, "正常"],          # row 3: day data
            ["Night行", 0, ""],            # row 4: NOT split row (first col differs from header)
            ["日期", 4, "夜班"],           # row 5: split row (first col matches header)
            ["Night行", 7, "正常"],        # row 6: night data
        ])

    def test_with_split_point_default_offset(self):
        df_raw = self._make_raw_df()
        result = split_day_night_shifts(df_raw, day_end_offset=-1)
        assert "班次" in result.columns
        assert list(result["班次"]).count("Day") >= 1
        assert list(result["班次"]).count("Night") >= 1

    def test_with_split_point_offset_zero(self):
        df_raw = self._make_raw_df()
        result = split_day_night_shifts(df_raw, day_end_offset=0)
        assert "班次" in result.columns
        assert list(result["班次"]).count("Day") >= 1

    def test_no_split_point_all_day(self):
        df_raw = pd.DataFrame([
            ["x", "x", "x"],
            ["日期", "工时", "备注"],
            ["A", 8, "ok"],
            ["B", 6, "ok"],
        ])
        result = split_day_night_shifts(df_raw)
        assert all(s == "Day" for s in result["班次"])

    def test_sets_column_names_from_header(self):
        df_raw = pd.DataFrame([
            ["x", "x"],
            ["日期", "工时"],
            ["A", 8],
        ])
        result = split_day_night_shifts(df_raw)
        assert list(result.columns[:2]) == ["日期", "工时"]


# ---------------------------------------------------------------------------
# clean_split_dataframe
# ---------------------------------------------------------------------------
class TestCleanSplitDataFrame:
    def test_removes_nan_columns(self):
        df = pd.DataFrame({
            "日期": ["a"],
            "值": [1],
            float("nan"): [2],
        })
        result = clean_split_dataframe(df)
        assert float("nan") not in result.columns

    def test_removes_empty_string_columns(self):
        df = pd.DataFrame({"日期": ["a"], "": [1], "值": [2]})
        result = clean_split_dataframe(df)
        assert "" not in result.columns

    def test_removes_rows_where_keyword_column_is_nan(self):
        df = pd.DataFrame({
            "日期": ["a", "b"],
            "Техникийн үзүүлэлт": [1.0, float("nan")],
            "值": [10, 20],
        })
        result = clean_split_dataframe(df)
        assert len(result) == 1

    def test_removes_rows_where_non_skip_columns_all_nan(self):
        df = pd.DataFrame({
            "日期": ["a", "b"],
            "班次": ["Day", "Night"],
            "值": [1.0, float("nan")],
        })
        result = clean_split_dataframe(df)
        assert len(result) == 1

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({"日期": ["a"], "": [1], "值": [2]})
        original_cols = list(df.columns)
        clean_split_dataframe(df)
        assert list(df.columns) == original_cols

    def test_returns_new_object(self):
        df = pd.DataFrame({"日期": ["a"], "值": [1]})
        result = clean_split_dataframe(df)
        assert result is not df

    def test_custom_skip_columns(self):
        df = pd.DataFrame({
            "X": ["a", "b"],
            "Y": ["c", "d"],
            "值": [1.0, float("nan")],
        })
        result = clean_split_dataframe(df, skip_columns=["X", "Y"])
        assert len(result) == 1

    def test_custom_check_keyword(self):
        df = pd.DataFrame({
            "日期": ["a", "b"],
            "MyKeyword col": [1.0, float("nan")],
            "值": [10, 20],
        })
        result = clean_split_dataframe(df, check_keyword="MyKeyword")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# dedup_dataframe
# ---------------------------------------------------------------------------
class TestDedupDataframe:
    def test_removes_duplicates(self):
        df = pd.DataFrame({"A": [1, 2, 1], "B": ["x", "y", "x"]})
        result = dedup_dataframe(df)
        assert len(result) == 2

    def test_keeps_first_occurrence(self):
        df = pd.DataFrame({"A": [1, 2, 1], "B": ["x", "y", "x"]})
        result = dedup_dataframe(df)
        assert list(result["B"]) == ["x", "y"]

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = dedup_dataframe(df)
        assert result.empty

    def test_no_duplicates_unchanged(self):
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        result = dedup_dataframe(df)
        assert len(result) == 3

    def test_logs_with_label(self, caplog):
        import logging
        df = pd.DataFrame({"A": [1, 1]})
        with caplog.at_level(logging.INFO):
            dedup_dataframe(df, label="test")
        assert "test" in caplog.text
        assert "去重" in caplog.text
