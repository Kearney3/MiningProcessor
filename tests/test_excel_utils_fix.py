"""Test: split_day_night_shifts handles empty header rows without crashing."""
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.excel_utils import split_day_night_shifts


class TestSplitDayNightShiftsEmptyHeader:
    """Regression: split_day_night_shifts must not crash when header row is all NaN."""

    def test_all_nan_header_row_returns_day_fallback(self):
        """When the header row is entirely NaN, the function should return
        all data rows with 班次='Day' (fallback path) instead of crashing."""
        df_raw = pd.DataFrame([
            [None, None, None],        # row 0: ignored (before header)
            [None, None, None],        # row 1: header -- all NaN
            ["A", 8, "正常"],          # row 2: data
            ["B", 6, "正常"],          # row 3: data
        ])
        result = split_day_night_shifts(df_raw)
        assert "班次" in result.columns
        assert all(s == "Day" for s in result["班次"])
        assert len(result) == 2

    def test_partial_nan_header_with_valid_cols_still_works(self):
        """When the header row has a mix of NaN and valid values,
        processing should proceed normally (existing behavior, no regression)."""
        df_raw = pd.DataFrame([
            ["x", "x", "x"],
            [None, "工时", None],       # header: only col 1 is valid
            ["Day行", 8, "正常"],
            ["日期", 6, "夜班"],
            ["Night行", 7, "正常"],
        ])
        result = split_day_night_shifts(df_raw)
        assert "班次" in result.columns
        assert list(result["班次"]).count("Day") >= 1

    def test_empty_dataframe_with_nan_header(self):
        """An empty DataFrame with an all-NaN header should also not crash."""
        df_raw = pd.DataFrame([
            [None, None],
            [None, None],
        ])
        result = split_day_night_shifts(df_raw)
        assert "班次" in result.columns
        assert len(result) == 0
