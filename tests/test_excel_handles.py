"""Tests that pd.ExcelFile handles are properly closed via context managers."""
import os
import tempfile
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_sample_excel(path: str) -> None:
    """Write a minimal two-sheet Excel file for testing."""
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Sheet1", index=False)
        pd.DataFrame({"B": [2]}).to_excel(writer, sheet_name="Sheet2", index=False)


# ---------------------------------------------------------------------------
# Tests: each processor closes its ExcelFile handle
# ---------------------------------------------------------------------------

class TestExcelFuelHandleClosed:
    """func.excel_fuel.process_diesel_data should close its ExcelFile."""

    def test_excelfile_enter_exit_called(self):
        """The context manager __enter__ and __exit__ must both fire."""
        from func.excel_fuel import process_diesel_data

        enter_called = False
        exit_called = False
        original_init = pd.ExcelFile.__init__
        original_enter = pd.ExcelFile.__enter__
        original_exit = pd.ExcelFile.__exit__

        def tracked_enter(self_inner):
            nonlocal enter_called
            enter_called = True
            return original_enter(self_inner)

        def tracked_exit(self_inner, *args):
            nonlocal exit_called
            exit_called = True
            return original_exit(self_inner, *args)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            _create_sample_excel(tmp.name)
            tmp_path = tmp.name

        try:
            with patch.object(pd.ExcelFile, "__enter__", tracked_enter), \
                 patch.object(pd.ExcelFile, "__exit__", tracked_exit):
                with pytest.raises(ValueError):
                    # No matching sheets -> raises, but handle should still close
                    process_diesel_data(tmp_path)

            assert enter_called, "__enter__ was never called on ExcelFile"
            assert exit_called, "__exit__ was never called on ExcelFile"
        finally:
            os.unlink(tmp_path)


class TestExcelElectricalHandleClosed:
    """func.excel_electrical.parse_excel_data should close its ExcelFile."""

    def test_excelfile_enter_exit_called(self):
        from func.excel_electrical import parse_excel_data

        enter_called = False
        exit_called = False
        original_enter = pd.ExcelFile.__enter__
        original_exit = pd.ExcelFile.__exit__

        def tracked_enter(self_inner):
            nonlocal enter_called
            enter_called = True
            return original_enter(self_inner)

        def tracked_exit(self_inner, *args):
            nonlocal exit_called
            exit_called = True
            return original_exit(self_inner, *args)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            _create_sample_excel(tmp.name)
            tmp_path = tmp.name

        try:
            with patch.object(pd.ExcelFile, "__enter__", tracked_enter), \
                 patch.object(pd.ExcelFile, "__exit__", tracked_exit):
                # No "Electrical" sheets -> returns None, but handle must close
                result = parse_excel_data(tmp_path)

            assert enter_called, "__enter__ was never called on ExcelFile"
            assert exit_called, "__exit__ was never called on ExcelFile"
        finally:
            os.unlink(tmp_path)


class TestExcelWorktimeHandleClosed:
    """func.excel_worktime.process_excel_data should close its ExcelFile."""

    def test_excelfile_enter_exit_called(self):
        from func.excel_worktime import process_excel_data

        enter_called = False
        exit_called = False
        original_enter = pd.ExcelFile.__enter__
        original_exit = pd.ExcelFile.__exit__

        def tracked_enter(self_inner):
            nonlocal enter_called
            enter_called = True
            return original_enter(self_inner)

        def tracked_exit(self_inner, *args):
            nonlocal exit_called
            exit_called = True
            return original_exit(self_inner, *args)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            _create_sample_excel(tmp.name)
            tmp_path = tmp.name

        try:
            with patch.object(pd.ExcelFile, "__enter__", tracked_enter), \
                 patch.object(pd.ExcelFile, "__exit__", tracked_exit):
                # Sheets are not numeric -> no data, but handle must close
                process_excel_data(tmp_path, year=2025, month=1)

            assert enter_called, "__enter__ was never called on ExcelFile"
            assert exit_called, "__exit__ was never called on ExcelFile"
        finally:
            os.unlink(tmp_path)


