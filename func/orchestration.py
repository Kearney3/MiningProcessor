"""
共享编排逻辑模块

供 Flet GUI 和 Tauri bridge 共用的编排函数，消除跨模块重复代码。
"""

import logging
from typing import Optional

import pandas as pd

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

    return apply_ledger_matching(output_file, equipment_ledger, oil_ledger, preloaded_sheets)


def postprocess_from_cache(
    output_file: str,
    use_equipment_ledger: bool = False,
    use_oil_ledger: bool = False,
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
    if not use_equipment_ledger and not use_oil_ledger:
        return False

    equipment_ledger, oil_ledger = load_ledgers(
        use_equipment=use_equipment_ledger,
        use_oil=use_oil_ledger,
    )
    return postprocess_with_ledgers(output_file, equipment_ledger, oil_ledger, preloaded_sheets)


# ---------------------------------------------------------------------------
# 工时表头映射配置构建
# ---------------------------------------------------------------------------


def build_worktime_header_mapping(
    mode: Optional[str] = None,
    fuzzy: Optional[bool] = None,
    fuzzy_match: Optional[bool] = None,
) -> dict:
    """构建工时表头映射配置。

    从 config_loader 获取基础配置，然后按传入参数覆盖 mode 和 fuzzy。

    支持 ``fuzzy_match`` 别名（前端兼容），当 ``fuzzy`` 为 None 时回退到
    ``fuzzy_match`` 的值。

    Args:
        mode: 覆盖映射模式（"position" 或 "name"），None 时使用配置默认值
        fuzzy: 是否启用模糊匹配，None 时回退到 fuzzy_match
        fuzzy_match: fuzzy 的别名，用于兼容前端参数名

    Returns:
        完整的 header_mapping dict，可直接传给 process_worktime_data / process_excel_data
    """
    from func.config_loader import get_worktime_header_mapping

    mapping = get_worktime_header_mapping()
    if mode is not None:
        mapping["mode"] = mode
    if fuzzy is not None:
        mapping["fuzzy"] = fuzzy
    elif fuzzy_match is not None:
        mapping["fuzzy"] = fuzzy_match
    return mapping
