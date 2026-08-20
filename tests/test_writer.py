"""Tests for func.writer — maintenance record Excel output."""

import datetime

import pandas as pd
import xlsxwriter

from func.writer import (
    _TAB_COLORS,
    _auto_col_width,
    _detect_stats,
    _make_formats,
    write_excel,
)

# ── _auto_col_width ────────────────────────────────────────────────────────


class TestAutoColWidth:
    def test_ascii_headers(self):
        widths = _auto_col_width(["Name", "Age"], [])
        # "Name" + 2 = 6, clamped to min 8
        assert widths == [8, 8]

    def test_cjk_headers_count_as_double_width(self):
        widths = _auto_col_width(["设备名称", "日期"], [])
        # "设备名称" = 4 CJK chars * 2 = 8, +2 = 10
        # "日期" = 2 CJK chars * 2 = 4, +2 = 6, clamped to min 8
        assert widths[0] == 10
        assert widths[1] == 8

    def test_rows_widen_columns(self):
        headers = ["ID"]
        rows = [("abcdefghijklmnop",)]  # 16 chars + 2 = 18
        widths = _auto_col_width(headers, rows)
        assert widths[0] == 18

    def test_min_width_clamp(self):
        widths = _auto_col_width(["A"], [], min_w=12)
        # "A" + 2 = 3, clamped to 12
        assert widths[0] == 12

    def test_max_width_clamp(self):
        headers = ["ID"]
        rows = [("x" * 100,)]
        widths = _auto_col_width(headers, rows, max_w=30)
        assert widths[0] == 30

    def test_date_values_use_fixed_width_12(self):
        headers = ["日期"]
        rows = [(datetime.date(2025, 1, 1),)]
        widths = _auto_col_width(headers, rows)
        # "日期" header = 4*2 + 2 = 10; date cell = 12
        assert widths[0] == 12

    def test_timestamp_values_use_fixed_width_12(self):
        headers = ["日期"]
        rows = [(pd.Timestamp("2025-06-15"),)]
        widths = _auto_col_width(headers, rows)
        assert widths[0] == 12

    def test_none_values_are_skipped(self):
        headers = ["Col"]
        rows = [(None,)]
        widths = _auto_col_width(headers, rows)
        # Only header contributes: "Col" + 2 = 5, clamped to 8
        assert widths[0] == 8

    def test_limits_rows_to_first_500(self):
        headers = ["X"]
        rows = [("short",)] * 501
        widths = _auto_col_width(headers, rows)
        # "short" + 2 = 7, clamped to min 8; only first 500 rows scanned
        assert widths[0] == 8

    def test_fullwidth_characters_count_as_double_width(self):
        headers = ["Ａ"]
        widths = _auto_col_width(headers, [])
        # Fullwidth A (U+FF21) = 2, +2 = 4, clamped to min 8
        assert widths[0] == 8

    def test_row_with_more_columns_than_headers(self):
        headers = ["A"]
        rows = [("val1", "val2")]  # more values than headers
        widths = _auto_col_width(headers, rows)
        # Only first column updated; extra columns ignored via bounds check
        assert len(widths) == 1

    def test_mixed_none_and_valid_values(self):
        headers = ["Col"]
        rows = [(None,), ("longvalue",)]
        widths = _auto_col_width(headers, rows)
        # "longvalue" + 2 = 11
        assert widths[0] == 11


# ── _detect_stats ──────────────────────────────────────────────────────────


