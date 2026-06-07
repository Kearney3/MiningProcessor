"""GUI batch progress logic tests."""
import asyncio
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gui.logic as logic


class FakeBtn:
    def __init__(self):
        self.disabled = False
        self.text = ""
        self.style = None

    def update(self):
        pass


class FakeProgress:
    def __init__(self):
        self.value = 0.0
        self.visible = False

    def update(self):
        pass


class FakeCancel:
    def __init__(self):
        self.disabled = False
        self.visible = False
        self.on_click = None

    def update(self):
        pass


class FakeProgressRow:
    def __init__(self):
        self.visible = False

    def update(self):
        pass


def _make_refs(tmp_path, cancel_event=None, progress_bar=None, progress_text=None, cancel_btn=None, progress_row=None):
    return {
        "path": types.SimpleNamespace(value=str(tmp_path)),
        "year": types.SimpleNamespace(value="2025"),
        "month": types.SimpleNamespace(value="1"),
        "auto_detect": types.SimpleNamespace(value=True),
        "merge": types.SimpleNamespace(value=True),
        "table_merge": None,
        "base_table": None,
        "ledger_toggle": None,
        "header_toggle": None,
        "header_mode": None,
        "header_fuzzy": None,
        "date_filter_toggle": None,
        "selected_date": [None],
        "btn": FakeBtn(),
        "progress_bar": progress_bar or FakeProgress(),
        "progress_text": progress_text or FakeProgress(),
        "cancel_btn": cancel_btn or FakeCancel(),
        "progress_row": progress_row or FakeProgressRow(),
        "cancel_event": cancel_event,
    }


class FakePage:
    def __init__(self):
        self.overlay = []

    def pop_dialog(self):
        pass

    def show_dialog(self, dialog):
        pass

    def update(self):
        pass


def test_on_batch_process_updates_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "scan_files", lambda path: ({"fuel": ["dummy.xlsx"]}, []))

    captured = {}

    def fake_process_files(*args, **kwargs):
        progress_cb = kwargs.get("progress_cb")
        if progress_cb:
            progress_cb({"stage": "preparing", "percent": 0.0, "current": 0, "total": 0, "detail": "开始处理"})
            progress_cb({"stage": "finished", "percent": 1.0, "current": 1, "total": 1, "detail": "分开输出完成"})
        captured["cancel_event"] = kwargs.get("cancel_event")
        return {"fuel": {"油耗信息": None}}

    monkeypatch.setattr(logic, "process_files", fake_process_files)

    progress_bar = FakeProgress()
    progress_text = FakeProgress()
    progress_row = FakeProgressRow()
    refs = _make_refs(tmp_path, progress_bar=progress_bar, progress_text=progress_text, progress_row=progress_row)

    asyncio.run(logic.on_batch_process(FakePage(), refs, lambda msg, level=None: None))

    assert progress_row.visible is False
    assert progress_bar.value == pytest.approx(1.0)
    assert "100%" in progress_text.value
    assert captured["cancel_event"] is not None


def test_on_batch_process_cancel_disables_button(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "scan_files", lambda path: ({"fuel": ["dummy.xlsx"]}, []))

    def fake_process_files(*args, **kwargs):
        return {"fuel": {"油耗信息": None}}

    monkeypatch.setattr(logic, "process_files", fake_process_files)

    cancel_btn = FakeCancel()
    refs = _make_refs(tmp_path, cancel_btn=cancel_btn)

    asyncio.run(logic.on_batch_process(FakePage(), refs, lambda msg, level=None: None))

    assert cancel_btn.on_click is not None
    cancel_btn.on_click(None)
    assert cancel_btn.disabled is True
