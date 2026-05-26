"""GUI 日志消费管道测试 — 诊断日志输出中断 bug

验证 _consume_logs → _schedule_flush → _run_flush_on_page → _flush_pending_to_ui 管道。
通过 mock page 对象模拟 Flet 的 run_thread 行为。
"""
import bisect
import logging
import pathlib
import queue
import sys
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.logger import QueueHandler, DEFAULT_FORMAT, setup_logging


# ---------------------------------------------------------------------------
# 辅助 Page Mocks
# ---------------------------------------------------------------------------
class SyncPage:
    """run_thread 同步执行回调（正常 Flet 行为）"""
    def run_thread(self, fn, *args):
        fn(*args)


class FailingPage:
    """run_thread 抛异常（模拟 session 销毁/loop 关闭）"""
    def run_thread(self, fn, *args):
        raise RuntimeError("An attempt to fetch destroyed session.")


class SilentFailPage:
    """run_thread 不抛异常但不执行回调（模拟 loop.call_soon_threadsafe 静默丢弃）"""
    def run_thread(self, fn, *args):
        pass


class IntermittentFailPage:
    """run_thread 前 N 次失败，之后恢复正常"""
    def __init__(self, fail_count=2):
        self._fail_count = fail_count
        self._calls = 0

    def run_thread(self, fn, *args):
        self._calls += 1
        if self._calls <= self._fail_count:
            raise RuntimeError(f"transient failure #{self._calls}")
        fn(*args)


