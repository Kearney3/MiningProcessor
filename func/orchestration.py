"""
共享编排逻辑模块

供 Flet GUI 和 Tauri bridge 共用的编排函数，消除跨模块重复代码。
"""

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from func.excel_utils import get_output_filename

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 台账加载（从缓存文件）
# ---------------------------------------------------------------------------


def load_equipment_ledger_from_cache():
    """从缓存加载设备台账实例，失败返回 None。

    Returns:
        EquipmentLedger instance or None
    """
    from func.equipment_ledger import EquipmentLedger
    from func.config_loader import has_equipment_ledger_cache, load_equipment_ledger_cache

    try:
        if has_equipment_ledger_cache():
            cached = load_equipment_ledger_cache()
            if cached:
                ledger = EquipmentLedger()
                ledger._df = pd.DataFrame(cached)
                ledger._build_search_cache()
                return ledger
    except Exception:
        logger.debug("设备台账缓存加载失败", exc_info=True)
    return None


def load_oil_ledger_from_cache():
    """从缓存加载油品台账实例，失败返回 None。

    Returns:
        OilLedger instance or None
    """
    from func.oil_ledger import OilLedger
    from func.config_loader import has_oil_ledger_cache, load_oil_ledger_cache

    try:
        if has_oil_ledger_cache():
            cached = load_oil_ledger_cache()
            if cached:
                ledger = OilLedger()
                ledger._df = pd.DataFrame(cached)
                ledger._build_search_cache()
                return ledger
    except Exception:
        logger.debug("油品台账缓存加载失败", exc_info=True)
    return None


def load_model_ledger_from_cache():
    """从缓存加载型号台账实例，失败返回 None。"""
    from func.model_ledger import ModelLedger
    from func.config_loader import has_model_ledger_cache, load_model_ledger_cache

    try:
        if has_model_ledger_cache():
            cached = load_model_ledger_cache()
            if cached:
                ledger = ModelLedger()
                ledger._df = pd.DataFrame(cached)
                ledger._build_search_cache()
                return ledger
    except Exception:
        logger.debug("型号台账缓存加载失败", exc_info=True)
    return None


def load_ledgers(
    use_equipment: bool = False,
    use_oil: bool = False,
) -> tuple:
    """按需从缓存加载设备台账和油品台账。

    Args:
        use_equipment: 是否加载设备台账
        use_oil: 是否加载油品台账

    Returns:
        (equipment_ledger, oil_ledger) — 未启用时对应位置为 None
    """
    equipment = load_equipment_ledger_from_cache() if use_equipment else None
    oil = load_oil_ledger_from_cache() if use_oil else None
    return equipment, oil


# ---------------------------------------------------------------------------
# 台账匹配后处理
# ---------------------------------------------------------------------------


def postprocess_with_ledgers(
    output_file: str,
    equipment_ledger=None,
    oil_ledger=None,
    preloaded_sheets: Optional[dict[str, pd.DataFrame]] = None,
    model_ledger=None,
) -> bool:
    """对输出 Excel 文件进行台账匹配后处理。

    Args:
        output_file: 输出 Excel 文件路径
        equipment_ledger: 设备台账实例，None 表示不匹配设备
        oil_ledger: 油品台账实例，None 表示不匹配油品
        preloaded_sheets: 预加载的 sheet 数据，None 时从文件读取

    Returns:
        True 表示有匹配发生并已写回，False 表示无匹配
    """
    from func.ledger_postprocess import apply_ledger_matching

    if model_ledger is None:
        return apply_ledger_matching(
            output_file, equipment_ledger, oil_ledger, preloaded_sheets
        )
    return apply_ledger_matching(
        output_file,
        equipment_ledger,
        oil_ledger,
        preloaded_sheets,
        model_ledger=model_ledger,
    )