class TestExcelProductionEnhancedHandleClosed:
    """func.excel_production_enhanced.MiningDataProcessor.process_single_file
    should close its ExcelFile."""

    def test_excelfile_enter_exit_called(self):
        from func.excel_production_enhanced import MiningDataProcessor

        enter_called = False
        exit_called = False
        original_enter = pd.ExcelFile.__enter__
        original_exit = pd.ExcelFile.__exit__

        def tracked_enter(self_inner):
            nonlocal enter_called
            enter_called = True
            return original_enter(self_inner)

        def tracked_exit(self_inner, *args):
            nonlocal exit_called
            exit_called = True
            return original_exit(self_inner, *args)

        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", prefix="2025.01.01_白班_", delete=False
        ) as tmp:
            _create_sample_excel(tmp.name)
            tmp_path = tmp.name

        try:
            processor = MiningDataProcessor(device_load_map={})
            with patch.object(pd.ExcelFile, "__enter__", tracked_enter), \
                 patch.object(pd.ExcelFile, "__exit__", tracked_exit):
                try:
                    processor.process_single_file(tmp_path)
                except Exception:
                    pass  # parsing may fail on our minimal file, that's fine

            assert enter_called, "__enter__ was never called on ExcelFile"
            assert exit_called, "__exit__ was never called on ExcelFile"
        finally:
            os.unlink(tmp_path)


class TestExcelWorktimeMultifileHandleClosed:
    """func.excel_worktime_multifile.process_directory should close its ExcelFile."""

    def test_excelfile_enter_exit_called(self):
        from func.excel_worktime_multifile import process_directory

        enter_called = False
        exit_called = False
        original_enter = pd.ExcelFile.__enter__
        original_exit = pd.ExcelFile.__exit__

        def tracked_enter(self_inner):
            nonlocal enter_called
            enter_called = True
            return original_enter(self_inner)

        def tracked_exit(self_inner, *args):
            nonlocal exit_called
            exit_called = True
            return original_exit(self_inner, *args)

        # Create a directory structure: base/01/Tsag_01.xlsx
        with tempfile.TemporaryDirectory() as base_dir:
            day_dir = os.path.join(base_dir, "01")
            os.makedirs(day_dir)
            excel_path = os.path.join(day_dir, "Tsag_01.xlsx")
            with pd.ExcelWriter(excel_path) as writer:
                pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="1", index=False)

            with patch.object(pd.ExcelFile, "__enter__", tracked_enter), \
                 patch.object(pd.ExcelFile, "__exit__", tracked_exit):
                output = os.path.join(base_dir, "output.xlsx")
                try:
                    process_directory(base_dir, year=2025, month=1, output_file=output)
                except SystemExit:
                    pass

            assert enter_called, "__enter__ was never called on ExcelFile"
            assert exit_called, "__exit__ was never called on ExcelFile"


class TestExcelMergerHandleClosed:
    """func.excel_merger.merge_excel_files should close all cached ExcelFile handles."""

    def test_xl_cache_values_closed(self):
        from func.excel_merger import merge_excel_files

        closed_instances = []
        original_close = pd.ExcelFile.close

        def tracking_close(self_inner):
            closed_instances.append(self_inner)
            return original_close(self_inner)

        with tempfile.TemporaryDirectory() as folder:
            # Create two matching Excel files
            for name in ("data_1.xlsx", "data_2.xlsx"):
                path = os.path.join(folder, name)
                with pd.ExcelWriter(path) as writer:
                    pd.DataFrame({"日期": ["2025-01-01"], "值": [10]}).to_excel(
                        writer, sheet_name="Data", index=False
                    )

            with patch.object(pd.ExcelFile, "close", tracking_close):
                output = os.path.join(folder, "merged.xlsx")
                merge_excel_files(folder, keyword="data", output_file=output)

            # Each file opened once -> close called once per file
            assert len(closed_instances) >= 2, (
                f"Expected at least 2 close() calls, got {len(closed_instances)}"
            )
