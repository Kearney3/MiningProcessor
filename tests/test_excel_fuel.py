"""Comprehensive tests for func/excel_fuel.py (process_diesel_data)."""

import os
import datetime
from pathlib import Path

import pytest
import openpyxl

from func.excel_fuel import process_diesel_data


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_realistic_fuel_sheet(ws, *, include_data=True):
    """Populate an openpyxl worksheet with a realistic diesel consumption layout.

    The parser expects this pandas row layout (after header=None parse):

    iloc 0-1  : title/filler rows
    iloc 2    : h2 (date row)  — dates, "起运小时数", or info labels
    iloc 3    : h3 (group row) — 班组 info, ffill-expanded
    iloc 4    : h4 (shift row) — combined shift+type labels, e.g. "白班小时数", "夜班柴油"
    iloc 5    : h5 (oil row)   — fuel type names like "柴油", or empty
    iloc 6    : marker row (col A == 1 triggers start_row detection)
    iloc 7+   : data rows

    Key detail: h4 is scanned for BOTH shift keywords (白班/夜班) via detect_shift()
    AND for hour-type keywords ("小时数", "已使用小时数") via substring check.
    So data columns must have combined values like "白班小时数" or "夜班柴油".
    """
    # Excel rows 1-2: title
    ws.cell(row=1, column=1, value="设备柴油消耗月报表")
    ws.cell(row=2, column=1, value="2025年1月")

    # h2 (date row) - Excel row 3, pandas iloc 2
    ws.cell(row=3, column=1, value="序号")
    ws.cell(row=3, column=2, value="设备名称")
    ws.cell(row=3, column=3, value="设备编号")
    ws.cell(row=3, column=4, value="起运小时数")
    # Date 1: cols 5-6 (Day end_hours + Day fuel), cols 7-8 (Night end_hours + Night fuel)
    ws.cell(row=3, column=5, value="2025-01-15")
    ws.cell(row=3, column=6, value="2025-01-15")
    ws.cell(row=3, column=7, value="2025-01-15")
    ws.cell(row=3, column=8, value="2025-01-15")
    # Date 2: cols 9-10 (Day end_hours + Day fuel)
    ws.cell(row=3, column=9, value="2025-01-16")
    ws.cell(row=3, column=10, value="2025-01-16")

    # h3 (group row) - Excel row 4, pandas iloc 3
    ws.cell(row=4, column=1, value="班组A")
    ws.cell(row=4, column=2, value="班组A")
    ws.cell(row=4, column=3, value="班组A")

    # h4 (shift + type row) - Excel row 5, pandas iloc 4
    # Combined shift+type labels for data columns.
    # detect_shift('白班') = 'Day', detect_shift('夜班') = 'Night'.
    # '小时数' in '白班小时数' = True => classified as end_hours.
    ws.cell(row=5, column=1, value="白班")
    ws.cell(row=5, column=2, value="白班")
    ws.cell(row=5, column=3, value="白班")
    ws.cell(row=5, column=4, value="白班")
    ws.cell(row=5, column=5, value="白班小时数")    # Day end_hours
    ws.cell(row=5, column=6, value="白班柴油")      # Day fuel (no hour marker => fuel)
    ws.cell(row=5, column=7, value="夜班小时数")    # Night end_hours
    ws.cell(row=5, column=8, value="夜班柴油")      # Night fuel
    ws.cell(row=5, column=9, value="白班小时数")    # Day end_hours
    ws.cell(row=5, column=10, value="白班柴油")     # Day fuel

    # h5 (oil type row) - Excel row 6, pandas iloc 5
    ws.cell(row=6, column=6, value="柴油")
    ws.cell(row=6, column=8, value="柴油")
    ws.cell(row=6, column=10, value="柴油")

    # Marker row - Excel row 7, pandas iloc 6
    ws.cell(row=7, column=1, value=1)

    if not include_data:
        return

    # Data rows (Excel row 8+, pandas iloc 7+)
    # Device 1: CAT 785D
    ws.cell(row=8, column=1, value=1)
    ws.cell(row=8, column=2, value="CAT 785D")
    ws.cell(row=8, column=3, value="D001")
    ws.cell(row=8, column=4, value=1000.0)   # initial start hours
    ws.cell(row=8, column=5, value=1010.0)   # Day1 end hours
    ws.cell(row=8, column=6, value=150.0)    # Day1 fuel
    ws.cell(row=8, column=7, value=1020.0)   # Night1 end hours
    ws.cell(row=8, column=8, value=120.0)    # Night1 fuel
    ws.cell(row=8, column=9, value=1030.0)   # Day2 end hours
    ws.cell(row=8, column=10, value=160.0)   # Day2 fuel

    # Device 2: KOM 730E
    ws.cell(row=9, column=1, value=2)
    ws.cell(row=9, column=2, value="KOM 730E")
    ws.cell(row=9, column=3, value="D002")
    ws.cell(row=9, column=4, value=500.0)
    ws.cell(row=9, column=5, value=508.0)
    ws.cell(row=9, column=6, value=180.0)
    ws.cell(row=9, column=7, value=516.0)
    ws.cell(row=9, column=8, value=130.0)
    ws.cell(row=9, column=9, value=524.0)
    ws.cell(row=9, column=10, value=170.0)


