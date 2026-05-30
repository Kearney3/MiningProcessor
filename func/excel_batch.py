"""
批量处理模块
在一个文件夹中同时进行燃油、电力、生产、工时数据处理
支持关键字配置、合并输出（带 sheet 前缀）或分别输出
"""

import logging
import os
import pandas as pd
from datetime import datetime

from func.excel_fuel import process_diesel_data
from func.excel_electrical import parse_excel_data
from func.excel_production_enhanced import MiningDataProcessor
from func.excel_worktime import process_excel_data
from func.equipment_ledger import EquipmentLedger
from func.oil_ledger import OilLedger
from func import config_loader
from func.logger import get_logger

logger = get_logger(__name__)

MODULE_LABELS = {
    "fuel": "燃油数据",
    "electrical": "电力数据",
    "production": "生产数据",
    "worktime": "工时数据",
}

MODULE_PREFIXES = {
    "fuel": "燃油数据_",
    "electrical": "电力数据_",
    "production": "生产数据_",
    "worktime": "工时数据_",
}


# ---------------------------------------------------------------------------
# 文件匹配
# ---------------------------------------------------------------------------

def scan_files(folder_path: str, keywords: dict[str, list[str]] | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """
    按文件名关键字扫描文件夹，返回各模块匹配到的文件路径列表和缺失模块列表。
    Sheet 级别的匹配由各处理器内部完成，此处仅做文件名筛选。

    Args:
        folder_path: 文件夹路径
        keywords: {模块类型: [关键字]}，默认从用户配置读取

    Returns:
        (matched, missing)
        matched: {"fuel": [path, ...], "electrical": [...], ...}
        missing: ["fuel", "electrical", ...]  未找到文件的模块类型
    """
    if keywords is None:
        keywords = config_loader.get_file_keywords()

    excel_files = sorted([
        f for f in os.listdir(folder_path)
        if f.lower().endswith((".xlsx", ".xls")) and not f.startswith("~$")
    ])

    matched: dict[str, list[str]] = {}
    all_types = ["fuel", "electrical", "production", "worktime"]

    for module_type in all_types:
        kw_list = keywords.get(module_type, [])
        if not kw_list:
            continue
        found = [
            os.path.join(folder_path, fname)
            for fname in excel_files
            if any(k in fname for k in kw_list)
        ]
        if found:
            matched[module_type] = found

    missing = [t for t in all_types if t not in matched]
    return matched, missing


# ---------------------------------------------------------------------------
# 处理
# ---------------------------------------------------------------------------

def process_files(
    folder_path: str,
    matched: dict[str, list[str]],
    year: int | None = None,
    month: int | None = None,
    raw_start: int = -1,
    merge_output: bool = True,
    equipment_ledger: EquipmentLedger = None,
    oil_ledger: OilLedger = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """
    根据已匹配的文件列表执行批量处理。

    Args:
        folder_path: 文件夹路径
        matched: scan_files 返回的 matched 字典
        year/month: 年份/月份
        raw_start: 生产数据表头起始行（-1 自动检测）
        merge_output: 是否合并输出
        equipment_ledger / oil_ledger: 台账实例

    Returns:
        {模块类型: {sheet名: DataFrame}}
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    all_results: dict[str, dict[str, pd.DataFrame]] = {}

    # ── 燃油数据 ──
    if "fuel" in matched:
        for fpath in matched["fuel"]:
            try:
                logger.info(f"燃油数据源: {os.path.basename(fpath)}")
                sheets = process_diesel_data(fpath, target_year=year, return_sheets=True)
                if sheets:
                    all_results["fuel"] = sheets
                    break
            except Exception as e:
                logger.error(f"燃油处理失败: {os.path.basename(fpath)} -> {e}")

    # ── 电力数据 ──
    if "electrical" in matched:
        for fpath in matched["electrical"]:
            try:
                logger.info(f"电力数据源: {os.path.basename(fpath)}")
                sheets = parse_excel_data(fpath, target_year=year, return_sheets=True)
                if sheets:
                    all_results["electrical"] = sheets
                    break
            except Exception as e:
                logger.error(f"电力处理失败: {os.path.basename(fpath)} -> {e}")

    # ── 生产数据 ──
    if "production" in matched:
        try:
            processor = MiningDataProcessor(version="new", raw_start=raw_start)
            sheets = processor.process_folder(folder_path, return_sheets=True)
            if sheets:
                all_results["production"] = sheets
            else:
                logger.warning("生产数据处理无结果")
        except Exception as e:
            logger.error(f"生产数据处理失败: {e}")

    # ── 工时数据 ──
    if "worktime" in matched:
        for fpath in matched["worktime"]:
            try:
                logger.info(f"工时数据源: {os.path.basename(fpath)}")
                sheets = process_excel_data(fpath, year, month, return_sheets=True)
                if sheets:
                    all_results["worktime"] = sheets
                    break
            except Exception as e:
                logger.error(f"工时处理失败: {os.path.basename(fpath)} -> {e}")

    # ── 日志摘要 ──
    success_labels = [MODULE_LABELS.get(k, k) for k in all_results]
    all_types = ["fuel", "electrical", "production", "worktime"]
    failed_labels = [MODULE_LABELS.get(k, k) for k in all_types if k not in all_results]
    logger.info(f"处理完成 — 成功: {', '.join(success_labels) or '无'}; 失败: {', '.join(failed_labels) or '无'}")

    if not all_results:
        logger.error("所有模块均无数据")
        return {}

    # ── 台账匹配 ──
    if equipment_ledger or oil_ledger:
        for module_type in list(all_results.keys()):
            all_results[module_type] = _apply_ledger_to_sheets(
                all_results[module_type], equipment_ledger, oil_ledger
            )

    # ── 输出 ──
    if merge_output:
        _write_merged(all_results, folder_path, year, month)
    else:
        _write_separate(all_results, folder_path, year, month)

    return all_results


# ---------------------------------------------------------------------------
# 台账匹配
# ---------------------------------------------------------------------------

def _find_col(columns, candidates):
    """在列名列表中查找第一个匹配的候选列名"""
    for c in candidates:
        if c in columns:
            return c
    return None


def _apply_ledger_to_sheets(
    sheets: dict[str, pd.DataFrame],
    equipment_ledger: EquipmentLedger = None,
    oil_ledger: OilLedger = None,
) -> dict[str, pd.DataFrame]:
    """
    对 sheets 字典进行台账匹配后处理，返回更新后的 sheets。
    """
    if not equipment_ledger and not oil_ledger:
        return sheets

    matched_any = False
    for sheet_name, df in sheets.items():
        cols = set(df.columns)

        if equipment_ledger:
            name_col = _find_col(cols, ["设备名称", "矿卡名称"])
            id_col = "设备编号" if "设备编号" in cols else None
            if name_col:
                std_names, std_ids, std_companies = [], [], []
                for _, row in df.iterrows():
                    name_val = row.get(name_col)
                    id_val = row.get(id_col) if id_col else None
                    name_str = str(name_val) if not pd.isna(name_val) else None
                    id_str = str(id_val) if id_val is not None and not pd.isna(id_val) else None
                    result = equipment_ledger.match_device(name=name_str, device_id=id_str)
                    if result:
                        std_names.append(result.get("标准设备名称", ""))
                        std_ids.append(result.get("标准设备编号", ""))
                        std_companies.append(result.get("标准公司名称", ""))
                    else:
                        std_names.append("")
                        std_ids.append("")
                        std_companies.append("")
                df["标准设备名称"] = std_names
                df["标准设备编号"] = std_ids
                df["标准公司名称"] = std_companies
                matched_any = True

        if oil_ledger:
            oil_col = _find_col(cols, ["油品种类", "油品名称"])
            if oil_col:
                std_oils = []
                for _, row in df.iterrows():
                    oil_val = row.get(oil_col)
                    if pd.isna(oil_val):
                        std_oils.append("")
                    else:
                        result = oil_ledger.match(str(oil_val))
                        std_oils.append(result["标准名称"] if result else "")
                df["标准油品名称"] = std_oils
                matched_any = True

        sheets[sheet_name] = df

    if matched_any:
        logger.info("台账匹配完成")
    return sheets


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _write_merged(
    all_results: dict[str, dict[str, pd.DataFrame]],
    folder_path: str,
    year: int,
    month: int,
):
    """将所有模块的结果合并到单个 Excel 文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(folder_path, f"批量处理结果_{year}{month:02d}_{timestamp}.xlsx")

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for module_type, sheets in all_results.items():
            prefix = MODULE_PREFIXES.get(module_type, f"{module_type}_")
            for sheet_name, df in sheets.items():
                prefixed_name = f"{prefix}{sheet_name}"
                if len(prefixed_name) > 31:
                    prefixed_name = prefixed_name[:31]
                df.to_excel(writer, sheet_name=prefixed_name, index=False)
                logger.info(f"写入 Sheet: {prefixed_name} ({len(df)} 行)")

    logger.info(f"合并输出完成: {output_file}")


def _write_separate(
    all_results: dict[str, dict[str, pd.DataFrame]],
    folder_path: str,
    year: int,
    month: int,
):
    """将各模块结果分别输出为独立 Excel 文件"""
    output_files = {
        "fuel": "Fuel.xlsx",
        "electrical": "电力消耗统计.xlsx",
        "production": "合并产量.xlsx",
        "worktime": f"{year}{month:02d}_工作效率表.xlsx",
    }

    for module_type, sheets in all_results.items():
        if not sheets:
            continue
        output_file = os.path.join(folder_path, output_files.get(module_type, f"{module_type}.xlsx"))
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.info(f"写入: {output_file} / {sheet_name} ({len(df)} 行)")
        logger.info(f"单独输出完成: {output_file}")
