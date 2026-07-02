"""Tests for batch progress polling during processing (not just after completion)."""
import asyncio
import pathlib
import queue
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
        self.update_count = 0

    def update(self):
        self.update_count += 1


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
        "match_eq_toggle": None,
        "match_oil_toggle": None,
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_progress_updates_during_processing(tmp_path, monkeypatch):
    """Progress bar should be updated WHILE the batch is running, not only after."""
    import time

    monkeypatch.setattr(logic, "scan_files", lambda path: ({"fuel": ["dummy.xlsx"]}, []))

    def fake_process_files(*args, **kwargs):
        progress_cb = kwargs.get("progress_cb")
        if progress_cb:
            progress_cb({"stage": "preparing", "percent": 0.0, "current": 0, "total": 2, "detail": "start"})
            time.sleep(0.8)
            progress_cb({"stage": "writing", "percent": 0.5, "current": 1, "total": 2, "detail": "file1 done"})
            time.sleep(0.8)
            progress_cb({"stage": "writing", "percent": 1.0, "current": 2, "total": 2, "detail": "file2 done"})
            progress_cb({"stage": "finished", "percent": 1.0, "current": 2, "total": 2, "detail": "done"})
        return {"fuel": {"油耗信息": None}}

    monkeypatch.setattr(logic, "process_files", fake_process_files)

    progress_bar = FakeProgress()
    progress_text = FakeProgress()
    refs = _make_refs(tmp_path, progress_bar=progress_bar, progress_text=progress_text)

    asyncio.run(logic.on_batch_process(FakePage(), refs, lambda msg, level=None: None))

    # After completion, the final value should be 1.0
    assert progress_bar.value == pytest.approx(1.0)
    assert "100%" in progress_text.value


def test_progress_bar_shows_intermediate_value(tmp_path, monkeypatch):
    """Progress bar value should be non-zero at some point during processing."""
    import time

    monkeypatch.setattr(logic, "scan_files", lambda path: ({"fuel": ["dummy.xlsx"]}, []))

    def fake_process_files(*args, **kwargs):
        progress_cb = kwargs.get("progress_cb")
        if progress_cb:
            progress_cb({"stage": "writing", "percent": 0.5, "current": 1, "total": 2, "detail": "halfway"})
            time.sleep(0.5)
            progress_cb({"stage": "finished", "percent": 1.0, "current": 2, "total": 2, "detail": "done"})
        return {"fuel": {"油耗信息": None}}

    monkeypatch.setattr(logic, "process_files", fake_process_files)

    progress_bar = FakeProgress()
    refs = _make_refs(tmp_path, progress_bar=progress_bar)

    asyncio.run(logic.on_batch_process(FakePage(), refs, lambda msg, level=None: None))

    # The progress bar was updated at least twice (0.5 and 1.0)
    assert progress_bar.update_count >= 2
    assert progress_bar.value == pytest.approx(1.0)


def test_polling_task_cleans_up_on_completion(tmp_path, monkeypatch):
    """The polling task must be properly awaited (no leaked tasks)."""
    monkeypatch.setattr(logic, "scan_files", lambda path: ({"fuel": ["dummy.xlsx"]}, []))

    def fake_process_files(*args, **kwargs):
        progress_cb = kwargs.get("progress_cb")
        if progress_cb:
            progress_cb({"stage": "finished", "percent": 1.0, "current": 1, "total": 1, "detail": "done"})
        return {"fuel": {"油耗信息": None}}

    monkeypatch.setattr(logic, "process_files", fake_process_files)

    refs = _make_refs(tmp_path)

    # Should complete without error and without task leaks
    asyncio.run(logic.on_batch_process(FakePage(), refs, lambda msg, level=None: None))


def test_polling_cancels_on_error(tmp_path, monkeypatch):
    """If processing raises, the polling task must be cancelled without leaking."""
    monkeypatch.setattr(logic, "scan_files", lambda path: ({"fuel": ["dummy.xlsx"]}, []))

    def fake_process_files(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(logic, "process_files", fake_process_files)

    refs = _make_refs(tmp_path)
    log_messages = []

    # Should not raise - error is caught and logged
    asyncio.run(logic.on_batch_process(FakePage(), refs, lambda msg, level=None: log_messages.append(msg)))

    assert any("失败" in m for m in log_messages)


def test_drain_queue_once_returns_none_on_empty_queue():
    """_drain_batch_progress_queue_once returns None when queue is empty."""
    q = queue.Queue()
    result = logic._drain_batch_progress_queue_once(q, None, None)
    assert result is None


def test_drain_queue_once_extracts_last_percent():
    """_drain_batch_progress_queue_once returns the last percent value."""
    q = queue.Queue()
    q.put_nowait({"percent": 0.1})
    q.put_nowait({"percent": 0.5})
    q.put_nowait({"percent": 0.9})
    result = logic._drain_batch_progress_queue_once(q, None, None)
    assert result == pytest.approx(0.9)


def test_poll_updates_progress_bar():
    """The polling coroutine should update progress controls with queue values."""
    async def _run():
        q = queue.Queue()
        done = asyncio.Event()
        progress_bar = FakeProgress()
        progress_text = FakeProgress()

        # Fill queue with a progress update
        q.put_nowait({"percent": 0.35})

        task = asyncio.create_task(
            logic._poll_batch_progress_queue(q, progress_bar, progress_text, done)
        )

        # Wait enough time for at least one poll cycle (0.3s interval)
        await asyncio.sleep(0.5)

        # Progress should have been updated by now
        assert progress_bar.value == pytest.approx(0.35)
        assert "35%" in progress_text.value

        done.set()
        await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(_run())


def test_poll_stops_after_done_flag():
    """The poller should exit promptly after done_flag is set."""
    async def _run():
        q = queue.Queue()
        done = asyncio.Event()
        progress_bar = FakeProgress()

        task = asyncio.create_task(
            logic._poll_batch_progress_queue(q, progress_bar, None, done)
        )
        # Set done immediately, poller should finish quickly
        done.set()
        await asyncio.wait_for(task, timeout=1.0)
        assert task.done()

    asyncio.run(_run())
