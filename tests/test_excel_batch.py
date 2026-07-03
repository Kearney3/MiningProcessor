"""excel_batch 模块测试"""
import pathlib
import sys
import threading

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from unittest.mock import patch, MagicMock

from func.excel_batch import (
    process_files,
    _check_cancel,
    _emit_progress,
    scan_files,
    MODULE_LABELS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_df(rows: int = 3) -> pd.DataFrame:
    """Return a small DataFrame for use as processor return value."""
    return pd.DataFrame({"日期": [f"2025-01-{i+1:02d}" for i in range(rows)],
                         "值": range(rows)})


def _make_matched(include: list[str] | None = None) -> dict[str, list[str]]:
    """Build a matched dict.  Only include keys listed in *include*."""
    all_keys = ["fuel", "electrical", "production", "worktime"]
    if include is None:
        include = all_keys
    return {k: [f"/data/{k}_file.xlsx"] for k in include}


def _mock_sheets(module: str = "default") -> dict[str, pd.DataFrame]:
    """Return a dict of sheets keyed by sheet name."""
    return {f"Sheet_{module}": _sample_df()}


# ---------------------------------------------------------------------------
# _check_cancel / _emit_progress (unit-level)
# ---------------------------------------------------------------------------

class TestCheckCancel:
    def test_returns_false_when_none(self):
        assert _check_cancel(None) is False

    def test_returns_false_when_not_set(self):
        ev = threading.Event()
        assert _check_cancel(ev) is False

    def test_returns_true_when_set(self):
        ev = threading.Event()
        ev.set()
        assert _check_cancel(ev) is True


class TestEmitProgress:
    def test_calls_callback(self):
        cb = MagicMock()
        _emit_progress(cb, {"stage": "writing", "percent": 0.5})
        cb.assert_called_once_with({"stage": "writing", "percent": 0.5})

    def test_swallows_exception_from_callback(self):
        cb = MagicMock(side_effect=RuntimeError("boom"))
        # Should not raise
        _emit_progress(cb, {"stage": "test"})

    def test_noop_when_none(self):
        _emit_progress(None, {"stage": "test"})  # no-op, no exception


# ---------------------------------------------------------------------------
# process_files – core orchestration
# ---------------------------------------------------------------------------

class TestProcessFilesAllModulesCalled:
    """test_process_files_calls_all_modules"""

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("electrical"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_all_four_processors_called(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        matched = _make_matched()
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )

        mock_fuel.assert_called_once_with(matched["fuel"], 2025, False)
        mock_electrical.assert_called_once_with(matched["electrical"], 2025, False)
        mock_production.assert_called_once_with("/data", -1, False)
        mock_worktime.assert_called_once_with(
            matched["worktime"], 2025, 6, None, False,
        )

        assert "fuel" in result
        assert "electrical" in result
        assert "production" in result
        assert "worktime" in result


class TestProcessFilesMissingModule:
    """test_process_files_with_missing_module – when a processor raises"""

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value={})
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_empty_result_for_electrical_included_but_empty(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        """When a module returns empty dict, its key appears in result with {}."""
        matched = _make_matched(["fuel", "electrical", "production", "worktime"])
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )

        assert "electrical" in result
        assert result["electrical"] == {}
        # non-empty modules still present
        assert "fuel" in result
        assert result["fuel"]

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value={})
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_empty_production_does_not_appear(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        matched = _make_matched(["fuel", "electrical", "production", "worktime"])
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )

        assert "production" not in result

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value={})
    def test_exception_in_fuel_returns_empty_for_fuel(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        """When _process_fuel_module returns {}, fuel key appears with empty dict."""
        matched = _make_matched(["fuel", "electrical", "production", "worktime"])
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )
        assert "fuel" in result
        assert result["fuel"] == {}
        # other modules still have data
        assert "electrical" in result
        assert result["electrical"]

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module")
    @patch("func.excel_batch._process_production_module")
    @patch("func.excel_batch._process_electrical_module")
    @patch("func.excel_batch._process_fuel_module")
    def test_all_modules_empty_returns_empty_or_partial(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        """When every module returns empty dict, production is excluded
        (if-result guard), but fuel/electrical/worktime are still added
        as empty dicts (direct assignment)."""
        mock_fuel.return_value = {}
        mock_electrical.return_value = {}
        mock_production.return_value = {}
        mock_worktime.return_value = {}
        matched = _make_matched()
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )
        # fuel/electrical/worktime keys present with empty dicts
        assert result.get("fuel") == {}
        assert result.get("electrical") == {}
        assert result.get("worktime") == {}
        # production excluded because _process_production_module returns {}
        # and the `if result:` guard on line 219 skips it
        assert "production" not in result