def postprocess_from_cache(
    output_file: str,
    use_equipment_ledger: bool = False,
    use_oil_ledger: bool = False,
    use_model_ledger: bool = False,
    preloaded_sheets: Optional[dict[str, pd.DataFrame]] = None,
) -> bool:
    """加载缓存台账后执行匹配后处理。

    适用于 Tauri bridge 等场景：先从缓存加载台账，再对输出文件执行匹配。
    如果两个开关都为 False，直接跳过不做任何处理。

    Args:
        output_file: 输出 Excel 文件路径
        use_equipment_ledger: 是否使用设备台账
        use_oil_ledger: 是否使用油品台账
        preloaded_sheets: 预加载的 sheet 数据

    Returns:
        True 表示有匹配发生并已写回，False 表示无匹配
    """
    if not use_equipment_ledger and not use_oil_ledger and not use_model_ledger:
        return False

    equipment_ledger, oil_ledger = load_ledgers(
        use_equipment=use_equipment_ledger,
        use_oil=use_oil_ledger,
    )
    model_ledger = load_model_ledger_from_cache() if use_model_ledger else None
    if model_ledger is None:
        return postprocess_with_ledgers(
            output_file, equipment_ledger, oil_ledger, preloaded_sheets
        )
    return postprocess_with_ledgers(
        output_file,
        equipment_ledger,
        oil_ledger,
        preloaded_sheets,
        model_ledger=model_ledger,
    )


# ---------------------------------------------------------------------------
# 工时表头映射配置构建
# ---------------------------------------------------------------------------


def build_worktime_header_mapping(
    mode: Optional[str] = None,
) -> dict:
    """构建工时表头映射配置。

    从 config_loader 获取基础配置，然后按传入参数覆盖 mode。

    Args:
        mode: 覆盖映射模式（"position" 或 "name"），None 时使用配置默认值

    Returns:
        完整的 header_mapping dict，可直接传给 process_worktime_data / process_excel_data
    """
    from func.config_loader import get_worktime_header_mapping

    mapping = get_worktime_header_mapping()
    if mode is not None:
        mapping["mode"] = mode
    return mapping


# ---------------------------------------------------------------------------
# 输出路径计算（统一供 Flet 和 Tauri 使用）
# ---------------------------------------------------------------------------


def get_output_path(
    module_type: str,
    path: str,
    *,
    year: int | None = None,
    month: int = 1,
    keyword: str = "",
) -> str | None:
    """根据模块类型和输入路径，计算输出文件路径。

    统一供 gui/logic.py::_get_output_file() 和 tauri_bridge.py 各 RPC 方法共用，
    消除两端各自内联计算输出路径的重复代码。

    Args:
        module_type: 模块类型 (fuel/electrical/production/worktime/merge/maint/batch)
        path: 输入文件或文件夹路径
        year: 年份（fuel/electrical/worktime），默认当前年
        month: 月份（worktime），默认 1
        keyword: 合并关键字（merge）

    Returns:
        输出文件路径字符串；batch 返回 None（已在内部处理）；
        维修记录返回 None（由 process_maintenance_data 自行返回路径）
    """
    from datetime import datetime

    if module_type == "batch":
        return None
    if module_type == "maint":
        return None
    if module_type == "merge":
        return os.path.join(path, f"{keyword}_合并.xlsx")

    effective_year = year if year is not None else datetime.now().year

    # 工时文件夹模式
    if module_type == "worktime" and os.path.isdir(path):
        return os.path.join(path, f"{effective_year}{month:02d}_多文件合并_工作效率表.xlsx")

    filename = get_output_filename(module_type, year=effective_year, month=month)
    if not filename:
        return None

    base = path if os.path.isdir(path) else os.path.dirname(path)
    return os.path.join(base or ".", filename)


# ---------------------------------------------------------------------------
# 统一单报表处理入口
# ---------------------------------------------------------------------------


