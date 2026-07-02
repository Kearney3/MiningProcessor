"""excel_electrical 模块测试"""
import pathlib

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys_path = __import__("sys").path
sys_path.insert(0, str(ROOT))

from func.excel_electrical import parse_excel_data


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_electrical_excel(path, rows):
    """Create an Excel file with a single 'Electrical' sheet.

    Args:
        path: File system path for the output .xlsx.
        rows: list[list] -- each inner list is one row (no header assumed).
    """
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Electrical", index=False, header=False)


def _make_multi_sheet_excel(path, sheets):
    """Create an Excel file with multiple sheets.

    Args:
        path: File system path for the output .xlsx.
        sheets: dict[str, list[list]] -- key is sheet name, value is rows.
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(
                writer, sheet_name=sheet_name, index=False, header=False,
            )


# Layout helper: The parser scans column 0 (col A) for the cell containing "日期".
# Columns at indices 1-3 (B, C, D) are filler.  Date columns start at index 4 (col E).
# We build rows as:  [col_A, col_B, col_C, col_D, col_E, col_F, ...]
# For the date header row: ["日期", "", "", "", date1, date2, ...]
# For data rows:            [device_label, None, None, None, None, val1, val2, ...]


def _date_header(*dates):
    """Build a date header row with '日期' in col 0 and dates from col 4."""
    return ["日期", "", "", ""] + list(dates)


def _device_row(label, *values):
    """Build a data row: device label in col 0, filler, then power values from col 4."""
    return [label, None, None, None] + list(values)


# ---------------------------------------------------------------------------
# test_normal_processing
# ---------------------------------------------------------------------------

class TestNormalProcessing:
    """Verify end-to-end extraction from a well-formed electrical sheet."""

    def test_extract_single_device(self, tmp_path):
        """A sheet with one device, one date, one power reading."""
        rows = [
            _date_header("2025-03-01", "2025-03-02"),
            _device_row("电力总消耗 EX-201 挖土机", 120.5, 130.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True, add_shift_column=False)

        assert result is not None
        df = result["电力消耗"]
        assert len(df) == 2
        assert set(df.columns) == {"日期", "设备名称", "电力消耗"}
        dates = sorted(df["日期"])
        assert dates == [pd.Timestamp("2025-03-01").date(), pd.Timestamp("2025-03-02").date()]
        devices = set(df["设备名称"])
        assert devices == {"EX-201"}

    def test_extract_multiple_devices(self, tmp_path):
        """Two devices on the same sheet."""
        rows = [
            _date_header("2025-04-10", "2025-04-11"),
            _device_row("电力总消耗 EX-201 挖土机", 120.5, 130.0),
            _device_row("电力总消耗 EX-305 卡车", 80.0, 90.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True, add_shift_column=False)

        assert result is not None
        df = result["电力消耗"]
        assert len(df) == 4  # 2 devices x 2 dates
        devices = set(df["设备名称"])
        assert devices == {"EX-201", "EX-305"}

    def test_target_year_overrides(self, tmp_path):
        """target_year replaces the year in extracted dates."""
        rows = [
            _date_header("2024-06-15"),
            _device_row("电力总消耗 EX-100", 50.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), target_year=2025, return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 1
        assert df.iloc[0]["日期"] == pd.Timestamp("2025-06-15").date()

    def test_filters_per_cubic_output(self, tmp_path):
        """Rows containing '每立方产量' must be skipped."""
        rows = [
            _date_header("2025-01-01"),
            _device_row("电力总消耗 EX-201 挖土机", 120.5),
            _device_row("电力总消耗 每立方产量", 0.5),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 1
        assert df.iloc[0]["设备名称"] == "EX-201"

    def test_returns_none_when_no_data(self, tmp_path):
        """When nothing matches, function returns None."""
        rows = [
            _date_header("2025-01-01"),
            _device_row("其他数据", 120.5),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None

    def test_skips_non_electrical_sheets(self, tmp_path):
        """Sheets without 'Electrical' in their name are ignored."""
        sheets = {
            "Fuel": [
                _date_header("2025-01-01"),
                _device_row("柴油消耗 EX-201", 50.0),
            ],
            "Production": [
                _date_header("2025-01-01"),
                _device_row("产量 EX-201", 100.0),
            ],
        }
        f = tmp_path / "input.xlsx"
        _make_multi_sheet_excel(f, sheets)

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None


# ---------------------------------------------------------------------------
# test_shift_detection
# ---------------------------------------------------------------------------

class TestShiftDetection:
    """Verify Day/Night shift identification from header rows."""

    def test_detect_day_shift(self, tmp_path):
        """Row above date row contains '白班'/'夜班' → correct shift labels."""
        # Shift labels go in the same column positions as dates, one row above
        rows = [
            ["", "", "", "", "白班", "夜班"],   # row 0: shift labels above dates
            _date_header("2025-03-01", "2025-03-02"),  # row 1: date row (idx 1)
            _device_row("电力总消耗 EX-201 挖土机", 120.5, 130.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert len(df) == 2
        shifts = dict(zip(df["日期"], df["班次"]))
        day_date = pd.Timestamp("2025-03-01").date()
        night_date = pd.Timestamp("2025-03-02").date()
        assert shifts[day_date] == "Day"
        assert shifts[night_date] == "Night"

    def test_detect_chinese_shifts(self, tmp_path):
        """Chinese shift labels 白班/夜班 are detected."""
        rows = [
            ["", "", "", "", "白班", "夜班"],
            _date_header("2025-05-01", "2025-05-02"),
            _device_row("电力总消耗 EX-300", 200.0, 180.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert len(df) == 2
        assert set(df["班次"]) == {"Day", "Night"}

    def test_default_shift_when_no_header(self, tmp_path):
        """If no shift keywords found, use default_shift parameter."""
        rows = [
            _date_header("2025-05-01", "2025-05-02"),
            _device_row("电力总消耗 EX-400", 90.0, 95.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert len(df) == 2
        assert all(s == "Day" for s in df["班次"])

    def test_default_shift_night(self, tmp_path):
        """default_shift='Night' should be used when no headers."""
        rows = [
            _date_header("2025-05-01"),
            _device_row("电力总消耗 EX-500", 70.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Night",
        )
        df = result["电力消耗"]
        assert df.iloc[0]["班次"] == "Night"

    def test_shift_column_order_in_output(self, tmp_path):
        """When add_shift_column is True, column order should be 日期, 班次, 设备名称, 电力消耗."""
        rows = [
            _date_header("2025-06-01"),
            _device_row("电力总消耗 EX-600", 60.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert list(df.columns) == ["日期", "班次", "设备名称", "电力消耗"]

    def test_day_before_night_sorting(self, tmp_path):
        """Day shift rows should appear before Night shift rows on the same date."""
        rows = [
            ["", "", "", "", "白班", "夜班"],
            _date_header("2025-06-01", "2025-06-02"),
            _device_row("电力总消耗 EX-700", 100.0, 110.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert df.iloc[0]["班次"] == "Day"
        assert df.iloc[1]["班次"] == "Night"

    def test_backward_look_for_shift(self, tmp_path):
        """When a column has no direct shift label, look backward to find nearest."""
        rows = [
            ["", "", "", "", "白班", "", ""],
            _date_header("2025-06-01", "2025-06-02", "2025-06-03"),
            _device_row("电力总消耗 EX-800", 100.0, 110.0, 120.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert len(df) == 3
        # All three dates should inherit "Day" via backward search since only col 5 has "白班"
        assert all(s == "Day" for s in df["班次"])


# ---------------------------------------------------------------------------
# test_date_parsing
# ---------------------------------------------------------------------------

class TestDateParsing:
    """Verify date extraction from the date header row."""

    def test_parse_string_dates(self, tmp_path):
        """String-formatted dates like '2025-01-01' are correctly parsed."""
        rows = [
            _date_header("2025-01-01", "2025-01-02", "2025-01-03"),
            _device_row("电力总消耗 EX-100", 50.0, 60.0, 70.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 3
        expected = [
            pd.Timestamp("2025-01-01").date(),
            pd.Timestamp("2025-01-02").date(),
            pd.Timestamp("2025-01-03").date(),
        ]
        assert sorted(df["日期"]) == expected

    def test_parse_excel_serial_dates(self, tmp_path):
        """Excel serial number dates are also handled."""
        # Excel serial for 2025-03-15 is 45731 (days since 1899-12-30)
        rows = [
            _date_header(45731, 45732),
            _device_row("电力总消耗 EX-200", 100.0, 110.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 2
        dates = sorted(df["日期"])
        assert dates == [
            pd.Timestamp("2025-03-15").date(),
            pd.Timestamp("2025-03-16").date(),
        ]

    def test_skip_non_date_columns(self, tmp_path):
        """Columns that cannot be parsed as dates are silently skipped."""
        rows = [
            ["日期", "", "", "", "2025-02-01", "NOT_A_DATE", "2025-02-03"],
            _device_row("电力总消耗 EX-300", 30.0, 40.0, 50.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 2  # Only valid dates kept
        dates = sorted(df["日期"])
        assert dates == [
            pd.Timestamp("2025-02-01").date(),
            pd.Timestamp("2025-02-03").date(),
        ]

    def test_date_has_no_time_component(self, tmp_path):
        """Output dates should be date-only, not datetime."""
        rows = [
            _date_header("2025-04-01"),
            _device_row("电力总消耗 EX-400", 25.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        val = df.iloc[0]["日期"]
        # Should be a date object (not datetime) after processing
        import datetime
        assert isinstance(val, (datetime.date, pd.Timestamp))
        if hasattr(val, "time"):
            assert val == pd.Timestamp("2025-04-01").date()

    def test_empty_cell_skipped(self, tmp_path):
        """Empty cells in the date row should not produce records."""
        # Skip index 1-3 as filler, index 4 is None (empty date cell)
        rows = [
            ["日期", "", "", "", None, "2025-05-01"],
            _device_row("电力总消耗 EX-500", 10.0, 20.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 1
        assert df.iloc[0]["日期"] == pd.Timestamp("2025-05-01").date()


# ---------------------------------------------------------------------------
# test_empty_sheet
# ---------------------------------------------------------------------------

class TestEmptySheet:
    """Edge cases involving empty or near-empty sheets."""

    def test_no_date_keyword(self, tmp_path):
        """Sheet without '日期' keyword in column 0 is skipped."""
        rows = [
            ["设备", "A", "B", "C", "时间", "2025-01-01"],
            _device_row("电力总消耗 EX-100", 50.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None

    def test_date_row_with_no_data_below(self, tmp_path):
        """Sheet has date row but no data rows below it."""
        rows = [
            _date_header("2025-01-01"),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None

    def test_all_nan_power_values(self, tmp_path):
        """Data rows exist but all power values are NaN."""
        rows = [
            _date_header("2025-01-01"),
            _device_row("电力总消耗 EX-100", None),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None

    def test_completely_empty_sheet(self, tmp_path):
        """An entirely empty sheet produces no results."""
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, [])

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None

    def test_no_electrical_sheet_found(self, tmp_path):
        """File with no sheet named 'Electrical' returns None."""
        sheets = {"Report": [["something"]]}
        f = tmp_path / "input.xlsx"
        _make_multi_sheet_excel(f, sheets)

        result = parse_excel_data(str(f), return_sheets=True)
        assert result is None


# ---------------------------------------------------------------------------
# test_multi_day_sheet
# ---------------------------------------------------------------------------

class TestMultiDaySheet:
    """Sheets spanning many dates and multiple devices."""

    def test_ten_dates_one_device(self, tmp_path):
        """Extract power readings across ten consecutive dates."""
        dates = [f"2025-07-{d:02d}" for d in range(1, 11)]
        rows = [
            _date_header(*dates),
            _device_row("电力总消耗 EX-999", *[float(d * 10) for d in range(1, 11)]),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 10
        assert all(df["设备名称"] == "EX-999")
        expected_vals = sorted([float(d * 10) for d in range(1, 11)])
        assert sorted(df["电力消耗"]) == expected_vals

    def test_multi_device_multi_day(self, tmp_path):
        """Three devices over five dates yields 15 records."""
        dates = [f"2025-08-{d:02d}" for d in range(1, 6)]
        rows = [
            _date_header(*dates),
            _device_row("电力总消耗 EX-A1", *[10.0] * 5),
            _device_row("电力总消耗 EX-B2", *[20.0] * 5),
            _device_row("电力总消耗 EX-C3", *[30.0] * 5),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 15
        devices = set(df["设备名称"])
        assert devices == {"EX-A1", "EX-B2", "EX-C3"}
        for dev in devices:
            assert len(df[df["设备名称"] == dev]) == 5

    def test_multi_day_with_shifts(self, tmp_path):
        """Multiple days with Day/Night shift labels on each date pair."""
        rows = [
            ["", "", "", "", "白班", "夜班", "白班", "夜班"],
            _date_header("2025-07-01", "2025-07-02", "2025-07-03", "2025-07-04"),
            _device_row("电力总消耗 EX-D1", 100.0, 110.0, 120.0, 130.0),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(
            str(f), return_sheets=True, add_shift_column=True, default_shift="Day",
        )
        df = result["电力消耗"]
        assert len(df) == 4
        shifts = df["班次"].tolist()
        assert shifts == ["Day", "Night", "Day", "Night"]

    def test_duplicate_records_deduped(self, tmp_path):
        """Duplicate rows (same date+device+power) are removed by dedup."""
        rows = [
            _date_header("2025-09-01"),
            _device_row("电力总消耗 EX-DEDUP", 50.0),
            _device_row("电力总消耗 EX-DEDUP", 50.0),  # exact duplicate
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 1

    def test_integer_and_float_values(self, tmp_path):
        """Both integer and float power values are captured."""
        rows = [
            _date_header("2025-10-01", "2025-10-02"),
            _device_row("电力总消耗 EX-MIX", 100, 50.5),
        ]
        f = tmp_path / "input.xlsx"
        _make_electrical_excel(f, rows)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 2
        vals = sorted(df["电力消耗"])
        assert vals == [50.5, 100]

    def test_only_electrical_sheet_processed(self, tmp_path):
        """Only sheets containing 'Electrical' are parsed; others ignored."""
        sheets = {
            "Daily Electrical Report": [
                _date_header("2025-11-01"),
                _device_row("电力总消耗 EX-E1", 75.0),
            ],
            "Fuel Sheet": [
                _date_header("2025-11-01"),
                _device_row("柴油消耗 EX-F1", 80.0),
            ],
        }
        f = tmp_path / "input.xlsx"
        _make_multi_sheet_excel(f, sheets)

        result = parse_excel_data(str(f), return_sheets=True)

        df = result["电力消耗"]
        assert len(df) == 1
        assert df.iloc[0]["设备名称"] == "EX-E1"
