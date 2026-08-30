#!/usr/bin/env python3
"""
Tauri-Python 桥接层 — JSON-RPC over stdin/stdout

协议：
  请求：{"id": int, "method": str, "params": dict}
  响应：{"id": int, "result": any} 或 {"id": int, "error": str}
  事件：{"event": str, "data": dict}  (异步推送，无 id)

日志通过 stderr 流式推送，包含 seq、timestamp、logger、message，
异常时额外携带 detail（完整 traceback）。
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import logging
import os
import secrets
import socket
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from func.time_utils import local_datetime_from_timestamp

# ─── 强制 UTF-8 编码 ───
# PyInstaller 打包后 PYTHONUTF8 环境变量可能不生效，
# 需要在代码中显式设置，避免中文 Windows 使用 GBK 编码
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding='utf-8', errors='replace')

logger = logging.getLogger(__name__)

MAX_TEXT_FILE_BYTES = 10 * 1024 * 1024

# ─── 项目路径注册 ───
# PyInstaller 打包模式：从临时解压目录加载，但持久化数据写入 Application Support
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    PROJECT_ROOT = Path(sys._MEIPASS)
    # 切换工作目录到解压目录，让 config_loader 等模块能找到 config.json
    import os
    os.chdir(PROJECT_ROOT)

    # 持久化数据目录：写入 Application Support，不会在重启时丢失
    if sys.platform == "darwin":
        _persistent_dir = Path.home() / "Library" / "Application Support" / "com.kearney.mining-processor"
    elif sys.platform == "win32":
        _persistent_dir = Path(os.environ.get("APPDATA", Path.home())) / "com.kearney.mining-processor"
    else:
        _persistent_dir = Path.home() / ".local" / "share" / "com.kearney.mining-processor"

    _persistent_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MINING_PROCESSOR_DATA_DIR"] = str(_persistent_dir)
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_project_version() -> str:
    """Read the bridge version from package metadata, with source-tree fallback."""
    try:
        from importlib.metadata import version

        return version("MiningProcessor")
    except Exception:
        try:
            import tomllib

            with (PROJECT_ROOT / "pyproject.toml").open("rb") as file:
                return str(tomllib.load(file)["project"]["version"])
        except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError):
            return "dev"


_BRIDGE_VERSION = _get_project_version()


def _validate_url(url: str, *, allow_local: bool = False) -> str:
    """Validate a URL to prevent SSRF attacks.

    Only allows http/https schemes and blocks loopback, link-local,
    and cloud metadata addresses.  LLM endpoints may explicitly opt in to
    local addresses because local model servers commonly listen on loopback
    or a private network interface.

    Args:
        url: URL to validate.
        allow_local: Allow loopback, private, and link-local addresses. Cloud
            metadata, multicast, reserved, and unspecified addresses remain
            blocked.

    Raises:
        ValueError: If the URL is invalid or targets a blocked address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got: {parsed.scheme!r}")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL must include a hostname")

    cloud_metadata = ipaddress.ip_network("169.254.169.254/32")

    def _is_local_address(addr: ipaddress._BaseAddress) -> bool:
        return addr.is_loopback or addr.is_link_local or addr.is_private

    def _is_blocked_address(addr: ipaddress._BaseAddress) -> bool:
        return (
            _is_local_address(addr)
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
            or addr in cloud_metadata
        )

    def _is_allowed_local_address(addr: ipaddress._BaseAddress) -> bool:
        return allow_local and _is_local_address(addr) and addr not in cloud_metadata

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Local MineBase installations intentionally use localhost.
        if hostname.casefold() in {"localhost", "localhost.localdomain"}:
            return url
        # Resolve hostnames once and reject private/link-local answers.  A
        # DNS failure is left to the HTTP client so offline configuration can
        # still be saved; callers will receive the normal connection error.
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError):
            addresses = set()
        if any(_is_blocked_address(address) for address in addresses):
            if addresses and all(_is_allowed_local_address(address) for address in addresses):
                return url
            raise ValueError("URL resolves to a private or local address")
        return url

    if _is_blocked_address(addr):
        if _is_allowed_local_address(addr):
            return url
        raise ValueError("Private, loopback, or link-local addresses are not allowed")

    return url


def _sanitize_path(
    raw: str,
    must_exist: bool = False,
    allow_file: bool = True,
    allow_dir: bool = True,
) -> Path:
    """Validate and normalize a file path to prevent directory traversal.

    .. deprecated:: 使用 ``func.path_utils.sanitize_path`` 代替。
    """
    from func.path_utils import sanitize_path
    return sanitize_path(raw, must_exist=must_exist, allow_file=allow_file, allow_dir=allow_dir)


def _require_params(params: dict, *names: str) -> None:
    """Raise a clear validation error instead of leaking ``KeyError`` to RPC clients."""
    missing = [name for name in names if name not in params or params[name] is None]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required parameter(s): {joined}")


# ─── JSON 编码器（处理 pandas/numpy/datetime 等类型）───
class _BridgeEncoder(json.JSONEncoder):
    """处理 pandas Timestamp、numpy 类型、NaN 等不可直接 JSON 序列化的值。"""

    def default(self, o: Any) -> Any:
        try:
            import numpy as np

            if isinstance(o, (np.integer,)):
                return int(o)
            if isinstance(o, (np.floating,)):
                if np.isnan(o):
                    return None
                return float(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
        except ImportError:
            pass
        try:
            import pandas as pd

            if isinstance(o, pd.Timestamp):
                return o.isoformat()
            if isinstance(o, pd.Series):
                return o.tolist()
            if pd.isna(o):
                return None
        except ImportError:
            pass
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, set):
            return list(o)
        return super().default(o)


def _send(obj: dict) -> None:
    """向 stdout 写一行 JSON。"""
    line = json.dumps(obj, ensure_ascii=False, cls=_BridgeEncoder, default=str)
    with _stdout_lock:
        print(line, flush=True)


def _sanitize(val):
    """将 numpy/pandas 类型转为原生 Python 类型，确保 JSON 安全。"""
    try:
        import numpy as np
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            f = float(val)
            return None if (f != f) else f  # NaN → None
        if isinstance(val, np.bool_):
            return bool(val)
        if isinstance(val, np.ndarray):
            return val.tolist()
    except ImportError:
        pass
    try:
        import pandas as pd
        if isinstance(val, pd.Timestamp):
            return val.isoformat() if pd.notna(val) else None
        if isinstance(val, pd.Series):
            return [_sanitize(v) for v in val]
        if pd.isna(val):
            return None
    except ImportError:
        pass
    if isinstance(val, float) and (val != val):  # native NaN
        return None
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    return val


def _sanitize_rows(rows: list[dict]) -> list[dict]:
    """批量清理行数据中所有值的类型。"""
    return [{k: _sanitize(v) for k, v in row.items()} for row in rows]


def _emit(event: str, data: dict) -> None:
    """向 stdout 推送一个事件。"""
    _send({"event": event, "data": data})


# ─── 日志拦截 ───
_NOISY_LOGGERS = frozenset({
    "watchfiles", "uvicorn", "asyncio",
})