def process_single(
    module_type: str,
    path: str,
    *,
    year: int | None = None,
    month: int = 1,
    raw_start: int = -1,
    keyword: str = "",
    strip_time: bool = False,
    sort_configs=None,
    add_shift_column: bool = False,
    default_shift: str = "Day",
    header_mapping: dict | None = None,
    tolerant_header: bool = False,
    dedup: bool = False,
    skip_hidden: bool = False,
    skip_hidden_rows: bool = False,
    skip_hidden_cols: bool = False,
    use_equipment_ledger: bool = False,
    use_oil_ledger: bool = False,
    use_model_ledger: bool = False,
    equipment_ledger=None,
    oil_ledger=None,
    model_ledger=None,
    anomaly_config=None,
    cancel_event=None,
    # maintenance 专属
    split_by_year: bool = False,
    details_only: bool = False,
    use_ml_fallback: bool = True,
    # production 专属过滤
    filter_zero_hours_meter: bool = False,
    filter_zero_km_meter: bool = False,
    filter_zero_run_hours: bool = False,
    filter_zero_run_km: bool = False,
    # fuel 专属过滤
    filter_zero_engine_hours: bool = False,
    filter_zero_work_hours: bool = False,
) -> dict:
    """统一单报表处理入口，供 Flet GUI 和 Tauri bridge 共用。

    按 module_type 分发到对应的 func/ 处理函数，计算输出文件路径，
    自动执行台账匹配后处理。

    外部可通过 equipment_ledger / oil_ledger 直接传入台账实例（Flet GUI 场景）；
    未传入时根据 use_*_ledger 开关从缓存自动加载（Tauri bridge 场景）。

    Returns:
        dict，始终包含 "output_file" 键（str | None）；
        production 额外包含 "summary"；
        maint（split_by_year）额外包含 "output_files"。

    Raises:
        ValueError: module_type 不支持
    """
    from datetime import datetime

    result: dict = {}

    # 单次任务使用独立的异常明细缓冲，供 GUI 任务完成后展示。
    if anomaly_config is not None and anomaly_config.enabled:
        anomaly_config._anomaly_counts = []
        anomaly_config._anomaly_records = []

    def _attach_anomaly_records() -> None:
        if anomaly_config is None:
            return
        records = list(getattr(anomaly_config, "_anomaly_records", None) or [])
        if records:
            result["anomalies"] = records
        anomaly_config._anomaly_records = None

    # 向后兼容
    if skip_hidden:
        skip_hidden_rows = True
        skip_hidden_cols = True

    effective_year = year if year is not None else datetime.now().year

    if use_model_ledger and not use_equipment_ledger and equipment_ledger is None:
        logger.warning("型号台账匹配需要同时启用设备台账匹配，已跳过型号台账")
        use_model_ledger = False
        model_ledger = None
    elif use_model_ledger and model_ledger is None:
        model_ledger = load_model_ledger_from_cache()

    # ── 分发到各处理器 ──
    if module_type == "fuel":
        from func.excel_fuel import process_diesel_data
        process_diesel_data(path, target_year=year,
                            skip_hidden_rows=skip_hidden_rows,
                            skip_hidden_cols=skip_hidden_cols,
                            anomaly_config=anomaly_config,
                            filter_zero_engine_hours=filter_zero_engine_hours,
                            filter_zero_work_hours=filter_zero_work_hours)

    elif module_type == "production":
        from func.excel_production_enhanced import MiningDataProcessor
        from func.config_loader import get_device_load_map, get_load_map_version
        load_map_ver = get_load_map_version()
        load_map = get_device_load_map(load_map_ver)
        processor = MiningDataProcessor(
            raw_start=raw_start, device_load_map=load_map,
            skip_hidden_rows=skip_hidden_rows,
            skip_hidden_cols=skip_hidden_cols,
            anomaly_config=anomaly_config,
            filter_zero_hours_meter=filter_zero_hours_meter,
            filter_zero_km_meter=filter_zero_km_meter,
            filter_zero_run_hours=filter_zero_run_hours,
            filter_zero_run_km=filter_zero_run_km,
        )
        if os.path.isdir(path):
            processor.process_folder(path, cancel_event=cancel_event)
        else:
            output = get_output_path("production", path)
            processor.process_single_file(path, output)
        result["summary"] = getattr(processor, "_processing_summary", None)

    elif module_type == "electrical":
        from func.excel_electrical import parse_excel_data
        parse_excel_data(
            path, target_year=year,
            add_shift_column=add_shift_column,
            default_shift=default_shift,
            skip_hidden_rows=skip_hidden_rows,
            skip_hidden_cols=skip_hidden_cols,
            anomaly_config=anomaly_config,
        )

    elif module_type == "worktime":
        out = get_output_path("worktime", path, year=effective_year, month=month)
        if os.path.isdir(path):
            from func.excel_worktime_multifile import process_directory
            process_directory(
                path, effective_year, month,
                output_file=out,
                header_mapping=header_mapping,
                skip_hidden_rows=skip_hidden_rows,
                skip_hidden_cols=skip_hidden_cols,
                anomaly_config=anomaly_config,
            )
        else:
            from func.excel_worktime import process_excel_data
            process_excel_data(
                path, effective_year, month,
                output_file=out,
                header_mapping=header_mapping,
                skip_hidden_rows=skip_hidden_rows,
                skip_hidden_cols=skip_hidden_cols,
                anomaly_config=anomaly_config,
            )

    elif module_type == "merge":
        from func.excel_merger import merge_excel_files
        merge_excel_files(
            path, keyword,
            strip_time=strip_time,
            sort_configs=sort_configs,
            skip_hidden_rows=skip_hidden_rows,
            skip_hidden_cols=skip_hidden_cols,
            tolerant_header=tolerant_header,
            dedup=dedup,
        )

    elif module_type == "maint":
        from func.excel_maintenance import process_maintenance_data
        from func.config_loader import get_maintenance_classifications
        eq_ledger = equipment_ledger
        if eq_ledger is None and use_equipment_ledger:
            eq_ledger = load_equipment_ledger_from_cache()
        classifications = get_maintenance_classifications()
        maint_result = process_maintenance_data(
            path,
            eq_ledger=eq_ledger,
            classifications=classifications,
            skip_hidden_rows=skip_hidden_rows,
            skip_hidden_cols=skip_hidden_cols,
            split_by_year=split_by_year,
            details_only=details_only,
            use_ml_fallback=use_ml_fallback,
        )
        # maintenance 自带台账匹配，但仍需外部后处理（oil_ledger 等）
        if isinstance(maint_result, list):
            for f in maint_result:
                if use_oil_ledger:
                    postprocess_from_cache(str(f), use_equipment_ledger=False, use_oil_ledger=True)
            result["output_file"] = str(maint_result[-1]) if maint_result else None
            result["output_files"] = [str(f) for f in maint_result]
            _attach_anomaly_records()
            return result
        if use_oil_ledger and maint_result:
            postprocess_from_cache(str(maint_result), use_equipment_ledger=False, use_oil_ledger=True)
        result["output_file"] = str(maint_result) if maint_result else None
        _attach_anomaly_records()
        return result

    else:
        raise ValueError(f"不支持的模块类型: {module_type}")

    # ── 计算输出文件路径（fuel/production/electrical/worktime/merge）──
    output_file = get_output_path(
        module_type, path, year=effective_year, month=month, keyword=keyword,
    )
    if not output_file:
        result["output_file"] = None
        _attach_anomaly_records()
        return result

    # ── 台账匹配后处理 ──
    if use_equipment_ledger or use_oil_ledger or use_model_ledger:
        if equipment_ledger is None and oil_ledger is None and model_ledger is None:
            cache_kwargs = {
                "use_equipment_ledger": use_equipment_ledger,
                "use_oil_ledger": use_oil_ledger,
            }
            if use_model_ledger:
                cache_kwargs["use_model_ledger"] = True
            postprocess_from_cache(output_file, **cache_kwargs)
        else:
            postprocess_with_ledgers(
                output_file,
                equipment_ledger,
                oil_ledger,
                model_ledger=model_ledger,
            )

    result["output_file"] = output_file
    _attach_anomaly_records()
    return result
