"""logger 模块测试"""
import logging
import pathlib
import queue
import sys
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.logger import QueueHandler, setup_logging, get_logger, _next_seq


@pytest.fixture(autouse=True)
def _clean_root_logger():
    """每个测试前后清理 root logger 的非 QueueHandler handler"""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    yield
    # 恢复原始 handlers
    root.handlers = original_handlers


class TestNextSeq:
    def test_returns_positive_int(self):
        val = _next_seq()
        assert isinstance(val, int)
        assert val > 0

    def test_increments_monotonically(self):
        a = _next_seq()
        b = _next_seq()
        assert b > a

    def test_thread_safe(self):
        """多线程调用不会产生重复序号"""
        results = []
        barrier = threading.Barrier(10)

        def collect():
            barrier.wait()
            results.append(_next_seq())

        threads = [threading.Thread(target=collect) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert len(set(results)) == 10  # 全部唯一


class TestQueueHandler:
    def test_pushes_to_queue(self):
        q = queue.Queue()
        handler = QueueHandler(q)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_queue")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("hello")

        assert not q.empty()
        payload = q.get_nowait()
        assert payload["message"] == "hello"
        assert payload["levelno"] == logging.INFO
        assert payload["levelname"] == "INFO"
        assert "timestamp" in payload
        assert "seq" in payload
        assert "created" in payload

        logger.removeHandler(handler)

    def test_includes_timestamp_format(self):
        q = queue.Queue()
        handler = QueueHandler(q)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_ts")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("ts_test")
        payload = q.get_nowait()

        # 时间戳格式: YYYY-MM-DD HH:MM:SS
        assert len(payload["timestamp"]) == 19
        assert payload["timestamp"][4] == "-"
        assert payload["timestamp"][7] == "-"
        assert payload["timestamp"][13] == ":"

        logger.removeHandler(handler)

    def test_error_level(self):
        q = queue.Queue()
        handler = QueueHandler(q)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_err")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.error("oops")

        payload = q.get_nowait()
        assert payload["levelno"] == logging.ERROR
        assert payload["levelname"] == "ERROR"

        logger.removeHandler(handler)

    def test_graceful_on_queue_error(self):
        """队列满时不应崩溃"""
        q = queue.Queue(maxsize=0)  # 无法放入
        handler = QueueHandler(q)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_overflow")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # put_nowait on maxsize=0 queue 会抛 Full，但 handler 应静默处理
        # 实际上 Queue(maxsize=0) 的 put_nowait 不会抛异常，只是阻塞
        # 使用一个简单的 Full 模拟：
        class FullQueue:
            def put_nowait(self, item):
                raise queue.Full

        handler2 = QueueHandler(FullQueue())
        handler2.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler2)

        # 不应抛异常
        logger.info("should not crash")

        logger.removeHandler(handler)
        logger.removeHandler(handler2)


class TestSetupLogging:
    def test_adds_stream_handler(self):
        root = logging.getLogger()
        # 清空
        root.handlers.clear()

        setup_logging()

        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                           and not isinstance(h, QueueHandler)]
        assert len(stream_handlers) == 1

    def test_no_duplicate_handlers(self):
        """多次调用不产生重复 handler"""
        setup_logging()
        setup_logging()
        setup_logging()

        root = logging.getLogger()
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                           and not isinstance(h, QueueHandler)]
        assert len(stream_handlers) == 1

    def test_respects_level(self):
        root = logging.getLogger()
        root.handlers.clear()

        setup_logging(level=logging.WARNING)
        assert root.level == logging.WARNING


class TestGetLogger:
    def test_returns_logger_instance(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_returns_root_logger_when_no_name(self):
        logger = get_logger()
        assert logger is logging.getLogger()

    def test_returns_same_logger_for_same_name(self):
        a = get_logger("same_name")
        b = get_logger("same_name")
        assert a is b
