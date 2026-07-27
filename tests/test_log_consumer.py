"""真实 GUI 日志 broker/controller 链路测试。"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from types import SimpleNamespace

import pytest

from gui.log_broker import LogEntry, LogSubscription, get_log_broker, install_gui_log_handler
from gui.log_system import LogSystem, MAX_RENDERED_RECORDS


class StubControl:
    def __init__(self, value=None, height=None):
        self.value = value
        self.height = height
        self.on_click = None
        self.on_select = None
        self.on_vertical_drag_start = None
        self.on_vertical_drag_update = None
        self.update_count = 0

    def update(self):
        self.update_count += 1


class StubLogList(StubControl):
    def __init__(self):
        super().__init__()
        self.controls = []
        self.scroll_count = 0
        self.on_scroll = None

    def scroll_to(self, **_kwargs):
        self.scroll_count += 1


class ImmediatePage:
    """在调用线程执行短生命周期 coroutine。"""

    def __init__(self):
        self.services = []
        self.window = SimpleNamespace(on_resize=None)
        self.task_calls = 0

    def run_task(self, handler, *args, **kwargs):
        self.task_calls += 1
        future = concurrent.futures.Future()
        try:
            result = asyncio.run(handler(*args, **kwargs))
        except BaseException as ex:
            future.set_exception(ex)
            raise
        future.set_result(result)
        return future


class DeferredPage(ImmediatePage):
    """保存调度请求，用于构造 clear/filter 与 pending 日志交错。"""

    def __init__(self):
        super().__init__()
        self.pending = []

    def run_task(self, handler, *args, **kwargs):
        self.task_calls += 1
        future = concurrent.futures.Future()
        self.pending.append((handler, args, kwargs, future))
        return future

    def run_pending(self):
        while self.pending:
            handler, args, kwargs, future = self.pending.pop(0)
            try:
                result = asyncio.run(handler(*args, **kwargs))
            except BaseException as ex:
                future.set_exception(ex)
                raise
            future.set_result(result)


def make_refs():
    return {
        "follow_status": StubControl(),
        "log_list": StubLogList(),
        "list_container": StubControl(height=300),
        "level_filter": StubControl(value="INFO"),
        "export_button": StubControl(),
        "resize_handle": StubControl(),
        "clear_button": StubControl(),
        "scroll_bottom_button": StubControl(),
    }


@pytest.fixture(autouse=True)
def isolated_gui_logging():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    broker = get_log_broker()
    broker.reset_for_testing()
    install_gui_log_handler()
    yield
    broker.reset_for_testing()
    root.handlers = original_handlers
    root.setLevel(original_level)


def values(refs):
    return [control.value for control in refs["log_list"].controls]


def test_real_pipeline_delivers_ordered_burst():
    page = ImmediatePage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()

    for index in range(25):
        logging.getLogger("test.pipeline").info("message-%02d", index)

    displayed = values(refs)
    indices = [int(value.rsplit("message-", 1)[1]) for value in displayed]
    assert indices == list(range(25))
    assert page.task_calls == 25


def test_flush_requests_coalesce_while_page_is_busy():
    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()

    for index in range(100):
        logging.getLogger("test.coalesce").info("burst-%d", index)

    assert page.task_calls == 1
    page.run_pending()
    assert len(values(refs)) == 100


def test_subscription_overflow_preserves_warning_and_latest_regular_logs():
    subscription = LogSubscription(lambda: None, capacity=3)
    subscription.publish(LogEntry(1, 0, logging.ERROR, "ERROR", "test", "important"))
    for sequence in range(2, 6):
        subscription.publish(LogEntry(sequence, 0, logging.INFO, "INFO", "test", str(sequence)))

    entries, dropped = subscription.drain()

    assert [entry.sequence for entry in entries] == [1, 4, 5]
    assert dropped == 2


def test_important_log_evicts_regular_log_when_subscription_is_full():
    subscription = LogSubscription(lambda: None, capacity=2)
    subscription.publish(LogEntry(1, 0, logging.INFO, "INFO", "test", "regular-1"))
    subscription.publish(LogEntry(2, 0, logging.INFO, "INFO", "test", "regular-2"))
    subscription.publish(LogEntry(3, 0, logging.WARNING, "WARNING", "test", "warning"))

    entries, dropped = subscription.drain()

    assert [entry.sequence for entry in entries] == [2, 3]
    assert dropped == 1


def test_clear_discards_records_already_pending_but_keeps_new_logs():
    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()

    logging.getLogger("test.clear").info("before-clear")
    asyncio.run(system._clear_logs())
    page.run_pending()
    assert not any("before-clear" in value for value in values(refs))

    logging.getLogger("test.clear").info("after-clear")
    page.run_pending()
    assert any("after-clear" in value for value in values(refs))


def test_filter_rebuild_cannot_overwrite_newer_log_batch():
    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()

    logging.getLogger("test.filter").info("info-entry")
    logging.getLogger("test.filter").error("error-entry")
    refs["level_filter"].value = "ERROR"
    asyncio.run(system._apply_filters())
    logging.getLogger("test.filter").error("later-error")
    page.run_pending()

    displayed = values(refs)
    assert not any("info-entry" in value for value in displayed)
    assert any("error-entry" in value for value in displayed)
    assert any("later-error" in value for value in displayed)


def test_manual_scroll_pauses_following_until_scroll_bottom_is_clicked():
    page = ImmediatePage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()
    system._on_log_scroll(SimpleNamespace(pixels=200, max_scroll_extent=1000))

    logging.getLogger("test.scroll").info("while-reading-history")
    assert refs["log_list"].scroll_count == 0
    assert refs["follow_status"].visible is True
    assert refs["scroll_bottom_button"].tooltip == "滚动到底部并恢复自动跟随"

    asyncio.run(system._scroll_to_bottom())
    logging.getLogger("test.scroll").info("following-again")
    assert refs["log_list"].scroll_count == 2
    assert refs["follow_status"].visible is False


def test_export_preserves_traceback_while_ui_only_shows_root_message(monkeypatch, tmp_path):
    from func import config_loader
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")

    class ExportPicker:
        async def save_file(self, **_kwargs):
            return str(tmp_path / "diagnostic.log")

    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()
    try:
        raise ValueError("diagnostic detail")
    except ValueError:
        logging.getLogger("test.export").exception("processing failed")
    page.run_pending()

    assert any("processing failed" in value for value in values(refs))
    assert not any("Traceback" in value for value in values(refs))

    system._log_export_picker = ExportPicker()
    asyncio.run(system._export_logs(None))
    exported = (tmp_path / "diagnostic.log").read_text(encoding="utf-8")

    assert "Traceback" in exported
    assert "ValueError: diagnostic detail" in exported


def test_export_write_failure_is_reported_without_raising(monkeypatch, tmp_path):
    from func import config_loader
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")

    class ExportPicker:
        async def save_file(self, **_kwargs):
            return str(tmp_path / "missing-directory" / "diagnostic.log")

    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()
    system._log_export_picker = ExportPicker()

    asyncio.run(system._export_logs(None))
    page.run_pending()

    assert any("日志导出失败" in value for value in values(refs))


def test_rendered_controls_are_bounded_below_history_capacity():
    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()
    for index in range(MAX_RENDERED_RECORDS + 250):
        logging.getLogger("test.render-bound").info("row-%d", index)

    page.run_pending()

    assert len(refs["log_list"].controls) == MAX_RENDERED_RECORDS
    assert len(system._log_records) == MAX_RENDERED_RECORDS + 250


def test_two_pages_receive_logs_and_shutdown_is_session_scoped():
    page_a, page_b = ImmediatePage(), ImmediatePage()
    refs_a, refs_b = make_refs(), make_refs()
    system_a, system_b = LogSystem(page_a, refs_a), LogSystem(page_b, refs_b)
    system_a.start()
    system_b.start()

    logging.getLogger("test.sessions").info("for-both")
    system_a.shutdown()
    count_a = len(values(refs_a))
    logging.getLogger("test.sessions").info("only-second-page")

    assert any("for-both" in value for value in values(refs_a))
    assert len(values(refs_a)) == count_a
    assert any("only-second-page" in value for value in values(refs_b))


def test_gui_handler_installation_is_idempotent():
    root = logging.getLogger()
    handler_a = install_gui_log_handler()
    handler_b = install_gui_log_handler()
    assert handler_a is handler_b
    assert root.handlers.count(handler_a) == 1


def test_gui_handler_installation_removes_stale_reloaded_instance():
    root = logging.getLogger()
    stale = logging.NullHandler()
    stale._miningprocessor_gui_handler = True
    root.addHandler(stale)

    current = install_gui_log_handler()

    assert stale not in root.handlers
    assert root.handlers.count(current) == 1


def test_render_failure_does_not_reenter_logging_pipeline(monkeypatch):
    page = ImmediatePage()
    refs = make_refs()
    refs["log_list"].update = lambda: (_ for _ in ()).throw(RuntimeError("destroyed"))
    system = LogSystem(page, refs)
    system.start()
    broker = get_log_broker()
    before = broker.latest_sequence
    diagnostics = []
    monkeypatch.setattr("gui.log_system._diagnose", lambda message, ex=None: diagnostics.append((message, ex)))

    logging.getLogger("test.failure").info("one-entry")

    assert broker.latest_sequence == before + 1
    assert len(diagnostics) == 1


def test_shutdown_cancels_pending_delivery():
    page = DeferredPage()
    refs = make_refs()
    system = LogSystem(page, refs)
    system.start()
    logging.getLogger("test.shutdown").info("pending")

    future = page.pending[0][3]
    system.shutdown()

    assert future.cancelled()
    logging.getLogger("test.shutdown").info("after")
    assert len(page.pending) == 1
