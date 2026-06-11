"""
台账匹配后处理模块
供 Flet GUI 和 Tauri 客户端共用，避免逻辑重复。
"""

import logging
from typing import Optional

import pandas as pd

from func.equipment_ledger import EquipmentLedger
from func.oil_ledger import OilLedger
from func.excel_utils import dedup_dataframe

logger = logging.getLogger(__name__)


def _find_col(columns: set[str], candidates: list[str]) -> Optional[str]:
    """在列名集合中查找第一个匹配的候选列名（支持 strip 匹配）"""
    # 先尝试精确匹配
    for c in candidates:
        if c in columns:
            return c
    # 再尝试 strip 后匹配
    stripped_map = {col.strip(): col for col in columns}
    for c in candidates:
        if c in stripped_map:
            return stripped_map[c]
    return None


def _match_equipment_rows(
    df: pd.DataFrame,
    name_col: str,
    id_col: Optional[str],
    equipment_ledger: EquipmentLedger,
    suffix: str = "",
) -> bool:
    """
    对 DataFrame 中的设备列进行台账匹配，原地添加标准列。
    返回 True 表示有匹配发生。
    """
    result_name_col = f"标准设备名称{suffix}"
    result_id_col = f"标准设备编号{suffix}"
    result_company_col = f"标准公司名称{suffix}"

    std_names = []
    std_ids = []
    std_companies = []

    # 使用 itertuples 替代 iterrows，性能提升 5-10 倍
    for row in df.itertuples(index=False):
        name_val = getattr(row, name_col, None)
        name_str = str(name_val) if name_val is not None and not pd.isna(name_val) else None

        id_str = None
        if id_col:
            id_val = getattr(row, id_col, None)
            id_str = str(id_val) if id_val is not None and not pd.isna(id_val) else None

        r = equipment_ledger.match_device(name=name_str, device_id=id_str)
        std_names.append(r.get("标准设备名称", "") if r else "")
        std_ids.append(r.get("标准设备编号", "") if r else "")
        std_companies.append(r.get("标准公司名称", "") if r else "")

    df[result_name_col] = std_names
    df[result_id_col] = std_ids
    df[result_company_col] = std_companies
    return True


def _match_oil_rows(
    df: pd.DataFrame,
    oil_col: str,
    oil_ledger: OilLedger,
) -> bool:
    """
    对 DataFrame 中的油品列进行台账匹配，原地添加标准列。
    返回 True 表示有匹配发生。
    """
    std_oils = []
    for row in df.itertuples(index=False):
        val = getattr(row, oil_col, None)
        if val is None or pd.isna(val):
            std_oils.append("")
        else:
            r = oil_ledger.match(str(val))
            std_oils.append(r["标准名称"] if r else "")
    df["标准油品名称"] = std_oils
    return True


def apply_ledger_matching(
    output_file: str,
    equipment_ledger: Optional[EquipmentLedger] = None,
    oil_ledger: Optional[OilLedger] = None,
    preloaded_sheets: Optional[dict[str, pd.DataFrame]] = None,
) -> bool:
    """
    对已写入的 Excel 文件进行台账匹配后处理。
    读取每个 sheet，检测列名，追加匹配字段，重新写回。

    对于生产数据（同时包含矿卡名称和挖机名称），匹配列名会添加（矿卡）或（挖机）后缀。

    Args:
        output_file: 输出 Excel 文件路径
        equipment_ledger: 设备台账实例，None 表示不匹配设备
        oil_ledger: 油品台账实例，None 表示不匹配油品
        preloaded_sheets: 预加载的 sheet 数据 {sheet_name: DataFrame}，
                          None 时从 output_file 读取

    Returns:
        True 表示有匹配发生并已写回，False 表示无匹配或无需处理
    """
    if not equipment_ledger and not oil_ledger:
        return False

    if preloaded_sheets:
        sheets_to_match = dict(preloaded_sheets)
    else:
        try:
            xl = pd.ExcelFile(output_file)
        except Exception as ex:
            logger.warning("无法读取输出文件进行台账匹配: %s", ex)
            return False
        sheets_to_match = {name: xl.parse(name) for name in xl.sheet_names}

    sheet_data = {}
    matched_any = False

    for sheet_name, df in sheets_to_match.items():
        cols = set(df.columns)

        # 设备匹配
        if equipment_ledger:
            has_truck_col = "矿卡名称" in cols
            has_excavator_col = "挖机名称" in cols

            if has_truck_col and has_excavator_col:
                # 生产数据场景：同时匹配矿卡和挖机
                id_col = "设备编号" if "设备编号" in cols else None
                _match_equipment_rows(df, "矿卡名称", id_col, equipment_ledger, "（矿卡）")
                _match_equipment_rows(df, "挖机名称", None, equipment_ledger, "（挖机）")
                matched_any = True
            else:
                # 单列匹配（非生产数据场景）
                name_col = _find_col(cols, ["设备名称", "矿卡名称"])
                id_col = "设备编号" if "设备编号" in cols else None
                if name_col:
                    _match_equipment_rows(df, name_col, id_col, equipment_ledger)
                    matched_any = True

        # 油品匹配
        if oil_ledger:
            oil_col = _find_col(cols, ["油品种类", "油品名称"])
            if oil_col:
                _match_oil_rows(df, oil_col, oil_ledger)
                matched_any = True

        sheet_data[sheet_name] = df

    if not matched_any:
        return False

    # 重写 Excel
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sheet_name, df in sheet_data.items():
            df = dedup_dataframe(df, f"台账匹配-{sheet_name}")
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    logger.info("台账匹配完成，已更新: %s", output_file)
    return True
