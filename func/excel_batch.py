"""
批量处理模块
在一个文件夹中同时进行燃油、电力、生产、工时数据处理
支持合并输出（带 sheet 前缀）或分别输出
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
from func.logger import get_logger

logger = get_logger(__name__)


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
    对合并后的 sheets 字典进行台账匹配后处理。
    返回更新后的 sheets 字典。
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
        logging.info("台账匹配完成")
    return sheets


def batch_process(
    folder_path: str,
    year: int | None = None,
    month: int | None = None,
    raw_start: int = -1,
    merge_output: bool = True,
    equipment_ledger: EquipmentLedger = None,
    oil_ledger: OilLedger = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """
    批量处理文件夹中的所有数据。

    Args:
        folder_path: 输入文件夹路径
        year: 目标年份（默认当前年）
        month: 目标月份（默认当前月）
        raw_start: 生产数据表头起始行（-1 为自动检测）
        merge_output: 是否合并输出到单个 Excel
        equipment_ledger: 设备台账实例
        oil_ledger: 油品台账实例

    Returns:
        {模块类型: {sheet名称: DataFrame}}
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    all_results: dict[str, dict[str, pd.DataFrame]] = {}

    excel_files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith((".xlsx", ".xls")) and not f.startswith("~$")
    ]

    # ── 燃油数据 ──
    fuel_found = False
    for fname in excel_files:
        fpath = os.path.join(folder_path, fname)
        try:
            xl = pd.ExcelFile(fpath)
            fuel_sheets = [s for s in xl.sheet_names if "设备柴油消耗" in s or "Техник" in s]
            if fuel_sheets:
                logger.info(f"燃油数据源: {fname}")
                sheets = process_diesel_data(fpath, target_year=year, return_sheets=True)
                if sheets:
                    all_results["fuel"] = sheets
                    fuel_found = True
                    break
        except Exception:
            continue
    if not fuel_found:
        logger.warning("未找到燃油数据文件")

    # ── 电力数据 ──
    elec_found = False
    for fname in excel_files:
        fpath = os.path.join(folder_path, fname)
        try:
            xl = pd.ExcelFile(fpath)
            elec_sheets = [s for s in xl.sheet_names if "Electrical" in s]
            if elec_sheets:
                logger.info(f"电力数据源: {fname}")
                sheets = parse_excel_data(fpath, target_year=year, return_sheets=True)
                if sheets:
                    all_results["electrical"] = sheets
                    elec_found = True
                    break
        except Exception:
            continue
    if not elec_found:
        logger.warning("未找到电力数据文件")

    # ── 生产数据 ──
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
    work_found = False
    for fname in excel_files:
        fpath = os.path.join(folder_path, fname)
        try:
            xl = pd.ExcelFile(fpath)
            if any(s.strip().isdigit() for s in xl.sheet_names):
                logger.info(f"工时数据源: {fname}")
                sheets = process_excel_data(fpath, year, month, return_sheets=True)
                if sheets:
                    all_results["worktime"] = sheets
                    work_found = True
                    break
        except Exception:
            continue
    if not work_found:
        logger.warning("未找到工时数据文件")

    # ── 日志摘要 ──
    module_names = {"fuel": "燃油", "electrical": "电力", "production": "生产", "worktime": "工时"}
    success = [module_names[k] for k in all_results]
    failed = [module_names[k] for k in module_names if k not in all_results]
    logger.info(f"处理完成 — 成功: {', '.join(success) or '无'}; 失败: {', '.join(failed) or '无'}")

    if not all_results:
        logger.error("所有模块均无数据")
        return {}

    # ── 台账匹配 ──
    if equipment_ledger or oil_ledger:
        for module_type in all_results:
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
# 输出
# ---------------------------------------------------------------------------

MODULE_PREFIXES = {
    "fuel": "燃油数据_",
    "electrical": "电力数据_",
    "production": "生产数据_",
    "worktime": "工时数据_",
}


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
                # Excel sheet 名称最长 31 字符
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