class TestDetectStats:
    def test_date_column_detected_by_keyword(self):
        headers = ["日期", "设备名称", "维修内容"]
        date_cols, pct_cols, hour_cols, wrap_cols = _detect_stats(headers, [])
        assert 0 in date_cols

    def test_percent_column_detected_by_zhanbi(self):
        headers = ["设备", "占比"]
        _, pct_cols, _, _ = _detect_stats(headers, [])
        assert 1 in pct_cols

    def test_percent_column_detected_by_guzhanglv(self):
        headers = ["设备", "故障率"]
        _, pct_cols, _, _ = _detect_stats(headers, [])
        assert 1 in pct_cols

    def test_percent_column_detected_by_bili(self):
        headers = ["设备", "比例"]
        _, pct_cols, _, _ = _detect_stats(headers, [])
        assert 1 in pct_cols

    def test_hour_column_detected(self):
        headers = ["设备", "工作小时"]
        _, _, hour_cols, _ = _detect_stats(headers, [])
        assert 1 in hour_cols

    def test_wrap_column_detected_by_weixiuneirong(self):
        headers = ["设备", "维修内容"]
        _, _, _, wrap_cols = _detect_stats(headers, [])
        assert 1 in wrap_cols

    def test_date_column_excludes_zhanbi(self):
        """Column named '占比日期' should not be detected as date."""
        headers = ["占比日期"]
        date_cols, _, _, _ = _detect_stats(headers, [])
        assert len(date_cols) == 0

    def test_no_special_columns(self):
        headers = ["ID", "Name", "Status"]
        date_cols, pct_cols, hour_cols, wrap_cols = _detect_stats(headers, [])
        assert date_cols == set()
        assert pct_cols == set()
        assert hour_cols == set()
        assert wrap_cols == set()

    def test_multiple_special_columns(self):
        headers = ["日期", "设备", "维修内容", "占比", "工作小时", "故障率"]
        date_cols, pct_cols, hour_cols, wrap_cols = _detect_stats(headers, [])
        assert 0 in date_cols
        assert 2 in wrap_cols
        assert 3 in pct_cols
        assert 4 in hour_cols
        assert 5 in pct_cols

    def test_empty_headers(self):
        date_cols, pct_cols, hour_cols, wrap_cols = _detect_stats([], [])
        assert all(s == set() for s in (date_cols, pct_cols, hour_cols, wrap_cols))


# ── _make_formats ──────────────────────────────────────────────────────────


class TestMakeFormats:
    def test_returns_all_expected_keys(self):
        wb = xlsxwriter.Workbook("/dev/null", {"strings_to_urls": False})
        fmts = _make_formats(wb)
        expected_keys = {
            "hdr",
            "int", "txt_center", "txt", "date", "pct", "hour",
            "a_int", "a_txt_center", "a_txt", "a_date", "a_pct", "a_hour",
        }
        assert set(fmts.keys()) == expected_keys
        wb.close()


# ── write_excel ────────────────────────────────────────────────────────────


