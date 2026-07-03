#!/usr/bin/env python3
"""
Tauri-Python 桥接层 — JSON-RPC over stdin/stdout

协议：
  请求：{"id": int, "method": str, "params": dict}
  响应：{"id": int, "result": any} 或 {"id": int, "error": str}
  事件：{"event": str, "data": dict}  (异步推送，无 id)

日志通过 stderr 流式推送：{"event": "log", "data": {"level": str, "message": str}}
"""

from __future__ import annotations

import json
import logging
import secrets
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── 项目路径注册 ───
# PyInstaller 打包模式：从临时解压目录加载
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    PROJECT_ROOT = Path(sys._MEIPASS)
    # 切换工作目录到解压目录，让 config_loader 等模块能找到 config.json
    import os
    os.chdir(PROJECT_ROOT)
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _sanitize_path(
    raw: str,
    must_exist: bool = False,
    allow_file: bool = True,
    allow_dir: bool = True,
) -> Path:
    """Validate and normalize a file path to prevent directory traversal."""
    p = Path(raw).resolve()
    if ".." in Path(raw).parts:
        raise ValueError("Path must not contain ..")
    if must_exist and not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p.name}")
    if p.is_file() and not allow_file:
        raise ValueError("Expected directory, got file")
    if p.is_dir() and not allow_dir:
        raise ValueError("Expected file, got directory")
    return p


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
class _StderrLogHandler(logging.Handler):
    """将 logging 记录序列化为 JSON 推送到 stderr。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            obj = json.dumps(
                {"event": "log", "data": {"level": record.levelname, "message": msg}},
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
    root.setLevel(logging.INFO)
    # 清除已有 handler，避免重复
    root.handlers.clear()
    root.addHandler(handler)


# ─── 取消令牌 ───
_cancel_event = threading.Event()


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


def _load_equipment_ledger_from_cache():
    """从缓存加载设备台账实例，失败返回 None。"""
    from func.orchestration import load_equipment_ledger_from_cache
    return load_equipment_ledger_from_cache()


def _load_oil_ledger_from_cache():
    """从缓存加载油品台账实例，失败返回 None。"""
    from func.orchestration import load_oil_ledger_from_cache
    return load_oil_ledger_from_cache()


def _post_process_ledger(
    output_file: str,
    use_equipment_ledger: bool = False,
    use_oil_ledger: bool = True,
) -> None:
    """对输出 Excel 文件进行台账匹配后处理。"""
    from func.orchestration import postprocess_from_cache
    postprocess_from_cache(
        output_file,
        use_equipment_ledger=use_equipment_ledger,
        use_oil_ledger=use_oil_ledger,
    )


# ═══════════════════════════════════════════════════════════
# RPC 方法实现
# ═══════════════════════════════════════════════════════════


@_register("process_fuel")
def _process_fuel(params: dict) -> dict:
    from func.excel_fuel import process_diesel_data

    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    result = process_diesel_data(safe_path, target_year=params.get("year"),
                                 skip_hidden=params.get("skip_hidden", False))
    output_file = str(result) if result else None
    if output_file:
        _post_process_ledger(
            output_file,
            use_equipment_ledger=params.get("use_equipment_ledger", False),
            use_oil_ledger=params.get("use_oil_ledger", False),
        )
    return {"output_file": output_file}


@_register("process_production")
def _process_production(params: dict) -> dict:
    from func.excel_production_enhanced import MiningDataProcessor
    from func.config_loader import get_device_load_map

    load_map = get_device_load_map()
    processor = MiningDataProcessor(
        raw_start=params.get("raw_start", -1), device_load_map=load_map,
        skip_hidden=params.get("skip_hidden", False),
    )
    path = str(_sanitize_path(params["path"], must_exist=True))
    p = Path(path)
    if p.is_dir():
        processor.process_folder(path)
        output_file = str(p / "合并产量.xlsx")
    else:
        output_file = str(p.parent / "合并产量.xlsx")
        processor.process_single_file(path, output_file)
    if output_file:
        _post_process_ledger(
            output_file,
            use_equipment_ledger=params.get("use_equipment_ledger", False),
            use_oil_ledger=params.get("use_oil_ledger", False),
        )
    return {"output_file": output_file}


@_register("process_electrical")
def _process_electrical(params: dict) -> dict:
    from func.excel_electrical import parse_excel_data

    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    parse_excel_data(
        safe_path,
        target_year=params.get("year"),
        add_shift_column=params.get("add_shift_column", False),
        default_shift=params.get("default_shift", "Day"),
        skip_hidden=params.get("skip_hidden", False),
    )
    output_file = str(Path(safe_path).parent / "电力消耗统计.xlsx")
    _post_process_ledger(
        output_file,
        use_equipment_ledger=params.get("use_equipment_ledger", False),
        use_oil_ledger=params.get("use_oil_ledger", False),
    )
    return {"output_file": output_file}


@_register("process_worktime")
def _process_worktime(params: dict) -> dict:
    from func.excel_worktime import process_excel_data
    from func.orchestration import build_worktime_header_mapping

    header_mapping = None
    if params.get("use_header_mapping"):
        header_mapping = build_worktime_header_mapping(
            mode=params.get("header_mode"),
            fuzzy=params.get("header_fuzzy"),
            fuzzy_match=params.get("fuzzy_match"),
        )

    year, month = params["year"], params["month"]
    safe_path = str(_sanitize_path(params["path"], must_exist=True))
    output_file = str(Path(safe_path).parent / f"{year}{month:02d}_工作效率表.xlsx")
    process_excel_data(
        safe_path,
        year=year,
        month=month,
        output_file=output_file,
        return_sheets=False,
        header_mapping=header_mapping,
        skip_hidden=params.get("skip_hidden", False),
    )
    _post_process_ledger(
        output_file,
        use_equipment_ledger=params.get("use_equipment_ledger", False),
        use_oil_ledger=params.get("use_oil_ledger", False),
    )
    return {"output_file": output_file}


@_register("process_merge")
def _process_merge(params: dict) -> dict:
    from func.excel_merger import merge_excel_files

    safe_folder = str(_sanitize_path(params["folder_path"], must_exist=True, allow_file=False))
    output = merge_excel_files(
        safe_folder,
        params["keyword"],
        strip_time=params.get("strip_time", False),
        sort_configs=params.get("sort_configs"),
        skip_hidden=params.get("skip_hidden", False),
    )
    if output:
        _post_process_ledger(
            output,
            use_equipment_ledger=params.get("use_equipment_ledger", False),
            use_oil_ledger=params.get("use_oil_ledger", False),
        )
    return {"output_file": output}


@_register("batch_scan")
def _batch_scan(params: dict) -> dict:
    from func.excel_batch import scan_files

    safe_folder = str(_sanitize_path(params["folder_path"], must_exist=True, allow_file=False))
    matched, missing = scan_files(safe_folder)
    return {"matched": matched, "missing": missing}


@_register("batch_process")
def _batch_process(params: dict) -> dict:
    from func.excel_batch import process_files
    from func.orchestration import load_ledgers, build_worktime_header_mapping

    # 台账
    use_eq = params.get("use_equipment_ledger", False)
    use_oil = params.get("use_oil_ledger", False)
    equipment_ledger, oil_ledger = load_ledgers(use_equipment=use_eq, use_oil=use_oil)

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
            fuzzy=params.get("header_fuzzy"),
            fuzzy_match=params.get("fuzzy_match"),
        )

    # 重置取消标记
    _cancel_event.clear()

    safe_folder = str(_sanitize_path(params["folder_path"], allow_file=False))
    matched = params.get("matched")
    if not matched:
        from func.excel_batch import scan_files

        matched, _ = scan_files(safe_folder)

    # 表合并基础表校验
    table_merge_config = params.get("table_merge_config")
    if table_merge_config:
        base_type = table_merge_config.get("base_type", "fuel")
        required = "fuel" if base_type == "fuel" else "worktime"
        if required not in (matched or {}):
            return {"error": f"表内合并需要 {required} 数据，但未在目录中找到"}

    result = process_files(
        folder_path=safe_folder,
        matched=matched,
        year=params.get("year"),
        month=params.get("month"),
        raw_start=params.get("raw_start", -1),
        merge_output=params.get("merge_output", True),
        equipment_ledger=equipment_ledger,
        oil_ledger=oil_ledger,
        filter_date=filter_date,
        worktime_header_mapping=worktime_header_mapping,
        table_merge_config=params.get("table_merge_config"),
        progress_cb=progress_cb,
        cancel_event=_cancel_event,
        skip_hidden=params.get("skip_hidden", False),
    )
    return {"cancelled": _cancel_event.is_set()}


@_register("cancel")
def _cancel(params: dict) -> dict:
    _cancel_event.set()
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
        use_ledger=params.get("use_ledger", False),
        use_equipment_ledger=params.get("use_equipment_ledger", False),
        use_oil_ledger=params.get("use_oil_ledger", True),
        skip_hidden=params.get("skip_hidden", False),
    )
    return {"results": results}


@_register("get_config")
def _get_config(params: dict) -> dict:
    from func.config_loader import (
        load_config, get_minebase_config,
        get_file_keywords, get_worktime_header_mapping,
    )

    key = params.get("key")
    if key == "minebase":
        return get_minebase_config()
    if key == "file_keywords":
        return get_file_keywords()
    if key == "worktime_header_mapping":
        return get_worktime_header_mapping()
    config = load_config()
    if key:
        return config.get(key, {})
    return config


@_register("save_config")
def _save_config(params: dict) -> dict:
    from func.config_loader import save_config, update_user_config

    target = params.get("target", "default")
    if target == "user":
        update_user_config(params["data"])
    else:
        save_config(params["data"])
    return {"ok": True}


@_register("save_minebase_config")
def _save_minebase_config(params: dict) -> dict:
    from func.config_loader import save_minebase_config

    save_minebase_config(params["config"])
    return {"ok": True}


@_register("get_device_load_map")
def _get_device_load_map(params: dict) -> dict:
    from func.config_loader import get_device_load_map

    return get_device_load_map()


@_register("update_device_load_map")
def _update_device_load_map(params: dict) -> dict:
    from func.config_loader import update_device_load_map

    update_device_load_map(params["map_data"])
    return {"ok": True}


@_register("apply_device_load_map")
def _apply_device_load_map(params: dict) -> dict:
    from func.config_loader import apply_device_load_map

    apply_device_load_map(params["map_data"])
    return {"ok": True}


@_register("get_default_load_map")
def _get_default_load_map(params: dict) -> dict:
    from func.config_loader import get_default_load_map

    return get_default_load_map(params.get("version", "new"))


# ─── 列映射配置方法 ───

@_register("get_minebase_column_mapping")
def _get_minebase_column_mapping(params: dict) -> dict:
    """获取 MineBase 列映射配置。"""
    from func.config_loader import get_minebase_column_mapping
    return get_minebase_column_mapping()


@_register("save_minebase_column_mapping")
def _save_minebase_column_mapping(params: dict) -> dict:
    """保存 MineBase 列映射配置。"""
    from func.config_loader import save_minebase_column_mapping
    save_minebase_column_mapping(params["mapping"])
    return {"ok": True}


@_register("reset_minebase_column_mapping")
def _reset_minebase_column_mapping(params: dict) -> dict:
    """重置 MineBase 列映射为默认值。"""
    from func.config_loader import reset_minebase_column_mapping
    reset_minebase_column_mapping()
    return {"ok": True}


@_register("get_equipment_ledger_data")
def _get_equipment_ledger_data(params: dict) -> dict:
    ledger = _load_equipment_ledger_from_cache()
    if not ledger:
        return {"rows": [], "columns": []}
    rows = _sanitize_rows(ledger.to_dict())
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@_register("get_oil_ledger_data")
def _get_oil_ledger_data(params: dict) -> dict:
    ledger = _load_oil_ledger_from_cache()
    if not ledger:
        return {"rows": [], "columns": []}
    rows = _sanitize_rows(ledger.to_dict())
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


# ─── 台账文件操作方法 ───

@_register("load_ledger_file_columns")
def _load_ledger_file_columns(params: dict) -> dict:
    """读取 Excel 文件的列名（用于列映射）。"""
    import pandas as pd
    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    df = pd.read_excel(safe_path, nrows=0)
    return {"columns": [str(c) for c in df.columns]}


@_register("load_oil_ledger_file_columns")
def _load_oil_ledger_file_columns(params: dict) -> dict:
    """读取 Excel 文件的列名（油品台账，用于列映射）。"""
    import pandas as pd
    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    df = pd.read_excel(safe_path, nrows=0)
    return {"columns": [str(c) for c in df.columns]}


@_register("import_equipment_ledger")
def _import_equipment_ledger(params: dict) -> dict:
    """导入设备台账 Excel，应用列映射后保存到缓存。"""
    from func.equipment_ledger import EquipmentLedger
    from func.config_loader import save_equipment_ledger_cache

    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    ledger = EquipmentLedger()
    ledger.load(safe_path, column_mapping=params.get("column_mapping"))
    records = ledger.to_dict()
    save_equipment_ledger_cache(records)
    return {"ok": True, "count": len(records)}


@_register("import_oil_ledger")
def _import_oil_ledger(params: dict) -> dict:
    """导入油品台账 Excel，应用列映射后保存到缓存。"""
    from func.oil_ledger import OilLedger
    from func.config_loader import save_oil_ledger_cache

    safe_path = str(_sanitize_path(params["file_path"], must_exist=True, allow_dir=False))
    ledger = OilLedger()
    ledger.load(safe_path, column_mapping=params.get("column_mapping"))
    records = ledger.to_dict()
    save_oil_ledger_cache(records)
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
    """读取指定 Sheet 的数据（默认限制 5000 行）。"""
    import pandas as pd
    safe_path = str(_sanitize_path(params["path"], must_exist=True, allow_dir=False))
    max_rows = params.get("max_rows", 5000)
    df = pd.read_excel(safe_path, sheet_name=params["sheet"])
    columns = [str(c) for c in df.columns]
    total = len(df)
    if len(df) > max_rows:
        df = df.head(max_rows)
    rows = _sanitize_rows(df.to_dict("records"))
    return {"columns": columns, "rows": rows, "total": total, "truncated": total > max_rows}


@_register("ledger_match_preview")
def _ledger_match_preview(params: dict) -> dict:
    """对数据行进行台账匹配预览。"""
    rows = params["rows"]
    name_col = params.get("name_column")
    id_col = params.get("id_column")
    oil_col = params.get("oil_column")
    mode = params.get("mode", "name")
    suffix = params.get("result_suffix", "")

    # 根据 suffix 生成带后缀的字段名
    def _key(base: str) -> str:
        return f"{base}_{suffix}" if suffix else base

    # 加载台账
    equipment_ledger = _load_equipment_ledger_from_cache()
    oil_ledger = _load_oil_ledger_from_cache()

    matched_count = 0
    for row in rows:
        matched = False

        # 设备匹配：优先 ID，其次名称
        if id_col and equipment_ledger:
            device_id = str(row.get(id_col, "")).strip()
            if device_id:
                result = equipment_ledger.match_by_id(device_id)
                if result:
                    row[_key("标准设备名称")] = result.get("标准设备名称", result.get("标准名称", ""))
                    row[_key("标准设备编号")] = result.get("标准设备编号", "")
                    row[_key("标准公司名称")] = result.get("标准公司名称", "")
                    matched = True

        if not matched and name_col and equipment_ledger:
            device_name = str(row.get(name_col, "")).strip()
            if device_name:
                if mode == "id":
                    result = equipment_ledger.match_by_id(device_name)
                else:
                    result = equipment_ledger.match_device(device_name)
                if result:
                    row[_key("标准设备名称")] = result.get("标准设备名称", result.get("标准名称", ""))
                    row[_key("标准设备编号")] = result.get("标准设备编号", "")
                    row[_key("标准公司名称")] = result.get("标准公司名称", "")
                    matched = True

        if oil_col:
            oil_name = str(row.get(oil_col, "")).strip()
            if oil_name and oil_ledger:
                oil_result = oil_ledger.match(oil_name)
                if oil_result:
                    row["标准油品名称"] = oil_result.get("标准名称", "")
                    row["匹配方式"] = oil_result.get("匹配方式", "")
                    row["相似度"] = oil_result.get("相似度", "")
                    matched = True

        row[_key("__matched")] = matched
        if matched:
            matched_count += 1

    return {
        "matched": matched_count,
        "unmatched": len(rows) - matched_count,
        "rows": _sanitize_rows(rows),
    }


@_register("export_matched_data")
def _export_matched_data(params: dict) -> dict:
    """将匹配后的数据导出为 Excel。"""
    import pandas as pd
    rows = params["rows"]
    columns = params["columns"]
    safe_output = str(_sanitize_path(params["output_path"], allow_dir=False))

    # 移除内部标记列
    export_cols = [c for c in columns if c != "__matched"]
    df = pd.DataFrame(rows)
    # 确保列顺序
    for col in export_cols:
        if col not in df.columns:
            df[col] = ""
    from func.excel_formatter import write_formatted_excel

    df = df[export_cols]
    write_formatted_excel(safe_output, {"导出数据": df})
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
    return {"pong": True, "pid": __import__("os").getpid(), "version": "1.0.0"}


@_register("test_minebase_connection")
def _test_minebase_connection(params: dict) -> dict:
    """测试 MineBase 连接（API 或数据库模式）。

    如果前端传入 __keyring__ 哨兵值，自动从已保存的配置中加载真实密码，
    方便用户无需重新输入密码即可测试连接。
    """
    from func.config_loader import get_minebase_api_config, get_minebase_db_config
    from func.sync_to_minebase import test_api_connection, test_db_connection

    KEYRING_SENTINEL = "__keyring__"
    mode = params.get("mode", "api")
    password = params.get("password", "")

    if password == KEYRING_SENTINEL:
        if mode == "api":
            password = get_minebase_api_config().get("password", "")
        else:
            password = get_minebase_db_config().get("password", "")

    if mode == "api":
        ok, msg = test_api_connection(
            url=params.get("url", "http://localhost:3000"),
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


# ═══════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════


def _handle_request(req: dict) -> None:
    """处理单个 RPC 请求。"""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method not in _METHODS:
        _send({"id": req_id, "error": f"Unknown method: {method}"})
        return

    try:
        result = _METHODS[method](params)
        _send({"id": req_id, "result": result})
    except Exception:
        ref_id = secrets.token_hex(4)
        logger.error("RPC error ref=%s method=%s", ref_id, method, exc_info=True)
        _send({"id": req_id, "error": f"处理失败 (ref: {ref_id})，请查看日志获取详情"})


def main() -> None:
    """入口：从 stdin 逐行读取 JSON 请求，处理后写回 stdout。"""
    _setup_logging()
    _emit("log", {"level": "INFO", "message": "Python bridge started"})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send({"error": f"Invalid JSON: {e}"})
            continue

        # 请求在当前线程处理，长时间任务会阻塞后续请求
        # 但 batch_process 内部使用 ThreadPoolExecutor，所以可以接受
        _handle_request(req)


if __name__ == "__main__":
    main()