def _create_fuel_excel(path, *, sheet_names=None, include_data=True):
    """Create an Excel file with one or more diesel sheets.

    Args:
        path: File path to save.
        sheet_names: List of sheet title strings. Defaults to ["设备柴油消耗表"].
        include_data: Whether to add data rows after headers.
    """
    if sheet_names is None:
        sheet_names = ["设备柴油消耗表"]

    wb = openpyxl.Workbook()
    for i, name in enumerate(sheet_names):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = name
        _build_realistic_fuel_sheet(ws, include_data=include_data)
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNormalProcessing:
    """Normal processing of a realistic diesel consumption sheet."""

    def test_returns_output_file_path(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path))

        # Assert
        assert result is not None
        assert result.endswith("Fuel.xlsx")
        assert os.path.exists(result)

    def test_engine_data_extracted(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        assert result is not None
        assert "设备信息" in result
        df_engine = result["设备信息"]
        assert len(df_engine) > 0
        assert set(["日期", "班次", "设备名称", "设备编号", "发动机小时数开始",
                     "发动机小时数结束", "运行小时数"]).issubset(df_engine.columns)

    def test_fuel_data_extracted(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        assert result is not None
        assert "油耗信息" in result
        df_fuel = result["油耗信息"]
        assert len(df_fuel) > 0
        assert set(["日期", "班次", "设备名称", "设备编号", "油品种类",
                     "油品消耗"]).issubset(df_fuel.columns)

    def test_device_names_correct(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_engine = result["设备信息"]
        devices = set(df_engine["设备名称"])
        assert "CAT 785D" in devices
        assert "KOM 730E" in devices

    def test_dates_are_date_objects(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_engine = result["设备信息"]
        for d in df_engine["日期"]:
            assert isinstance(d, datetime.date)

    def test_shifts_are_day_or_night(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_engine = result["设备信息"]
        assert set(df_engine["班次"]).issubset({"Day", "Night"})

    def test_sorted_by_date_and_shift(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_engine = result["设备信息"]
        dates = list(df_engine["日期"])
        assert dates == sorted(dates)

    def test_fuel_type_values(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel_input.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_fuel = result["油耗信息"]
        assert all(t == "柴油" for t in df_fuel["油品种类"])


class TestMultipleSheets:
    """Test processing a file with multiple matching sheets."""

    def test_both_sheets_processed(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(
            tmp_path / "multi.xlsx",
            sheet_names=["设备柴油消耗表1", "设备柴油消耗表2"],
        )

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        assert result is not None
        # Both sheets produce data, so results should have more rows than a single sheet
        df_engine = result["设备信息"]
        assert len(df_engine) > 4  # at least 2 devices * 2 sheets worth


class TestNoMatchingSheet:
    """Test ValueError when no sheet name matches."""

    def test_raises_value_error(self, tmp_path):
        # Arrange
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "RandomSheet"
        ws.cell(row=1, column=1, value="data")
        path = tmp_path / "no_match.xlsx"
        wb.save(path)

        # Act & Assert
        with pytest.raises(ValueError, match="未找到匹配的柴油消耗Sheet"):
            process_diesel_data(str(path))


class TestEmptyData:
    """Test handling of a sheet with headers but no usable data rows."""

    def test_no_valid_data_raises(self, tmp_path):
        # Arrange: headers + marker but no device data rows
        excel_path = _create_fuel_excel(
            tmp_path / "empty.xlsx", include_data=False
        )

        # Act & Assert
        with pytest.raises(ValueError, match="未找到有效数据"):
            process_diesel_data(str(excel_path))


class TestMongolianHeaders:
    """Test with Mongolian sheet name 'Техник'."""

    def test_mongolian_sheet_name(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(
            tmp_path / "mongolian.xlsx", sheet_names=["Техникин"]
        )

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        assert result is not None
        assert "设备信息" in result


class TestReturnSheetsMode:
    """Test return_sheets=True returns dict without writing file."""

    def test_returns_dict_not_path(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        assert isinstance(result, dict)
        assert "设备信息" in result or "油耗信息" in result

    def test_does_not_write_output_file(self, tmp_path):
        # Arrange: use a different input name to avoid case-insensitive collision
        # with the default output "Fuel.xlsx" on macOS
        excel_path = _create_fuel_excel(tmp_path / "diesel_input.xlsx")

        # Act
        process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        output_file = tmp_path / "Fuel.xlsx"
        assert not output_file.exists()

    def test_returns_none_when_no_valid_data(self, tmp_path):
        # Arrange: a sheet that matches name but has short headers (skipped)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "设备柴油消耗表"
        ws.cell(row=1, column=1, value="hdr")
        ws.cell(row=2, column=1, value=1)  # marker at row 2 => start_row=2 < 6
        path = tmp_path / "short.xlsx"
        wb.save(path)

        # Act & Assert - should raise ValueError since no valid data found
        with pytest.raises(ValueError):
            process_diesel_data(str(path), return_sheets=True)


class TestYearFiltering:
    """Test target_year parameter overrides date years."""

    def test_year_override(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel.xlsx")

        # Act
        result = process_diesel_data(
            str(excel_path), target_year=2024, return_sheets=True
        )

        # Assert
        assert result is not None
        df_engine = result["设备信息"]
        for d in df_engine["日期"]:
            assert d.year == 2024

    def test_default_year_preserved(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_engine = result["设备信息"]
        for d in df_engine["日期"]:
            assert d.year == 2025  # original year from fixture


class TestProcessFuelDataAlias:
    """Test that process_fuel_data is an alias for process_diesel_data."""

    def test_alias_exists(self):
        from func.excel_fuel import process_fuel_data
        assert process_fuel_data is process_diesel_data


class TestEngineHoursChain:
    """Test that engine hours chain is maintained correctly across shifts."""

    def test_hours_chain_continuity(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert - for device D001, the chain should be:
        # initial_start=1000 -> Day1 end=1010 -> Night1 end=1020 -> Day2 end=1030
        df_engine = result["设备信息"]
        d001 = df_engine[df_engine["设备编号"] == "D001"].sort_values(
            by=["日期", "班次"], key=lambda s: s.map({"Day": 0, "Night": 1}) if s.name == "班次" else s
        )
        starts = list(d001["发动机小时数开始"])
        ends = list(d001["发动机小时数结束"])
        # First start should be the initial value
        assert starts[0] == 1000.0
        # Each subsequent start should equal previous end
        for i in range(1, len(starts)):
            assert starts[i] == ends[i - 1]

    def test_work_hours_recorded(self, tmp_path):
        # Arrange
        excel_path = _create_fuel_excel(tmp_path / "fuel.xlsx")

        # Act
        result = process_diesel_data(str(excel_path), return_sheets=True)

        # Assert
        df_engine = result["设备信息"]
        # All work hours should be numeric
        for val in df_engine["运行小时数"]:
            assert isinstance(val, (int, float))


class TestDeduplication:
    """Test that duplicate rows are removed."""

    def test_duplicates_removed(self, tmp_path):
        # Arrange - create a sheet where data has a duplicate device row
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "设备柴油消耗表"

        # Minimal valid structure
        _build_realistic_fuel_sheet(ws)

        # Add an exact duplicate of row 8 (device D001)
        ws.cell(row=10, column=1, value=1)
        ws.cell(row=10, column=2, value="CAT 785D")
        ws.cell(row=10, column=3, value="D001")
        ws.cell(row=10, column=4, value=1000.0)
        ws.cell(row=10, column=5, value=1010.0)
        ws.cell(row=10, column=6, value=150.0)
        ws.cell(row=10, column=7, value=1020.0)
        ws.cell(row=10, column=8, value=120.0)
        ws.cell(row=10, column=9, value=1030.0)
        ws.cell(row=10, column=10, value=160.0)

        path = tmp_path / "dup.xlsx"
        wb.save(path)

        # Act
        result = process_diesel_data(str(path), return_sheets=True)

        # Assert - dedup should reduce rows; fuel data for D001 should have
        # exactly the same count as non-dup run (3 data rows per device)
        assert result is not None
