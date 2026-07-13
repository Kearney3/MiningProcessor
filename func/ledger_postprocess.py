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
from func.string_utils import clean_string

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

    def _extract(result, key):
        return result.get(key, "") if result else ""

    matched_count = 0
    unmatched_count = 0

    if id_col:
        # Composite key: batch match on unique (name, id) pairs
        unique_pairs = df[[name_col, id_col]].drop_duplicates()
        pair_to_result: dict[tuple, dict] = {}
        for _, row in unique_pairs.iterrows():
            name_str = clean_string(row[name_col]) or None
            id_str = clean_string(row[id_col]) or None
            result = equipment_ledger.match_device(
                name=name_str, device_id=id_str
            )
            pair_to_result[(row[name_col], row[id_col])] = result
            if result:
                matched_count += 1
            else:
                unmatched_count += 1

        df[result_name_col] = df.apply(
            lambda r: _extract(pair_to_result.get((r[name_col], r[id_col])), "标准设备名称"),
            axis=1,
        )
        df[result_id_col] = df.apply(
            lambda r: _extract(pair_to_result.get((r[name_col], r[id_col])), "标准设备编号"),
            axis=1,
        )
        df[result_company_col] = df.apply(
            lambda r: _extract(pair_to_result.get((r[name_col], r[id_col])), "标准公司名称"),
            axis=1,
        )
    else:
        # No id column: batch match on unique names only
        unique_names = df[name_col].dropna().unique()
        name_to_result: dict = {}
        for name in unique_names:
            name_str = clean_string(name) or None
            result = equipment_ledger.match_device(name=name_str)
            name_to_result[name] = result
            if result:
                matched_count += 1
            else:
                unmatched_count += 1

        df[result_name_col] = df[name_col].map(
            lambda n: _extract(name_to_result.get(n), "标准设备名称")
        )
        df[result_id_col] = df[name_col].map(
            lambda n: _extract(name_to_result.get(n), "标准设备编号")
        )
        df[result_company_col] = df[name_col].map(
            lambda n: _extract(name_to_result.get(n), "标准公司名称")
        )

    label = f"设备{suffix}" if suffix else "设备"
    logger.info(
        "台账匹配[%s]: 成功 %d, 失败 %d, 共 %d 条",
        label, matched_count, unmatched_count, matched_count + unmatched_count,
    )

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
    matched_count = 0
    unmatched_count = 0
    std_oils = []
    for row in df.itertuples(index=False):
        val = getattr(row, oil_col, None)
        cleaned = clean_string(val)
        if not cleaned:
            std_oils.append("")
        else:
            r = oil_ledger.match(cleaned)
            if r:
                std_oils.append(r["标准名称"])
                matched_count += 1
            else:
                std_oils.append("")
                unmatched_count += 1
    df["标准油品名称"] = std_oils
    logger.info(
        "台账匹配[油品]: 成功 %d, 失败 %d, 共 %d 条",
        matched_count, unmatched_count, matched_count + unmatched_count,
    )
    return True


def match_sheets(
    sheets: dict[str, pd.DataFrame],
    equipment_ledger: Optional[EquipmentLedger] = None,
    oil_ledger: Optional[OilLedger] = None,
) -> dict[str, pd.DataFrame]:
    """对 sheets 字典进行台账匹配后处理，返回更新后的 sheets。

    对于生产数据（同时包含矿卡名称和挖机名称），匹配列名会添加
    （矿卡）或（挖机）后缀。

    Args:
        sheets: {sheet_name: DataFrame} 字典
        equipment_ledger: 设备台账实例，None 表示不匹配设备
        oil_ledger: 油品台账实例，None 表示不匹配油品

    Returns:
        匹配后的 sheets 字典（返回新字典，DataFrame 为副本）
    """
    if not equipment_ledger and not oil_ledger:
        return sheets

    result = {}
    for sheet_name, df in sheets.items():
        new_df = df.copy()
        cols = set(new_df.columns)

        if equipment_ledger:
            has_truck_col = "矿卡名称" in cols
            has_excavator_col = "挖机名称" in cols

            if has_truck_col and has_excavator_col:
                id_col = "设备编号" if "设备编号" in cols else None
                _match_equipment_rows(new_df, "矿卡名称", id_col, equipment_ledger, "（矿卡）")
                _match_equipment_rows(new_df, "挖机名称", None, equipment_ledger, "（挖机）")
            else:
                name_col = _find_col(cols, ["设备名称", "矿卡名称"])
                id_col = "设备编号" if "设备编号" in cols else None
                if name_col:
                    _match_equipment_rows(new_df, name_col, id_col, equipment_ledger)

        if oil_ledger:
            oil_col = _find_col(cols, ["油品种类", "油品名称"])
            if oil_col:
                _match_oil_rows(new_df, oil_col, oil_ledger)

        result[sheet_name] = new_df

    return result


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

    initial_col_counts = {name: len(df.columns) for name, df in sheets_to_match.items()}
    matched_sheets = match_sheets(sheets_to_match, equipment_ledger, oil_ledger)

    # 检查是否有匹配发生（match_sheets 返回副本，比较列数前后的差异）
    any_matched = any(
        len(matched_sheets[name].columns) > initial_col_counts[name]
        for name in matched_sheets
    )
    if not any_matched:
        return False

    from func.excel_formatter import write_formatted_excel

    # 重写 Excel（先去重再格式化输出）
    deduped_sheets = {
        name: dedup_dataframe(df, f"台账匹配-{name}")
        for name, df in matched_sheets.items()
    }
    write_formatted_excel(output_file, deduped_sheets)
    logger.info("台账匹配完成，已更新: %s", output_file)
    return True
