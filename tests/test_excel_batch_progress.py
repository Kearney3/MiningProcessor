"""excel_batch progress callback tests."""
import pathlib
import sys
import threading

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import func.excel_batch as batch_mod
from func.excel_batch import process_files


@pytest.fixture(autouse=True)
def _patch_fuel_processing(monkeypatch):
    df = pd.DataFrame(
        {
            "日期": ["2025-01-01"],
            "班次": ["Night"],
            "标准设备名称": ["TR100 #1"],
            "设备名称": ["TR100 #1"],
            "设备编号": ["T-001"],
            "油品消耗": [12],
        }
    )

    def fake_process_fuel_data(file_path, target_year=None, return_sheets=False):
        return {"设备信息": df.copy(), "油耗信息": df.copy()}

    monkeypatch.setattr(batch_mod, "process_fuel_data", fake_process_fuel_data)


def test_separate_output_reports_file_progress(tmp_path):
    events = []

    def on_progress(payload):
        events.append(payload)

    process_files(
        folder_path=str(tmp_path),
        matched={"fuel": ["dummy.xlsx"]},
        merge_output=False,
        progress_cb=on_progress,
    )

    assert events[0] == {"stage": "preparing", "percent": 0.0, "current": 0, "total": 0, "detail": "开始处理"}
    writing_events = [e for e in events if e["stage"] == "writing"]
    assert len(writing_events) >= 2
    assert writing_events[0]["detail"] == "开始分开输出"
    assert writing_events[-1]["current"] == 1
    assert writing_events[-1]["total"] == 1
    assert events[-1]["stage"] == "finished"
    assert events[-1]["percent"] == pytest.approx(1.0)


def test_cancel_event_stops_before_output(tmp_path):
    cancel = threading.Event()
    cancel.set()
    events = []

    def on_progress(payload):
        events.append(payload)

    process_files(
        folder_path=str(tmp_path),
        matched={"fuel": ["dummy.xlsx"]},
        merge_output=False,
        cancel_event=cancel,
        progress_cb=on_progress,
    )

    assert events[-1]["stage"] == "cancelled"
    assert not (tmp_path / "Fuel.xlsx").exists()


def test_merged_output_reports_sheet_progress(tmp_path):
    events = []

    def on_progress(payload):
        events.append(payload)

    process_files(
        folder_path=str(tmp_path),
        matched={"fuel": ["dummy.xlsx"]},
        merge_output=True,
        progress_cb=on_progress,
    )

    writing_events = [e for e in events if e["stage"] == "writing"]
    assert writing_events[0]["detail"] == "开始合并输出"
    assert writing_events[-1]["current"] == 2
    assert writing_events[-1]["total"] == 2
    assert events[-1]["stage"] == "finished"
    assert events[-1]["percent"] == pytest.approx(1.0)


def test_table_merge_reports_fixed_steps(tmp_path):
    events = []

    def on_progress(payload):
        events.append(payload)

    process_files(
        folder_path=str(tmp_path),
        matched={"fuel": ["dummy.xlsx"]},
        merge_output=True,
        table_merge_config={"base_type": "fuel"},
        progress_cb=on_progress,
    )

    table_events = [e for e in events if e.get("detail", "").startswith("表内合并")]
    assert [e["stage"] for e in table_events] == ["writing", "writing", "finished"]
    assert table_events[-1]["percent"] == pytest.approx(1.0)
    assert table_events[-1]["current"] == 3
    assert table_events[-1]["total"] == 3