class TestWriteExcel:
    def test_creates_valid_xlsx(self, tmp_path):
        output = tmp_path / "output.xlsx"
        df = pd.DataFrame({"日期": ["2025-01-01"], "设备": ["卡车-01"], "值": [100]})
        write_excel(str(output), {"维修明细": df})
        assert output.exists()
        assert output.stat().st_size > 0

    def test_valid_xlsx_readable_by_pandas(self, tmp_path):
        output = tmp_path / "output.xlsx"
        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        write_excel(str(output), {"维修明细": df})
        result = pd.read_excel(str(output), sheet_name="维修明细")
        assert len(result) == 2
        assert list(result.columns) == ["A", "B"]

    def test_sheet_ordering_follows_defined_order(self, tmp_path):
        output = tmp_path / "output.xlsx"
        # Provide sheets in reverse order
        sheets = {
            "故障类型统计": pd.DataFrame({"X": [1]}),
            "维修明细": pd.DataFrame({"Y": [2]}),
            "每月设备故障统计": pd.DataFrame({"Z": [3]}),
        }
        write_excel(str(output), sheets)
        xls = pd.ExcelFile(str(output))
        # Sheets should appear in ORDER sequence, not insertion order
        assert xls.sheet_names == ["维修明细", "每月设备故障统计", "故障类型统计"]

    def test_multiple_sheets(self, tmp_path):
        output = tmp_path / "output.xlsx"
        sheets = {
            "维修明细": pd.DataFrame({"A": [1]}),
            "每月设备故障统计": pd.DataFrame({"B": [2]}),
            "全周期设备故障统计": pd.DataFrame({"C": [3]}),
        }
        write_excel(str(output), sheets)
        xls = pd.ExcelFile(str(output))
        assert len(xls.sheet_names) == 3

    def test_unordered_sheets_not_included(self, tmp_path):
        output = tmp_path / "output.xlsx"
        sheets = {
            "维修明细": pd.DataFrame({"A": [1]}),
            "未知Sheet": pd.DataFrame({"B": [2]}),
        }
        write_excel(str(output), sheets)
        xls = pd.ExcelFile(str(output))
        assert xls.sheet_names == ["维修明细"]
        assert "未知Sheet" not in xls.sheet_names

    def test_empty_dataframe_produces_no_sheet(self, tmp_path):
        output = tmp_path / "output.xlsx"
        sheets = {
            "维修明细": pd.DataFrame(),
            "故障类型统计": pd.DataFrame({"X": [1]}),
        }
        write_excel(str(output), sheets)
        xls = pd.ExcelFile(str(output))
        # Empty DF is skipped; only the non-empty sheet appears
        assert xls.sheet_names == ["故障类型统计"]

    def test_none_dataframe_skipped(self, tmp_path):
        output = tmp_path / "output.xlsx"
        sheets = {"维修明细": None, "故障类型统计": pd.DataFrame({"X": [1]})}
        write_excel(str(output), sheets)
        xls = pd.ExcelFile(str(output))
        assert xls.sheet_names == ["故障类型统计"]

    def test_all_sheets_in_order(self, tmp_path):
        """Verify all 8 defined sheet names are written in correct order."""
        output = tmp_path / "output.xlsx"
        order = [
            "维修明细",
            "每月设备故障统计",
            "全周期设备故障统计",
            "全周期设备故障汇总",
            "每月设备型号故障统计",
            "全周期设备型号故障统计",
            "全周期设备型号故障汇总",
            "故障类型统计",
        ]
        sheets = {name: pd.DataFrame({"X": [i]}) for i, name in enumerate(order)}
        write_excel(str(output), sheets)
        xls = pd.ExcelFile(str(output))
        assert xls.sheet_names == order

    def test_nan_values_written_as_empty(self, tmp_path):
        """NaN in source data should not crash the writer."""
        output = tmp_path / "output.xlsx"
        df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [95.0, float("nan")]})
        write_excel(str(output), {"维修明细": df})
        result = pd.read_excel(str(output), sheet_name="维修明细")
        # NaN cell is written as empty string; pandas reads it back as NaN
        # but the row is still present because column A has data
        assert len(result) == 2
        assert result["Name"].iloc[0] == "Alice"
        assert result["Name"].iloc[1] == "Bob"
        assert pd.isna(result["Score"].iloc[1])

    def test_date_column_formatted_as_datetime(self, tmp_path):
        output = tmp_path / "output.xlsx"
        df = pd.DataFrame({
            "日期": [datetime.date(2025, 3, 15)],
            "设备": ["挖掘机-01"],
        })
        write_excel(str(output), {"维修明细": df})
        result = pd.read_excel(str(output), sheet_name="维修明细")
        # Date should be parseable as datetime, not a string
        assert pd.api.types.is_datetime64_any_dtype(result["日期"])

    def test_percent_column_formatted(self, tmp_path):
        output = tmp_path / "output.xlsx"
        df = pd.DataFrame({"设备": ["卡车"], "占比": [0.85]})
        write_excel(str(output), {"维修明细": df})
        result = pd.read_excel(str(output), sheet_name="维修明细")
        # Value should be stored as the raw number (0.85), not 85
        assert abs(result["占比"].iloc[0] - 0.85) < 0.01

    def test_large_dataframe(self, tmp_path):
        output = tmp_path / "output.xlsx"
        df = pd.DataFrame({
            "ID": range(1000),
            "Name": [f"设备-{i}" for i in range(1000)],
            "Value": [i * 1.5 for i in range(1000)],
        })
        write_excel(str(output), {"维修明细": df})
        result = pd.read_excel(str(output), sheet_name="维修明细")
        assert len(result) == 1000


# ── _TAB_COLORS ────────────────────────────────────────────────────────────


class TestTabColors:
    def test_has_colors_for_all_sheets(self):
        """Tab color palette should cover all 8 defined sheets."""
        assert len(_TAB_COLORS) >= 8

    def test_colors_are_hex_format(self):
        for color in _TAB_COLORS:
            assert color.startswith("#")
            assert len(color) == 7