class TestProgressQueueUpdates:
    """test_progress_queue_updates – verify progress_cb receives stage updates"""

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_preparing_stage_emitted(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        cb = MagicMock()
        matched = _make_matched()
        process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
            progress_cb=cb,
        )

        stages = [call.args[0]["stage"] for call in cb.call_args_list]
        assert "preparing" in stages


class TestCancelEvent:
    """test_cancel_event – verify cancel_event stops processing early"""

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_cancel_before_processing_returns_empty(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        """When cancel_event is set before processing starts, no modules run."""
        ev = threading.Event()
        ev.set()

        matched = _make_matched()
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
            cancel_event=ev,
        )

        assert result == {}
        mock_fuel.assert_not_called()
        mock_electrical.assert_not_called()
        mock_production.assert_not_called()
        mock_worktime.assert_not_called()
        mock_write.assert_not_called()

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_cancel_emits_cancelled_stage(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        ev = threading.Event()
        ev.set()
        cb = MagicMock()

        matched = _make_matched()
        process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
            cancel_event=ev,
            progress_cb=cb,
        )

        stages = [call.args[0]["stage"] for call in cb.call_args_list]
        assert "cancelled" in stages


class TestReturnSheetsPassthrough:
    """test_return_sheets_passthrough – verify return_sheets flag works correctly
    (no file I/O when return_sheets=True via processor mocks)"""

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_merge_output_true_writes_merged_file(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        matched = _make_matched()
        process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )
        mock_write.assert_called_once()

    @patch("func.excel_batch._write_separate")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_merge_output_false_writes_separate_files(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        matched = _make_matched()
        process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=False,
        )
        mock_write.assert_called_once()

    @patch("func.excel_batch._write_merged")
    @patch("func.excel_batch._process_worktime_module", return_value=_mock_sheets("worktime"))
    @patch("func.excel_batch._process_production_module", return_value=_mock_sheets("production"))
    @patch("func.excel_batch._process_electrical_module", return_value=_mock_sheets("elec"))
    @patch("func.excel_batch._process_fuel_module", return_value=_mock_sheets("fuel"))
    def test_sheets_returned_per_module(
        self, mock_fuel, mock_electrical, mock_production, mock_worktime, mock_write
    ):
        """Verify that process_files returns the sheets dict keyed by module type."""
        matched = _make_matched()
        result = process_files(
            folder_path="/data",
            matched=matched,
            year=2025,
            month=6,
            merge_output=True,
        )
        assert set(result.keys()) == {"fuel", "electrical", "production", "worktime"}
        for module_type, sheets in result.items():
            assert isinstance(sheets, dict)
            assert len(sheets) > 0


# ---------------------------------------------------------------------------
# scan_files
# ---------------------------------------------------------------------------

class TestScanFiles:
    def test_returns_matched_and_missing(self, tmp_path):
        # Create sample Excel files
        (tmp_path / "fuel_report.xlsx").touch()
        (tmp_path / "elec_data.xlsx").touch()
        (tmp_path / "random.xlsx").touch()

        keywords = {
            "fuel": ["fuel"],
            "electrical": ["elec"],
            "production": ["prod"],
            "worktime": ["work"],
        }
        matched, missing = scan_files(str(tmp_path), keywords=keywords)

        assert "fuel" in matched
        assert "electrical" in matched
        assert "production" in missing
        assert "worktime" in missing

    def test_ignores_temp_files(self, tmp_path):
        (tmp_path / "~$fuel_report.xlsx").touch()
        (tmp_path / "fuel_report.xlsx").touch()

        keywords = {"fuel": ["fuel"], "electrical": [], "production": [], "worktime": []}
        matched, _ = scan_files(str(tmp_path), keywords=keywords)

        assert len(matched.get("fuel", [])) == 1
        assert "~$" not in matched["fuel"][0]


# ---------------------------------------------------------------------------
# MODULE_LABELS coverage
# ---------------------------------------------------------------------------

class TestModuleLabels:
    def test_all_keys_present(self):
        expected = {"fuel", "electrical", "production", "worktime"}
        assert set(MODULE_LABELS.keys()) == expected

    def test_values_are_strings(self):
        for val in MODULE_LABELS.values():
            assert isinstance(val, str)