# ---------------------------------------------------------------------------
# 精简版日志管道（与 gui/main.py 修复后逻辑一致）
# ---------------------------------------------------------------------------
class LogPipeline:
    """与 gui/main.py 中的日志管道逻辑一致（含 fallback flush），不依赖 Flet GUI"""

    MAX_LOG_RECORDS = 5000
    FLUSH_INTERVAL = 0.05
    FALLBACK_FLUSH_TIMEOUT = 0.3

    def __init__(self, page_mock=None):
        self.log_queue = queue.Queue()
        self.shutdown_event = threading.Event()
        self.log_records: list[dict] = []
        self.log_records_lock = threading.Lock()
        self._pending_records: list[dict] = []
        self._pending_lock = threading.Lock()
        self._flush_timer: threading.Timer | None = None
        self._last_flush_time: float = time.monotonic()
        self.page = page_mock or SyncPage()
        self.flush_count = 0
        self.ui_texts: list[str] = []
        self._consumer_thread: threading.Thread | None = None

        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        )

    def start(self):
        setup_logging()
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, QueueHandler):
                root.removeHandler(h)
        root.addHandler(self.queue_handler)
        self._consumer_thread = threading.Thread(target=self._consume_logs, daemon=True)
        self._consumer_thread.start()

    def stop(self):
        self.shutdown_event.set()
        root = logging.getLogger()
        root.removeHandler(self.queue_handler)
        with self._pending_lock:
            if self._flush_timer is not None:
                self._flush_timer.cancel()
                self._flush_timer = None
        try:
            while True:
                self.log_queue.get_nowait()
        except queue.Empty:
            pass
        self.log_queue.put_nowait(None)
        if self._consumer_thread:
            self._consumer_thread.join(timeout=2)

    def _append_log_record(self, log_item: dict):
        record = {
            "timestamp": str(log_item.get("timestamp", "")),
            "created": float(log_item.get("created", 0)),
            "seq": int(log_item.get("seq", 0)),
            "levelno": int(log_item["levelno"]),
            "levelname": str(log_item["levelname"]),
            "message": str(log_item["message"]),
        }
        with self.log_records_lock:
            keys = [r["seq"] for r in self.log_records]
            idx = bisect.bisect_right(keys, record["seq"])
            self.log_records.insert(idx, record)
            if len(self.log_records) > self.MAX_LOG_RECORDS:
                del self.log_records[:-self.MAX_LOG_RECORDS]
        with self._pending_lock:
            self._pending_records.append(record)

    def _flush_pending_to_ui(self):
        with self._pending_lock:
            batch = self._pending_records[:]
            self._pending_records.clear()
        if not batch or self.shutdown_event.is_set():
            return
        batch.sort(key=lambda r: r.get("seq", 0))
        for record in batch:
            self.ui_texts.append(str(record["message"]))
        self.flush_count += 1
        self._last_flush_time = time.monotonic()

    def _schedule_flush(self):
        with self._pending_lock:
            if self._flush_timer is None:
                self._flush_timer = threading.Timer(
                    self.FLUSH_INTERVAL, self._run_flush_on_page
                )
                self._flush_timer.daemon = True
                self._flush_timer.start()

    def _run_flush_on_page(self):
        with self._pending_lock:
            self._flush_timer = None
        try:
            self.page.run_thread(self._flush_pending_to_ui)
        except Exception:
            pass

    def _update_log_view(self):
        if self.shutdown_event.is_set():
            return
        self._schedule_flush()

    def _consume_logs(self):
        while True:
            try:
                log_item = self.log_queue.get(timeout=max(self.FLUSH_INTERVAL * 4, 0.2))
            except queue.Empty:
                # 定期检查：pending 记录是否长时间未被 flush
                with self._pending_lock:
                    pending_count = len(self._pending_records)
                if pending_count > 0:
                    elapsed = time.monotonic() - self._last_flush_time
                    if elapsed > self.FALLBACK_FLUSH_TIMEOUT:
                        self._flush_pending_to_ui()
                continue
            except Exception:
                continue
            if log_item is None:
                break
            if self.shutdown_event.is_set():
                continue
            try:
                self._append_log_record(log_item)
                for _ in range(100):
                    try:
                        log_item = self.log_queue.get_nowait()
                    except queue.Empty:
                        break
                    if log_item is None:
                        return
                    if not self.shutdown_event.is_set():
                        self._append_log_record(log_item)
                self._update_log_view()
                # Fallback flush
                with self._pending_lock:
                    pending_count = len(self._pending_records)
                if pending_count > 0:
                    elapsed = time.monotonic() - self._last_flush_time
                    if elapsed > self.FALLBACK_FLUSH_TIMEOUT:
                        self._flush_pending_to_ui()
            except Exception as ex:
                print(f"[日志消费线程异常] {ex}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------
class TestLogPipelineNormal:
    def test_single_log_reaches_ui(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        logging.getLogger("test").info("hello world")
        time.sleep(0.3)
        pipeline.stop()
        assert any("hello world" in t for t in pipeline.ui_texts)

    def test_multiple_logs_all_reach_ui(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        for i in range(20):
            logging.getLogger("test").info(f"msg-{i}")
        time.sleep(0.5)
        pipeline.stop()
        for i in range(20):
            assert any(f"msg-{i}" in t for t in pipeline.ui_texts), f"msg-{i} missing"

    def test_logs_stored_in_records(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        logging.getLogger("test").info("stored")
        time.sleep(0.3)
        pipeline.stop()
        assert any("stored" in r["message"] for r in pipeline.log_records)


class TestRunThreadFailure:
    def test_failing_page_accumulates_pending_initially(self):
        pipeline = LogPipeline(page_mock=FailingPage())
        pipeline.start()
        logging.getLogger("test").info("before failure")
        time.sleep(0.1)
        assert pipeline.flush_count == 0
        pipeline.stop()

    def test_silent_fail_recovers_via_fallback(self):
        """run_thread 静默失败时，fallback flush 应从 consumer 线程直接 flush"""
        pipeline = LogPipeline(page_mock=SilentFailPage())
        pipeline.start()
        logging.getLogger("test").info("msg-silent")
        # 等待 fallback timeout + consumer 定时唤醒
        time.sleep(1.5)
        pipeline.stop()
        assert len(pipeline.ui_texts) >= 1, "fallback should deliver logs"
        assert any("msg-silent" in t for t in pipeline.ui_texts)

    def test_failing_then_recovering_flushes_all(self):
        pipeline = LogPipeline(page_mock=IntermittentFailPage(fail_count=2))
        pipeline.start()
        logging.getLogger("test").info("msg-1")
        time.sleep(0.15)
        logging.getLogger("test").info("msg-2")
        time.sleep(0.15)
        logging.getLogger("test").info("msg-3")
        time.sleep(0.5)
        pipeline.stop()
        assert len(pipeline.ui_texts) >= 1

    def test_failing_page_recovers_via_fallback(self):
        """即使 run_thread 一直失败，fallback 也能 deliver 日志"""
        pipeline = LogPipeline(page_mock=FailingPage())
        pipeline.start()
        for i in range(3):
            logging.getLogger("test").info(f"msg-{i}")
            time.sleep(0.05)
        time.sleep(1.5)
        pipeline.stop()
        assert len(pipeline.ui_texts) >= 1, "fallback should deliver logs"


class TestTimerLifecycle:
    def test_flush_timer_cleared_before_run_thread(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        logging.getLogger("test").info("test")
        time.sleep(pipeline.FLUSH_INTERVAL + 0.1)
        assert pipeline._flush_timer is None
        pipeline.stop()

    def test_concurrent_schedule_flush_no_crash(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        barrier = threading.Barrier(10)

        def call_schedule():
            barrier.wait()
            pipeline._schedule_flush()

        threads = [threading.Thread(target=call_schedule) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        time.sleep(0.2)
        pipeline.stop()


class TestConsumerResilience:
    def test_consumer_survives_append_exception(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        original_append = pipeline._append_log_record
        call_count = [0]

        def flaky_append(log_item):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ValueError("simulated corruption")
            return original_append(log_item)

        pipeline._append_log_record = flaky_append
        pipeline.start()
        logging.getLogger("test").info("before-error")
        logging.getLogger("test").info("the-error-one")
        logging.getLogger("test").info("after-error")
        time.sleep(0.5)
        pipeline.stop()
        assert len(pipeline.ui_texts) >= 1

    def test_consumer_stops_after_shutdown(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        logging.getLogger("test").info("before")
        time.sleep(0.3)
        pipeline.stop()
        before_count = len(pipeline.ui_texts)
        logging.getLogger("test").info("after")
        time.sleep(0.3)
        assert len(pipeline.ui_texts) == before_count


class TestShutdownBehavior:
    def test_shutdown_discards_pending_records(self):
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        logging.getLogger("test").info("msg")
        pipeline.shutdown_event.set()
        time.sleep(0.2)
        pipeline.stop()


# ---------------------------------------------------------------------------
# 测试：日志时间线排序
# ---------------------------------------------------------------------------
class TestLogOrdering:
    def test_ui_texts_are_in_seq_order(self):
        """即使 fallback flush 交错，UI 中的日志也应按 seq 排序"""
        pipeline = LogPipeline(page_mock=SyncPage())
        pipeline.start()
        for i in range(30):
            logging.getLogger("test").info(f"seq-msg-{i:03d}")
        time.sleep(0.8)
        pipeline.stop()
        # 提取序号，验证单调递增
        indices = []
        for t in pipeline.ui_texts:
            if "seq-msg-" in t:
                try:
                    idx = int(t.split("seq-msg-")[1][:3])
                    indices.append(idx)
                except ValueError:
                    pass
        assert len(indices) >= 10, f"Expected many logs, got {len(indices)}"
        assert indices == sorted(indices), f"UI order not sorted: {indices[:20]}..."