class _SuppressNoisyFilter(logging.Filter):
    """过滤第三方库的 DEBUG 日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.INFO:
            name = record.name or ""
            if name in _NOISY_LOGGERS or any(
                name.startswith(prefix + ".") for prefix in _NOISY_LOGGERS
            ):
                return False
        return True


class _StderrLogHandler(logging.Handler):
    """将 logging 记录序列化为 JSON 推送到 stderr。"""

    def __init__(self):
        super().__init__()
        self.addFilter(_SuppressNoisyFilter())
        self._sequence = 0
        self._sequence_lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            detail = self.format(record)
            message = detail.split("\n", 1)[0].rstrip()
            with self._sequence_lock:
                self._sequence += 1
                sequence = self._sequence
            data = {
                "seq": sequence,
                "timestamp": local_datetime_from_timestamp(record.created).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
            if detail != message:
                data["detail"] = detail
            obj = json.dumps(
                {"event": "log", "data": data},
                ensure_ascii=False,
                cls=_BridgeEncoder,
            )
            sys.stderr.write(obj + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def _setup_logging() -> None:
    """配置 logging：所有日志通过 stderr JSON 推送给 Tauri。"""
    handler = _StderrLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # 清除已有 handler，避免重复
    root.handlers.clear()
    root.addHandler(handler)


# ─── 取消令牌 ───
_cancel_event = threading.Event()
_llm_cancel_event = threading.Event()
_task_state_lock = threading.Lock()
_active_cancel_event: threading.Event | None = None
_active_cancel_request_id: int | None = None
_pending_cancel_requests: set[int] = set()


def _begin_cancellable_task(request_id: int | None = None) -> threading.Event:
    """注册当前长任务的取消令牌。

    长任务在独立的单线程执行器中运行，因此同一时刻只允许一个任务；
    快速 RPC（包括 cancel）由另一个执行器处理，不会被它阻塞。
    """
    global _active_cancel_event, _active_cancel_request_id
    event = threading.Event()
    with _task_state_lock:
        if _active_cancel_event is not None:
            raise RuntimeError("已有数据处理任务正在运行")
        if request_id is not None and request_id in _pending_cancel_requests:
            event.set()
            _pending_cancel_requests.discard(request_id)
        _active_cancel_event = event
        _active_cancel_request_id = request_id
    return event


def _end_cancellable_task(event: threading.Event) -> None:
    """清理当前长任务的取消令牌。"""
    global _active_cancel_event, _active_cancel_request_id
    with _task_state_lock:
        if _active_cancel_event is event:
            _active_cancel_event = None
            _active_cancel_request_id = None


def _discard_pending_cancel(request_id: int | None) -> None:
    """丢弃未能匹配到任务的取消请求，避免污染后续任务。"""
    if request_id is None:
        return
    with _task_state_lock:
        _pending_cancel_requests.discard(request_id)


def _cancel_active_task(params: dict | None = None) -> None:
    """按请求 ID 设置长任务取消令牌。"""
    global _cancel_event, _llm_cancel_event
    target_request_id = (params or {}).get("request_id")
    if target_request_id is not None:
        try:
            target_request_id = int(target_request_id)
        except (TypeError, ValueError):
            target_request_id = None

    event = None
    with _task_state_lock:
        if _active_cancel_event is not None and (
            target_request_id is None
            or target_request_id == _active_cancel_request_id
        ):
            event = _active_cancel_event
        elif target_request_id is not None:
            # The long-task executor may not have started the handler yet.
            # Keep the cancellation bound to this request ID only.
            _pending_cancel_requests.add(target_request_id)
    if event is not None:
        event.set()
        # 保留旧事件，兼容仍直接引用这些模块变量的处理器/第三方调用方。
        _cancel_event.set()
        _llm_cancel_event.set()


# stdout 可能由多个 RPC worker 同时写入，必须保证一条 JSON 完整输出。
_stdout_lock = threading.Lock()


# ─── RPC 方法注册表 ───
_METHODS: dict[str, callable] = {}


def _register(name: str):
    """装饰器：注册一个 RPC 方法。"""

    def decorator(fn):
        _METHODS[name] = fn
        return fn

    return decorator


# ═══════════════════════════════════════════════════════════
# 台账缓存加载 & 匹配后处理（委托 func/orchestration.py 共享模块）
# ═══════════════════════════════════════════════════════════


def _build_anomaly_config(params: dict):
    """从 RPC 参数构建 AnomalyConfig，未传入时返回 disabled 实例。

    逐列检测阈值从用户配置中读取（持久化设置），无需前端传入。
    """
    from func.anomaly.rules import AnomalyConfig
    if not params.get("anomaly_enabled"):
        return AnomalyConfig(enabled=False)
    return AnomalyConfig.build_from_ui(
        enabled=True,
        generate_report=params.get("anomaly_report", False),
        mode=params.get("anomaly_mode", "flag"),
    )


def _extract_common_params(params: dict) -> dict:
    """从 RPC 参数中提取所有模块共用的处理参数。

    消除 6 个 @_register 方法中重复的参数提取代码。
    """
    return {
        "skip_hidden": params.get("skip_hidden", False),
        "skip_hidden_rows": params.get("skip_hidden_rows", False),
        "skip_hidden_cols": params.get("skip_hidden_cols", False),
        "anomaly_config": _build_anomaly_config(params),
        "use_equipment_ledger": params.get("use_equipment_ledger", False),
        "use_oil_ledger": params.get("use_oil_ledger", False),
        "use_model_ledger": params.get("use_model_ledger", False),
    }


# ═══════════════════════════════════════════════════════════
# RPC 方法实现
# ═══════════════════════════════════════════════════════════


@_register("process_fuel")
def _process_fuel(params: dict) -> dict:
    from func.orchestration import process_single
    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    common = _extract_common_params(params)
    return process_single(
        "fuel", safe_path,
        year=params.get("year"),
        filter_zero_engine_hours=params.get("filter_zero_engine_hours", True),
        filter_zero_work_hours=params.get("filter_zero_work_hours", False),
        **common,
    )


@_register("process_tire")
def _process_tire(params: dict) -> dict:
    """处理轮胎寿命统计表。"""
    from func.orchestration import process_single

    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    common = _extract_common_params(params)
    return process_single("tire", safe_path, **common)


@_register("process_production")
def _process_production(params: dict) -> dict:
    from func.orchestration import process_single
    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    common = _extract_common_params(params)
    cancel_event = _begin_cancellable_task(params.get("_bridge_request_id"))
    try:
        return process_single(
            "production", safe_path,
            raw_start=params.get("raw_start", -1),
            cancel_event=cancel_event,
            filter_zero_hours_meter=params.get("filter_zero_hours_meter", True),
            filter_zero_km_meter=params.get("filter_zero_km_meter", True),
            filter_zero_run_hours=params.get("filter_zero_run_hours", False),
            filter_zero_run_km=params.get("filter_zero_run_km", False),
            **common,
        )
    finally:
        _end_cancellable_task(cancel_event)


@_register("process_electrical")
def _process_electrical(params: dict) -> dict:
    from func.orchestration import process_single
    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    common = _extract_common_params(params)
    return process_single(
        "electrical", safe_path,
        year=params.get("year"),
        add_shift_column=params.get("add_shift_column", False),
        default_shift=params.get("default_shift", "Day"),
        **common,
    )


@_register("process_worktime")
def _process_worktime(params: dict) -> dict:
    _require_params(params, "path", "year", "month")
    from func.orchestration import build_worktime_header_mapping, process_single
    common = _extract_common_params(params)
    header_mapping = None
    if params.get("use_header_mapping"):
        header_mapping = build_worktime_header_mapping(mode=params.get("header_mode"))
    return process_single(
        "worktime", str(_sanitize_path(params["path"], must_exist=True)),
        year=params["year"], month=params["month"],
        header_mapping=header_mapping,
        **common,
    )


@_register("process_merge")
def _process_merge(params: dict) -> dict:
    from func.orchestration import process_single
    safe_folder = str(_sanitize_path(params["folder_path"], must_exist=True, allow_file=False))
    common = _extract_common_params(params)
    return process_single(
        "merge", safe_folder,
        keyword=params["keyword"],
        strip_time=params.get("strip_time", False),
        sort_configs=params.get("sort_configs"),
        tolerant_header=params.get("tolerant_header", False),
        dedup=params.get("dedup", False),
        **common,
    )


@_register("process_maintenance")
def _process_maintenance(params: dict) -> dict:
    from func.orchestration import process_single
    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    common = _extract_common_params(params)
    return process_single(
        "maint", safe_path,
        split_by_year=params.get("split_by_year", False),
        details_only=params.get("details_only", False),
        use_ml_fallback=params.get("use_ml_fallback", True),
        **common,
    )


@_register("get_llm_config")
def _get_llm_config(params: dict) -> dict:
    from func.config_loader import get_llm_config
    from func.secret_store import LLM_KEY_MASK
    cfg = get_llm_config()
    cfg["api_key"] = LLM_KEY_MASK if cfg.get("api_key") else ""
    return cfg


@_register("get_system_resource_config")
def _get_system_resource_config(params: dict) -> dict:
    """返回系统资源设置及当前机器可用核心数。"""
    from func.config_loader import (
        get_available_cpu_cores,
        get_cpu_cores,
        get_default_cpu_cores,
    )

    return {
        "cpu_cores": get_cpu_cores(),
        "available_cpu_cores": get_available_cpu_cores(),
        "default_cpu_cores": get_default_cpu_cores(),
    }


@_register("save_system_resource_config")
def _save_system_resource_config(params: dict) -> dict:
    """校验并保存系统资源设置。"""
    _require_params(params, "cpu_cores")
    from func.config_loader import (
        get_available_cpu_cores,
        get_default_cpu_cores,
        set_cpu_cores,
    )

    cpu_cores = set_cpu_cores(params["cpu_cores"])
    return {
        "cpu_cores": cpu_cores,
        "available_cpu_cores": get_available_cpu_cores(),
        "default_cpu_cores": get_default_cpu_cores(),
    }


@_register("update_llm_config")
def _update_llm_config(params: dict) -> dict:
    from func.config_loader import update_llm_config
    from func.secret_store import LLM_KEY_MASK
    updates = {k: v for k, v in params.items() if k in ("url", "api_key", "model", "format", "concurrency", "batch_size", "timeout", "max_retries")}
    if "url" in updates:
        _validate_url(updates["url"], allow_local=True)
    cfg = update_llm_config(updates)
    cfg["api_key"] = LLM_KEY_MASK if cfg.get("api_key") else ""
    return cfg


@_register("test_llm_connection")
def _test_llm_connection(params: dict) -> dict:
    from func.config_loader import test_llm_connection
    cfg = {
        "url": _validate_url(params.get("url", ""), allow_local=True),
        "api_key": params.get("api_key", ""),
        "format": params.get("format", "openai"),
    }
    return test_llm_connection(cfg)


@_register("process_maintenance_llm")
def _process_maintenance_llm(params: dict) -> dict:
    from func.config_loader import get_llm_config
    from func.label_maintenance_with_llm import process_maintenance_llm

    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    llm_config = get_llm_config()
    if not llm_config.get("url") or not llm_config.get("api_key"):
        raise ValueError("请先在配置中填写 LLM 接口 URL 和 API Key")
    if not llm_config.get("model"):
        raise ValueError("请先在配置中选择 LLM 模型")
    cancel_event = _begin_cancellable_task(params.get("_bridge_request_id"))
    _llm_cancel_event.clear()
    _CANCEL_FILE.unlink(missing_ok=True)
    try:
        result = process_maintenance_llm(
            safe_path,
            llm_config=llm_config,
            sheet_name=params.get("sheet_name", "维修明细"),
            content_column=params.get("content_column", "维修内容"),
            category_column=params.get("category_column", "大类"),
            minor_column=params.get("minor_column", "小类"),
            status_column=params.get("status_column", "分类方式"),
            date_column=params.get("date_column"),
            device_column=params.get("device_column"),
            model_column=params.get("model_column"),
            hours_column=params.get("hours_column"),
            filter_values=params.get("filter_values"),
            export_mode=params.get("export_mode", "statistics"),
            concurrency=llm_config.get("concurrency", 10),
            batch_size=llm_config.get("batch_size", 50),
            cancel_event=cancel_event,
            cancel_file=_CANCEL_FILE,
            show_progress_bar=True,
        )
        result["cancelled"] = cancel_event.is_set()
        return result
    finally:
        _end_cancellable_task(cancel_event)


# LLM 标注取消文件（用于处理器在网络请求间隔中检测取消）。
# Include the process ID so multiple bridge instances cannot cancel each other.
_CANCEL_FILE = Path(tempfile.gettempdir()) / f"mining_processor_cancel_{os.getpid()}"


@_register("cancel_llm_labeling")
def _cancel_llm_labeling(params: dict) -> dict:
    _cancel_active_task(params)
    return {"ok": True}


@_register("preview_excel_sheets")
def _preview_excel_sheets(params: dict) -> dict:
    from func.excel_utils import load_workbook_safely
    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    wb = load_workbook_safely(safe_path, read_only=True, data_only=True)
    sheets = wb.sheetnames
    wb.close()
    return {"sheets": sheets}


@_register("preview_excel_columns")
def _preview_excel_columns(params: dict) -> dict:
    from func.label_maintenance_with_llm import preview_excel_columns

    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    sheet_name = params.get("sheet_name", "维修明细")
    return preview_excel_columns(safe_path, sheet_name=sheet_name)


@_register("export_maintenance_template")
def _export_maintenance_template(params: dict) -> dict:
    from func.config_loader import export_maintenance_classification_template

    path = params.get("path", "")
    if not path:
        from func.config_loader import _DATA_DIR
        path = str(_DATA_DIR / "维修分类配置模板.xlsx")
    with_defaults = params.get("with_defaults", False)
    output = export_maintenance_classification_template(path, with_defaults=with_defaults)
    return {"output_file": output}


@_register("batch_scan")
def _batch_scan(params: dict) -> dict:
    from func.file_scanner import scan_folder

    safe_folder = str(_sanitize_path(params["folder_path"], must_exist=True, allow_file=False))
    return scan_folder(safe_folder, scope="batch")


@_register("sync_scan")
def _sync_scan(params: dict) -> dict:
    """扫描同步目录，返回逐文件识别结果。"""
    from func.file_scanner import scan_folder

    safe_folder = str(_sanitize_path(params["input_dir"], must_exist=True, allow_file=False))
    return scan_folder(safe_folder, scope="sync")


@_register("daily_report_scan")
def _daily_report_scan(params: dict) -> dict:
    """扫描日报目录，返回逐文件识别结果。"""
    from func.file_scanner import scan_folder

    safe_folder = str(_sanitize_path(params["source_dir"], must_exist=True, allow_file=False))
    return scan_folder(safe_folder, scope="daily")


@_register("batch_process")
def _batch_process(params: dict) -> dict:
    cancel_event = _begin_cancellable_task(params.get("_bridge_request_id"))
    try:
        return _batch_process_impl(params, cancel_event)
    finally:
        _end_cancellable_task(cancel_event)


def _batch_process_impl(params: dict, cancel_event: threading.Event) -> dict:
    from func.excel_batch import process_files
    from func.orchestration import build_worktime_header_mapping, load_ledgers

    # 台账
    use_eq = params.get("use_equipment_ledger", False)
    use_oil = params.get("use_oil_ledger", False)
    equipment_ledger, oil_ledger = load_ledgers(use_equipment=use_eq, use_oil=use_oil)
    model_ledger = None
    if params.get("use_model_ledger", False):
        from func.orchestration import load_model_ledger_from_cache
        model_ledger = load_model_ledger_from_cache()

    # 进度回调 → 事件推送
    def progress_cb(payload):
        _emit("progress", payload)

    # 日期过滤
    filter_date = None
    if params.get("filter_date"):
        filter_date = date.fromisoformat(params["filter_date"])

    # 工时表头映射
    worktime_header_mapping = None
    if params.get("use_worktime_header_mapping"):
        worktime_header_mapping = build_worktime_header_mapping(
            mode=params.get("header_mode"),
        )

    safe_folder = str(_sanitize_path(params["folder_path"], allow_file=False))
    matched = params.get("matched")
    if matched is None:
        from func.excel_batch import scan_files

        matched, _ = scan_files(safe_folder)

    # 表合并基础表校验
    table_merge_config = params.get("table_merge_config")
    if table_merge_config:
        base_type = table_merge_config.get("base_type", "fuel")
        required = "fuel" if base_type == "fuel" else "worktime"
        if required not in (matched or {}):
            return {"error": f"表内合并需要 {required} 数据，但未在目录中找到"}

    _result, summary = process_files(
        folder_path=safe_folder,
        matched=matched,
        year=params.get("year"),
        month=params.get("month"),
        raw_start=params.get("raw_start", -1),
        merge_output=params.get("merge_output", True),
        equipment_ledger=equipment_ledger,
        oil_ledger=oil_ledger,
        model_ledger=model_ledger,
        filter_date=filter_date,
        worktime_header_mapping=worktime_header_mapping,
        table_merge_config=params.get("table_merge_config"),
        progress_cb=progress_cb,
        cancel_event=cancel_event,
        skip_hidden=params.get("skip_hidden", False),
        skip_hidden_rows=params.get("skip_hidden_rows", False),
        skip_hidden_cols=params.get("skip_hidden_cols", False),
        anomaly_config=_build_anomaly_config(params),
        filter_zero_engine_hours=params.get("filter_zero_engine_hours", True),
        filter_zero_work_hours=params.get("filter_zero_work_hours", False),
        filter_zero_hours_meter=params.get("filter_zero_hours_meter", True),
        filter_zero_km_meter=params.get("filter_zero_km_meter", True),
        filter_zero_run_hours=params.get("filter_zero_run_hours", False),
        filter_zero_run_km=params.get("filter_zero_run_km", False),
        selected_files=matched if params.get("matched") is not None else None,
    )
    return {"cancelled": cancel_event.is_set(), "summary": summary}


@_register("cancel")
def _cancel(params: dict) -> dict:
    _cancel_active_task(params)
    return {"ok": True}


@_register("sync_minebase")
def _sync_minebase(params: dict) -> dict:
    from func.sync_to_minebase import sync

    safe_input = str(_sanitize_path(params["input_dir"], must_exist=True, allow_file=False))
    results = sync(
        input_dir=safe_input,
        mode=params.get("mode"),
        data_types=params.get("data_types"),
        dry_run=params.get("dry_run", False),
        mapping_file=params.get("mapping_file"),
        year=params.get("year"),
        month=params.get("month"),
        date_start=params.get("date_start"),
        date_end=params.get("date_end"),
        apply_header_mapping=params.get("apply_header_mapping", True),
        header_mode=params.get("header_mode"),
        use_ledger=params.get("use_ledger", False),
        use_equipment_ledger=params.get("use_equipment_ledger", False),
        use_oil_ledger=params.get("use_oil_ledger", True),
        skip_hidden=params.get("skip_hidden", False),
        skip_hidden_rows=params.get("skip_hidden_rows", False),
        skip_hidden_cols=params.get("skip_hidden_cols", False),
        anomaly_config=_build_anomaly_config(params),
        filter_zero_engine_hours=params.get("filter_zero_engine_hours", True),
        filter_zero_work_hours=params.get("filter_zero_work_hours", False),
        filter_zero_hours_meter=params.get("filter_zero_hours_meter", True),
        filter_zero_km_meter=params.get("filter_zero_km_meter", True),
        filter_zero_run_hours=params.get("filter_zero_run_hours", False),
        filter_zero_run_km=params.get("filter_zero_run_km", False),
        conflict_policy=params.get("conflict_policy", "SKIP"),
        selected_files=params.get("selected_files"),
        profile_id=params.get("profile_id"),
    )
    dry_run_file = results.pop("_dry_run_file", None)
    resp: dict = {"results": results}
    if dry_run_file:
        resp["dry_run_file"] = dry_run_file
    return resp


@_register("daily_report_export")
def _daily_report_export(params: dict) -> dict:
    """按日期范围导出每日报表。"""
    from func.daily_report import export_daily_report
    from func.orchestration import (
        load_equipment_ledger_from_cache,
        load_model_ledger_from_cache,
    )

    source_dir = str(_sanitize_path(params["source_dir"], must_exist=True, allow_file=False))
    output_path = str(_sanitize_path(params["output_path"], allow_dir=False))
    use_equipment = bool(params.get("use_equipment_ledger", True))
    use_model = bool(params.get("use_model_ledger", False))
    if use_model and not use_equipment:
        raise ValueError("型号台账匹配需要同时启用设备台账匹配")
    equipment = load_equipment_ledger_from_cache() if use_equipment else None
    model = load_model_ledger_from_cache() if use_model else None
    result = export_daily_report(
        source_dir,
        output_path,
        params.get("date_start"),
        params.get("date_end"),
        equipment_ledger=equipment,
        model_ledger=model,
        config=params.get("config"),
        preprocess_options=params.get("preprocess_options"),
        include_detail_sheets=bool(params.get("include_detail_sheets", False)),
        selected_files=params.get("selected_files"),
    )
    return {
        "output_file": output_path,
        "rows": len(result.report),
        "warnings": result.warnings,
        "detail_sheets": list(result.detail_sheets),
    }


@_register("get_daily_report_config")
def _get_daily_report_config(params: dict) -> dict:
    from func.config_loader import get_daily_report_config
    return get_daily_report_config()


@_register("save_daily_report_config")
def _save_daily_report_config(params: dict) -> dict:
    from func.config_loader import save_daily_report_config
    return save_daily_report_config(params.get("config") or {})


@_register("validate_daily_report_config")
def _validate_daily_report_config(params: dict) -> dict:
    from func.daily_report import validate_daily_report_formulas

    errors = validate_daily_report_formulas(
        (params.get("config") or {}).get("formulas"),
        available_columns=params.get("available_columns"),
    )
    return {"valid": not errors, "errors": errors}


@_register("export_sync_warnings")
def _export_sync_warnings(params: dict) -> dict:
    from func.sync.export import export_warnings_to_excel

    warnings = params.get("warnings", [])
    output_path = params.get("output_path")
    input_dir = params.get("input_dir")

    out_file = export_warnings_to_excel(warnings, output_path=output_path, input_dir=input_dir)
    return {"output_file": out_file}


@_register("export_sync_anomalies")
def _export_sync_anomalies(params: dict) -> dict:
    """导出同步过程中检测到的异常值明细。"""
    from func.sync.export import export_anomaly_records_to_excel

    records = params.get("records", [])
    output_path = params.get("output_path")
    input_dir = params.get("input_dir")

    out_file = export_anomaly_records_to_excel(
        records,
        output_path=output_path,
        input_dir=input_dir,
    )
    return {"output_file": out_file}


@_register("get_config")
def _get_config(params: dict) -> dict:
    from func.config_loader import (
        get_file_keywords,
        get_minebase_config,
        get_worktime_header_mapping,
        load_config,
    )

    def _mask_minebase_passwords(config: dict) -> dict:
        from func.secret_store import KEYRING_SENTINEL

        minebase = config if isinstance(config.get("profiles"), list) else config.get("minebase")
        if not isinstance(minebase, dict):
            return config
        for profile in minebase.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            for section in ("api", "database"):
                connection = profile.get(section, {})
                if isinstance(connection, dict) and connection.get("password"):
                    connection["password"] = KEYRING_SENTINEL
        return config

    key = params.get("key")
    if key == "minebase":
        # The frontend only needs to know whether a password exists. Never
        # send the encrypted token over the JSON-RPC boundary.
        return _mask_minebase_passwords(get_minebase_config())
    if key == "file_keywords":
        return get_file_keywords()
    if key == "worktime_header_mapping":
        return get_worktime_header_mapping()
    config = load_config()
    if key:
        return config.get(key, {})
    return _mask_minebase_passwords(config)


@_register("save_config")
def _save_config(params: dict) -> dict:
    _require_params(params, "data")
    from func.config_loader import save_config, update_user_config

    target = params.get("target", "default")
    if target == "user":
        update_user_config(params["data"])
    else:
        save_config(params["data"])
    return {"ok": True}


@_register("save_minebase_config")
def _save_minebase_config(params: dict) -> dict:
    _require_params(params, "config")
    from func.config_loader import save_minebase_config

    save_minebase_config(params["config"])
    return {"ok": True}


@_register("get_anomaly_config")
def _get_anomaly_config(params: dict) -> dict:
    from func.config_loader import get_anomaly_detection_config

    return get_anomaly_detection_config()


@_register("save_anomaly_config")
def _save_anomaly_config(params: dict) -> dict:
    from func.config_loader import save_anomaly_detection_config, update_anomaly_detection_config

    updates = params.get("updates")
    if updates is not None:
        update_anomaly_detection_config(updates)
    else:
        full = params.get("config")
        if full is not None:
            save_anomaly_detection_config(full)
    return {"ok": True}


@_register("get_device_load_map")
def _get_device_load_map(params: dict) -> dict:
    from func.config_loader import get_device_load_map

    return get_device_load_map(params.get("version", "new"))


@_register("update_device_load_map")
def _update_device_load_map(params: dict) -> dict:
    _require_params(params, "map_data")
    from func.config_loader import update_device_load_map

    update_device_load_map(params["map_data"], params.get("version", "new"))
    return {"ok": True}


@_register("apply_device_load_map")
def _apply_device_load_map(params: dict) -> dict:
    _require_params(params, "map_data")
    from func.config_loader import apply_device_load_map

    apply_device_load_map(params["map_data"], params.get("version", "new"))
    return {"ok": True}


@_register("get_default_load_map")
def _get_default_load_map(params: dict) -> dict:
    from func.config_loader import get_default_load_map

    return get_default_load_map(params.get("version", "new"))


@_register("get_load_map_version")
def _get_load_map_version(params: dict) -> dict:
    from func.config_loader import get_load_map_version

    return {"version": get_load_map_version()}


@_register("set_load_map_version")
def _set_load_map_version(params: dict) -> dict:
    _require_params(params, "version")
    from func.config_loader import set_load_map_version

    set_load_map_version(params["version"])
    return {"ok": True}


# ─── 维修分类配置 ───

@_register("get_maintenance_classifications")
def _get_maintenance_classifications(params: dict) -> dict:
    from func.config_loader import get_maintenance_classifications

    rules = get_maintenance_classifications()
    # 序列化 set → list（JSON 不支持 set）
    rules["noise_exact"] = sorted(rules.get("noise_exact", set()))
    return rules


@_register("import_maintenance_classifications")
def _import_maintenance_classifications(params: dict) -> dict:
    from func.config_loader import import_maintenance_classifications

    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    rules = import_maintenance_classifications(safe_path)
    rules["noise_exact"] = sorted(rules.get("noise_exact", set()))
    return rules


@_register("update_maintenance_classifications")
def _update_maintenance_classifications(params: dict) -> dict:
    _require_params(params, "rules")
    from func.config_loader import update_maintenance_classifications

    rules = params["rules"]
    if "noise_exact" in rules and isinstance(rules["noise_exact"], list):
        rules["noise_exact"] = set(rules["noise_exact"])
    update_maintenance_classifications(rules)
    return {"ok": True}


# ─── 列映射配置方法 ───

@_register("get_minebase_column_mapping")
def _get_minebase_column_mapping(params: dict) -> dict:
    """获取 MineBase 列映射配置。"""
    from func.config_loader import get_minebase_column_mapping
    return get_minebase_column_mapping()


@_register("save_minebase_column_mapping")
def _save_minebase_column_mapping(params: dict) -> dict:
    """保存 MineBase 列映射配置。"""
    _require_params(params, "mapping")
    from func.config_loader import save_minebase_column_mapping
    save_minebase_column_mapping(params["mapping"])
    return {"ok": True}


@_register("reset_user_config")
def _reset_user_config(params: dict) -> dict:
    """重置所有用户覆盖配置（清空 config.user.json，恢复为系统默认值）。"""
    from func.config_loader import reset_all_user_overrides
    reset_all_user_overrides()
    return {"ok": True}


@_register("reset_minebase_column_mapping")
def _reset_minebase_column_mapping(params: dict) -> dict:
    """重置 MineBase 列映射为默认值。"""
    from func.config_loader import reset_minebase_column_mapping
    reset_minebase_column_mapping()
    return {"ok": True}


@_register("get_equipment_ledger_data")
def _get_equipment_ledger_data(params: dict) -> dict:
    from func.orchestration import load_equipment_ledger_from_cache
    ledger = load_equipment_ledger_from_cache()
    if not ledger:
        return {"rows": [], "columns": []}
    rows = _sanitize_rows(ledger.to_dict())
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@_register("get_oil_ledger_data")
def _get_oil_ledger_data(params: dict) -> dict:
    from func.orchestration import load_oil_ledger_from_cache
    ledger = load_oil_ledger_from_cache()
    if not ledger:
        return {"rows": [], "columns": []}
    rows = _sanitize_rows(ledger.to_dict())
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@_register("get_model_ledger_data")
def _get_model_ledger_data(params: dict) -> dict:
    from func.orchestration import load_model_ledger_from_cache
    ledger = load_model_ledger_from_cache()
    if not ledger:
        return {"rows": [], "columns": []}
    rows = _sanitize_rows(ledger.to_dict())
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


# ─── 台账文件操作方法 ───


def _load_excel_columns(params: dict) -> dict:
    """读取 Excel 文件的列名和 sheet 列表（用于列映射）。"""
    import pandas as pd
    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    xl = pd.ExcelFile(safe_path)
    sheet_names = xl.sheet_names
    target_sheet = params.get("sheet_name", sheet_names[0] if sheet_names else 0)
    df = pd.read_excel(safe_path, sheet_name=target_sheet, nrows=0)
    return {"columns": [str(c) for c in df.columns], "sheets": sheet_names}


@_register("load_ledger_file_columns")
def _load_ledger_file_columns(params: dict) -> dict:
    """读取 Excel 文件的列名和 sheet 列表（设备台账，用于列映射）。"""
    return _load_excel_columns(params)


@_register("load_oil_ledger_file_columns")
def _load_oil_ledger_file_columns(params: dict) -> dict:
    """读取 Excel 文件的列名和 sheet 列表（油品台账，用于列映射）。"""
    return _load_excel_columns(params)


@_register("load_model_ledger_file_columns")
def _load_model_ledger_file_columns(params: dict) -> dict:
    return _load_excel_columns(params)


@_register("import_equipment_ledger")
def _import_equipment_ledger(params: dict) -> dict:
    """导入设备台账 Excel，应用列映射后保存到缓存。"""
    from func.config_loader import save_equipment_ledger_cache
    from func.equipment_ledger import EquipmentLedger

    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    ledger = EquipmentLedger()
    ledger.load(
        safe_path,
        column_mapping=params.get("column_mapping"),
        sheet_name=params.get("sheet_name"),
    )
    records = ledger.to_dict()
    save_equipment_ledger_cache(records)
    return {"ok": True, "count": len(records)}


@_register("import_oil_ledger")
def _import_oil_ledger(params: dict) -> dict:
    """导入油品台账 Excel，应用列映射后保存到缓存。"""
    from func.config_loader import save_oil_ledger_cache
    from func.oil_ledger import OilLedger

    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    ledger = OilLedger()
    ledger.load(
        safe_path,
        column_mapping=params.get("column_mapping"),
        sheet_name=params.get("sheet_name"),
    )
    records = ledger.to_dict()
    save_oil_ledger_cache(records)
    return {"ok": True, "count": len(records)}


@_register("import_model_ledger")
def _import_model_ledger(params: dict) -> dict:
    from func.config_loader import save_model_ledger_cache
    from func.model_ledger import ModelLedger

    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    ledger = ModelLedger()
    ledger.load(
        safe_path,
        column_mapping=params.get("column_mapping"),
        sheet_name=params.get("sheet_name"),
    )
    records = ledger.to_dict()
    save_model_ledger_cache(records)
    return {"ok": True, "count": len(records)}


@_register("export_equipment_ledger_template")
def _export_equipment_ledger_template(params: dict) -> dict:
    """导出设备台账模板 Excel。"""
    from func.equipment_ledger import EquipmentLedger
    safe_path = str(_sanitize_path(params["output_path"], allow_dir=False))
    ledger = EquipmentLedger()
    ledger.export_template(safe_path)
    return {"ok": True, "output_file": safe_path}


@_register("export_oil_ledger_template")
def _export_oil_ledger_template(params: dict) -> dict:
    """导出油品台账模板 Excel。"""
    from func.oil_ledger import OilLedger
    safe_path = str(_sanitize_path(params["output_path"], allow_dir=False))
    ledger = OilLedger()
    ledger.export_template(safe_path)
    return {"ok": True, "output_file": safe_path}


@_register("export_model_ledger_template")
def _export_model_ledger_template(params: dict) -> dict:
    from func.model_ledger import ModelLedger
    safe_path = str(_sanitize_path(params["output_path"], allow_dir=False))
    ModelLedger().export_template(safe_path)
    return {"ok": True, "output_file": safe_path}


@_register("set_default_equipment_ledger")
def _set_default_equipment_ledger(params: dict) -> dict:
    """将当前设备台账数据保存为默认（写入缓存）。"""
    from func.config_loader import has_equipment_ledger_cache
    if has_equipment_ledger_cache():
        return {"ok": True, "message": "已是默认台账"}
    return {"ok": False, "message": "无台账数据可保存"}


@_register("set_default_oil_ledger")
def _set_default_oil_ledger(params: dict) -> dict:
    """将当前油品台账数据保存为默认（写入缓存）。"""
    from func.config_loader import has_oil_ledger_cache
    if has_oil_ledger_cache():
        return {"ok": True, "message": "已是默认台账"}
    return {"ok": False, "message": "无台账数据可保存"}


@_register("set_default_model_ledger")
def _set_default_model_ledger(params: dict) -> dict:
    from func.config_loader import has_model_ledger_cache
    if has_model_ledger_cache():
        return {"ok": True, "message": "已是默认台账"}
    return {"ok": False, "message": "无台账数据可保存"}


@_register("cancel_default_equipment_ledger")
def _cancel_default_equipment_ledger(params: dict) -> dict:
    """清除设备台账默认缓存。"""
    from func.config_loader import clear_equipment_ledger_cache
    clear_equipment_ledger_cache()
    return {"ok": True}


@_register("cancel_default_oil_ledger")
def _cancel_default_oil_ledger(params: dict) -> dict:
    """清除油品台账默认缓存。"""
    from func.config_loader import clear_oil_ledger_cache
    clear_oil_ledger_cache()
    return {"ok": True}


@_register("cancel_default_model_ledger")
def _cancel_default_model_ledger(params: dict) -> dict:
    from func.config_loader import clear_model_ledger_cache
    clear_model_ledger_cache()
    return {"ok": True}


@_register("clear_equipment_ledger")
def _clear_equipment_ledger(params: dict) -> dict:
    """清空设备台账数据和缓存。"""
    from func.config_loader import clear_equipment_ledger_cache
    clear_equipment_ledger_cache()
    return {"ok": True}


@_register("clear_oil_ledger")
def _clear_oil_ledger(params: dict) -> dict:
    """清空油品台账数据和缓存。"""
    from func.config_loader import clear_oil_ledger_cache
    clear_oil_ledger_cache()
    return {"ok": True}


@_register("clear_model_ledger")
def _clear_model_ledger(params: dict) -> dict:
    from func.config_loader import clear_model_ledger_cache
    clear_model_ledger_cache()
    return {"ok": True}


@_register("export_ledger_data")
def _export_ledger_data(params: dict) -> dict:
    """将当前台账数据导出为 Excel。

    params:
        data_type: "oil" 或 "equipment"
        output_path: 输出文件路径
    """
    from func.config_loader import load_equipment_ledger_cache, load_oil_ledger_cache

    data_type = params.get("data_type", "oil")
    safe_path = str(_sanitize_path(params["output_path"], allow_dir=False))

    if data_type == "oil":
        records = load_oil_ledger_cache()
        sheet_name = "油品台账"
    elif data_type == "model":
        from func.config_loader import load_model_ledger_cache
        records = load_model_ledger_cache()
        sheet_name = "型号台账"
    else:
        records = load_equipment_ledger_cache()
        sheet_name = "设备台账"

    if not records:
        return {"error": f"无{sheet_name}数据可导出"}

    import pandas as pd

    from func.excel_formatter import write_formatted_excel

    df = pd.DataFrame(records)
    write_formatted_excel(safe_path, {sheet_name: df})
    return {"output_file": safe_path}


@_register("list_directory")
def _list_directory(params: dict) -> dict:
    """列出目录内容，返回文件和子目录。"""
    p = _sanitize_path(params["path"], must_exist=True, allow_file=False)
    if not p.is_dir():
        return {"error": "Not a directory", "files": [], "dirs": []}
    files = []
    dirs = []
    for item in sorted(p.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            dirs.append(item.name)
        else:
            files.append(item.name)
    return {"files": files, "dirs": dirs}


@_register("list_excel_sheets")
def _list_excel_sheets(params: dict) -> dict:
    """列出 Excel 文件中的所有 Sheet 名。"""
    import pandas as pd
    safe_path = str(_sanitize_path(params["path"], must_exist=True, allow_dir=False))
    xl = pd.ExcelFile(safe_path)
    return {"sheets": xl.sheet_names}


@_register("read_excel_sheet")
def _read_excel_sheet(params: dict) -> dict:
    """读取指定 Sheet 的数据。

    max_rows=0 或不传表示不限制行数。
    """
    _require_params(params, "path", "sheet")
    import pandas as pd
    safe_path = str(_sanitize_path(params["path"], must_exist=True, allow_dir=False))
    max_rows = params.get("max_rows", 0)
    df = pd.read_excel(safe_path, sheet_name=params["sheet"])
    columns = [str(c) for c in df.columns]
    total = len(df)
    if max_rows > 0 and len(df) > max_rows:
        df = df.head(max_rows)
    rows = _sanitize_rows(df.to_dict("records"))
    return {"columns": columns, "rows": rows, "total": total, "truncated": max_rows > 0 and total > max_rows}


@_register("ledger_match_preview")
def _ledger_match_preview(params: dict) -> dict:
    """对数据行进行台账匹配预览。

    Returns:
        matched, unmatched, rows, columns — columns 保持原始列在前、结果列在后。
    """
    rows = params["rows"]
    name_col = params.get("name_column")
    id_col = params.get("id_column")
    oil_col = params.get("oil_column")
    mode = params.get("mode", "name")
    suffix = params.get("result_suffix", "")

    # 根据 suffix 生成带后缀的字段名
    def _key(base: str) -> str:
        return f"{base}_{suffix}" if suffix else base

    # 记录原始列顺序（从第一行 key 推断）
    original_columns = list(rows[0].keys()) if rows else []

    # 结果列名（按添加顺序）
    result_columns: list[str] = []

    def _track(key: str) -> str:
        if key not in result_columns:
            result_columns.append(key)
        return key

    # 加载台账
    from func.orchestration import load_equipment_ledger_from_cache, load_oil_ledger_from_cache
    equipment_ledger = load_equipment_ledger_from_cache()
    oil_ledger = load_oil_ledger_from_cache()

    matched_count = 0
    for row in rows:
        matched = False

        # 设备匹配：优先 ID，其次名称
        if id_col and equipment_ledger:
            device_id = str(row.get(id_col, "")).strip()
            if device_id:
                result = equipment_ledger.match_by_id(device_id)
                if result:
                    row[_track(_key("标准设备名称"))] = result.get("标准设备名称", result.get("标准名称", ""))
                    row[_track(_key("标准设备编号"))] = result.get("标准设备编号", "")
                    row[_track(_key("标准公司名称"))] = result.get("标准公司名称", "")
                    matched = True

        if not matched and name_col and equipment_ledger:
            device_name = str(row.get(name_col, "")).strip()
            if device_name:
                if mode == "id":
                    result = equipment_ledger.match_by_id(device_name)
                else:
                    result = equipment_ledger.match_device(device_name)
                if result:
                    row[_track(_key("标准设备名称"))] = result.get("标准设备名称", result.get("标准名称", ""))
                    row[_track(_key("标准设备编号"))] = result.get("标准设备编号", "")
                    row[_track(_key("标准公司名称"))] = result.get("标准公司名称", "")
                    matched = True

        if oil_col:
            oil_name = str(row.get(oil_col, "")).strip()
            if oil_name and oil_ledger:
                oil_result = oil_ledger.match(oil_name)
                if oil_result:
                    row[_track("标准油品名称")] = oil_result.get("标准名称", "")
                    row[_track("匹配方式")] = oil_result.get("匹配方式", "")
                    row[_track("相似度")] = oil_result.get("相似度", "")
                    matched = True

        row[_key("__matched")] = matched
        if matched:
            matched_count += 1

    # 最终列顺序 = 原始列 + 结果列 + __matched 标记列
    matched_key = _key("__matched")
    final_columns = original_columns + result_columns + [matched_key]

    return {
        "matched": matched_count,
        "unmatched": len(rows) - matched_count,
        "rows": _sanitize_rows(rows),
        "columns": final_columns,
    }


@_register("export_matched_data")
def _export_matched_data(params: dict) -> dict:
    """将匹配后的数据导出为 Excel。

    Params:
        rows: 当前 sheet 的数据行（单 sheet 模式）
        columns: 列名列表
        output_path: 输出文件路径
        date_only: bool, 是否使用 YYYY-MM-DD 格式（去除时间）
        sheets: dict[sheet_name, {columns, rows}] — 多 sheet 模式（优先于 rows/columns）
    """
    import pandas as pd

    from func.excel_formatter import write_formatted_excel

    safe_output = str(_sanitize_path(params["output_path"], allow_dir=False))
    date_only = params.get("date_only", False)

    sheets_param = params.get("sheets")
    if sheets_param:
        # Multi-sheet mode: each key → separate worksheet tab
        dfs: dict[str, pd.DataFrame] = {}
        for tab_name, sheet_data in sheets_param.items():
            cols = [c for c in sheet_data["columns"] if not c.startswith("__matched")]
            df = pd.DataFrame(sheet_data["rows"])
            for col in cols:
                if col not in df.columns:
                    df[col] = ""
            dfs[tab_name] = df[cols]
        write_formatted_excel(safe_output, dfs, date_only=date_only)
    else:
        # Single-sheet mode (legacy)
        rows = params["rows"]
        columns = params["columns"]
        export_cols = [c for c in columns if c != "__matched"]
        df = pd.DataFrame(rows)
        for col in export_cols:
            if col not in df.columns:
                df[col] = ""
        df = df[export_cols]
        write_formatted_excel(safe_output, {"导出数据": df}, date_only=date_only)

    return {"output_file": safe_output}


@_register("check_directory_exists")
def _check_directory_exists(params: dict) -> dict:
    """检查目录是否存在。"""
    try:
        p = _sanitize_path(params.get("path", ""), allow_file=False)
        return {"exists": p.is_dir()}
    except (ValueError, FileNotFoundError):
        return {"exists": False}


@_register("ping")
def _ping(params: dict) -> dict:
    return {"pong": True, "pid": os.getpid(), "version": _BRIDGE_VERSION}


@_register("get_sync_data_types")
def _get_sync_data_types(params: dict) -> dict:
    """返回 MineBase 同步支持的数据类型列表。"""
    from func.data_types import SYNC_DATA_TYPES
    return {"types": [{"id": t[0], "label": t[1]} for t in SYNC_DATA_TYPES]}


@_register("write_text_file")
def _write_text_file(params: dict) -> dict:
    """将文本内容写入指定路径（用于日志导出等）。"""
    from func.path_utils import sanitize_path
    _require_params(params, "path")
    safe_path = str(sanitize_path(params["path"], allow_dir=False))
    content = params.get("content", "")
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    content_size = len(content.encode("utf-8"))
    if content_size > MAX_TEXT_FILE_BYTES:
        raise ValueError(f"content exceeds the {MAX_TEXT_FILE_BYTES} byte limit")
    Path(safe_path).write_text(content, encoding="utf-8")
    return {"ok": True}


@_register("test_minebase_connection")
def _test_minebase_connection(params: dict) -> dict:
    """测试 MineBase 连接（API 或数据库模式）。

    如果前端传入 __keyring__ 哨兵值，按 profile_id 从已保存的配置中加载
    真实密码，方便用户无需重新输入密码即可测试连接。
    """
    from func.config_loader import get_minebase_api_config, get_minebase_db_config
    from func.secret_store import KEYRING_SENTINEL
    from func.sync_to_minebase import test_api_connection, test_db_connection

    mode = params.get("mode", "api")
    profile_id = params.get("profile_id")
    password = params.get("password", "")

    if password == KEYRING_SENTINEL:
        if mode == "api":
            password = get_minebase_api_config(profile_id).get("password", "")
        else:
            password = get_minebase_db_config(profile_id).get("password", "")

    if mode == "api":
        ok, msg = test_api_connection(
            url=_validate_url(params.get("url", "http://localhost:3000")),
            username=params.get("username", ""),
            password=password,
        )
    else:
        ok, msg = test_db_connection(
            host=params.get("host", "localhost"),
            port=int(params.get("port", 5432)),
            database=params.get("database", "minebase"),
            user=params.get("user", "postgres"),
            password=password,
        )
    return {"success": ok, "message": msg}


# ─── last_directory 持久化（统一走 config.user.json）───


@_register("get_last_directory")
def _get_last_directory(params: dict) -> dict:
    """获取指定 key 的上次使用目录。"""
    from func.config_loader import get_user_config
    key = params.get("key", "last_directory")
    return {"path": get_user_config(key, "")}


@_register("save_last_directory")
def _save_last_directory(params: dict) -> dict:
    """保存指定 key 的上次使用目录。"""
    from func.config_loader import update_user_config
    key = params.get("key", "last_directory")
    path = params.get("path", "")
    update_user_config({key: path})
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════


# 长任务单独串行，避免两个处理任务同时写同一批输出文件；
# 快速 RPC 使用独立线程池，因此长任务不会阻塞台账、配置和取消请求。
_LONG_RUNNING_METHODS = frozenset({
    "process_fuel",
    "process_production",
    "process_electrical",
    "process_worktime",
    "process_merge",
    "process_maintenance",
    "process_maintenance_llm",
    "batch_process",
    "sync_minebase",
})


def _handle_request(req: dict) -> None:
    """处理单个 RPC 请求。"""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method not in _METHODS:
        _send({"id": req_id, "error": f"Unknown method: {method}"})
        return

    call_params = dict(params) if isinstance(params, dict) else {}
    if method in _LONG_RUNNING_METHODS and req_id is not None:
        # 让处理器把取消令牌绑定到具体 RPC 请求，覆盖任务尚未开始执行的窗口。
        call_params["_bridge_request_id"] = req_id

    try:
        result = _METHODS[method](call_params)
        _send({"id": req_id, "result": result})
    except Exception:
        ref_id = secrets.token_hex(4)
        logger.error("RPC error ref=%s method=%s", ref_id, method, exc_info=True)
        # 提取根因，构造用户友好的错误消息
        root_msg = str(sys.exc_info()[1]).strip()
        if not root_msg:
            root_msg = sys.exc_info()[0].__name__
        _send({"id": req_id, "error": root_msg})
    finally:
        if method in _LONG_RUNNING_METHODS and req_id is not None:
            _discard_pending_cancel(req_id)


def main() -> None:
    """入口：从 stdin 读取请求，并异步分发后写回 stdout。

    stdin 主线程只负责收包；长任务和快速 RPC 使用不同执行器。
    因此台账/配置请求可以在数据处理期间继续执行。
    """
    _setup_logging()
    logger.info("Python bridge started")

    with (
        ThreadPoolExecutor(max_workers=4, thread_name_prefix="bridge-rpc") as rpc_executor,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-task") as task_executor,
    ):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                _send({"error": f"Invalid JSON: {e}"})
                continue

            executor = task_executor if req.get("method") in _LONG_RUNNING_METHODS else rpc_executor
            executor.submit(_handle_request, req)


if __name__ == "__main__":
    main()
