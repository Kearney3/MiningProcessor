"""
批量处理模块
在一个文件夹中同时进行燃油、电力、生产、工时数据处理
支持关键字配置、合并输出（带 sheet 前缀）或分别输出
"""

import os
import pandas as pd
from datetime import datetime, date as date_type

from func.excel_fuel import process_diesel_data
from func.excel_electrical import parse_excel_data
from func.excel_production_enhanced import MiningDataProcessor
from func.excel_worktime import process_excel_data
from func.equipment_ledger import EquipmentLedger
from func.oil_ledger import OilLedger
from func import config_loader
from func.logger import get_logger
from func.excel_utils import dedup_dataframe, get_output_filename
from func.ledger_postprocess import match_sheets


logger = get_logger(__name__)

# Excel sheet 名称最大长度（Excel 限制为 31 字符）
MAX_SHEET_NAME_LENGTH = 31

# 表内合并输出阶段数
_MERGE_STAGE_COUNT = 3


def _check_cancel(cancel_event) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def _emit_progress(progress_cb, payload):
    if progress_cb is None:
        return
    try:
        progress_cb(payload)
    except Exception:
        logger.debug("progress_cb failed", exc_info=True)

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


def _process_fuel_module(files: list[str], year: int) -> dict[str, pd.DataFrame]:
    """处理燃油数据文件列表，返回第一个成功的 sheets 字典。"""
    for fpath in files:
        try:
            logger.info(f"燃油数据源: {os.path.basename(fpath)}")
            sheets = process_diesel_data(fpath, target_year=year, return_sheets=True)
            if sheets:
                return sheets
        except Exception as e:
            logger.error(f"燃油处理失败: {os.path.basename(fpath)} -> {e}", exc_info=True)
    return {}


def _process_electrical_module(files: list[str], year: int) -> dict[str, pd.DataFrame]:
    """处理电力数据文件列表，返回第一个成功的 sheets 字典。"""
    for fpath in files:
        try:
            logger.info(f"电力数据源: {os.path.basename(fpath)}")
            sheets = parse_excel_data(fpath, target_year=year, return_sheets=True)
            if sheets:
                return sheets
        except Exception as e:
            logger.error(f"电力处理失败: {os.path.basename(fpath)} -> {e}", exc_info=True)
    return {}


def _process_production_module(folder_path: str, raw_start: int) -> dict[str, pd.DataFrame]:
    """处理生产数据，返回 sheets 字典或空字典。"""
    try:
        processor = MiningDataProcessor(version="new", raw_start=raw_start)
        sheets = processor.process_folder(folder_path, return_sheets=True)
        if sheets:
            return sheets
        logger.warning("生产数据处理无结果")
    except Exception as e:
        logger.error(f"生产数据处理失败: {e}", exc_info=True)
    return {}


def _process_worktime_module(
    files: list[str], year: int, month: int, header_mapping: dict | None
) -> dict[str, pd.DataFrame]:
    """处理工时数据文件列表，返回第一个成功的 sheets 字典。"""
    for fpath in files:
        try:
            logger.info(f"工时数据源: {os.path.basename(fpath)}")
            sheets = process_excel_data(fpath, year, month, return_sheets=True,
                                        header_mapping=header_mapping)
            if sheets:
                return sheets
        except Exception as e:
            logger.error(f"工时处理失败: {os.path.basename(fpath)} -> {e}", exc_info=True)
    return {}


def process_files(
    folder_path: str,
    matched: dict[str, list[str]],
    year: int | None = None,
    month: int | None = None,
    raw_start: int = -1,
    merge_output: bool = True,
    equipment_ledger: EquipmentLedger = None,
    oil_ledger: OilLedger = None,
    filter_date: date_type | None = None,
    worktime_header_mapping: dict | None = None,
    table_merge_config: dict | None = None,
    progress_cb=None,
    cancel_event=None,
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
        filter_date: 若指定，只保留该日期的数据
        worktime_header_mapping: 工作效率表头映射配置（含 mode/fuzzy/entries）
        table_merge_config: 表内合并配置，如 {"base_type": "fuel"}。None 表示不启用。

    Returns:
        {模块类型: {sheet名: DataFrame}}
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    all_results: dict[str, dict[str, pd.DataFrame]] = {}
    _emit_progress(progress_cb, {"stage": "preparing", "percent": 0.0, "current": 0, "total": 0, "detail": "开始处理"})
    if _check_cancel(cancel_event):
        _emit_progress(progress_cb, {"stage": "cancelled", "percent": 0.0, "current": 0, "total": 0, "detail": "用户取消，已完成部分输出"})
        return all_results

    # ── 燃油数据 ──
    if "fuel" in matched:
        all_results["fuel"] = _process_fuel_module(matched["fuel"], year)

    # ── 电力数据 ──
    if "electrical" in matched:
        all_results["electrical"] = _process_electrical_module(matched["electrical"], year)

    # ── 生产数据 ──
    if "production" in matched:
        result = _process_production_module(folder_path, raw_start)
        if result:
            all_results["production"] = result

    # ── 工时数据 ──
    if "worktime" in matched:
        all_results["worktime"] = _process_worktime_module(
            matched["worktime"], year, month, worktime_header_mapping
        )

    # ── 日志摘要 ──
    success_labels = [MODULE_LABELS.get(k, k) for k in all_results]
    all_types = ["fuel", "electrical", "production", "worktime"]
    failed_labels = [MODULE_LABELS.get(k, k) for k in all_types if k not in all_results]
    logger.info(f"处理完成 — 成功: {', '.join(success_labels) or '无'}; 失败: {', '.join(failed_labels) or '无'}")

    if not all_results:
        logger.error("所有模块均无数据")
        return {}

    # ── 日期筛选 ──
    if filter_date is not None:
        all_results = _filter_by_date(all_results, filter_date)
        remaining = sum(len(s) for s in all_results.values())
        if remaining == 0:
            logger.warning(f"日期筛选后无剩余数据 ({filter_date})")
            return {}

    if _check_cancel(cancel_event):
        _emit_progress(progress_cb, {"stage": "cancelled", "percent": 0.0, "current": 0, "total": 0, "detail": "用户取消，已完成部分输出"})
        return all_results

    # ── 台账匹配 ──
    if equipment_ledger or oil_ledger:
        for module_type in list(all_results.keys()):
            all_results[module_type] = _apply_ledger_to_sheets(
                all_results[module_type], equipment_ledger, oil_ledger
            )

    if _check_cancel(cancel_event):
        _emit_progress(progress_cb, {"stage": "cancelled", "percent": 0.0, "current": 0, "total": 0, "detail": "用户取消，已完成部分输出"})
        return all_results

    # ── 输出 ──
    if table_merge_config:
        _table_merge_and_write(all_results, folder_path, year, month, table_merge_config, progress_cb=progress_cb, cancel_event=cancel_event)
    elif merge_output:
        _write_merged(all_results, folder_path, year, month, progress_cb=progress_cb, cancel_event=cancel_event)
    else:
        _write_separate(all_results, folder_path, year, month, progress_cb=progress_cb, cancel_event=cancel_event)

    return all_results


# ---------------------------------------------------------------------------
# 日期筛选
# ---------------------------------------------------------------------------

def _filter_by_date(
    all_results: dict[str, dict[str, pd.DataFrame]],
    target_date: date_type,
) -> dict[str, dict[str, pd.DataFrame]]:
    """对所有结果按「日期」列筛选，只保留 target_date 当天的行。"""
    filtered: dict[str, dict[str, pd.DataFrame]] = {}
    for module_type, sheets in all_results.items():
        kept: dict[str, pd.DataFrame] = {}
        for sheet_name, df in sheets.items():
            if "日期" not in df.columns:
                kept[sheet_name] = df
                continue
            col = df["日期"]
            if not pd.api.types.is_datetime64_any_dtype(col):
                col = pd.to_datetime(col, errors="coerce")
            mask = col.dt.date == target_date
            sub = df.loc[mask].copy()
            if not sub.empty:
                kept[sheet_name] = sub
                logger.info(f"[{module_type}] {sheet_name}: 筛选 {target_date} 保留 {len(sub)}/{len(df)} 行")
            else:
                logger.info(f"[{module_type}] {sheet_name}: 筛选 {target_date} 后无数据")
        if kept:
            filtered[module_type] = kept
    return filtered


# ---------------------------------------------------------------------------
# 台账匹配（委托给 ledger_postprocess.match_sheets）
# ---------------------------------------------------------------------------

def _apply_ledger_to_sheets(
    sheets: dict[str, pd.DataFrame],
    equipment_ledger: EquipmentLedger = None,
    oil_ledger: OilLedger = None,
) -> dict[str, pd.DataFrame]:
    """对 sheets 字典进行台账匹配后处理，返回更新后的 sheets。"""
    return match_sheets(sheets, equipment_ledger, oil_ledger)



# ---------------------------------------------------------------------------
# 表内合并：生产数据聚合 + 左合并流水线
# ---------------------------------------------------------------------------

def _add_default_shift(sheets: dict[str, pd.DataFrame], default_shift: str = "Night") -> dict[str, pd.DataFrame]:
    """对没有「班次」列的 sheet 新增一列，默认值为 default_shift。"""
    result = {}
    for sheet_name, df in sheets.items():
        if "班次" not in df.columns:
            result[sheet_name] = df.assign(班次=default_shift)
            logger.info(f"Sheet '{sheet_name}' 缺少班次列，已新增默认值: {default_shift}")
        else:
            result[sheet_name] = df
    return result


def _aggregate_production_data(
    production_sheets: dict[str, pd.DataFrame],
) -> pd.DataFrame | None:
    """
    将生产数据的「生产数据」sheet 按矿卡/挖机分别聚合，再 concat。
    要求台账匹配已完成（标准设备名称列已存在）。
    
    Returns:
        聚合后的 DataFrame，或 None（无数据时）
    """
    prod_df = production_sheets.get("生产数据")
    if prod_df is None or prod_df.empty:
        logger.warning("生产数据 sheet 不存在或为空，跳过聚合")
        return None

    required_cols = {"日期", "班次", "矿石类型", "产量", "运次"}
    missing_cols = required_cols - set(prod_df.columns)
    if missing_cols:
        logger.error(f"生产数据缺少必要列: {missing_cols}")
        return None

    df = prod_df.copy()

    # ── df1: 按矿卡聚合 ──
    truck_name_col = "标准设备名称（矿卡）"
    if truck_name_col not in df.columns:
        # 回退到原始列
        truck_name_col = "矿卡名称"
        if truck_name_col not in df.columns:
            logger.warning("生产数据缺少矿卡名称列，跳过矿卡聚合")
            df1 = pd.DataFrame()
        else:
            df1 = pd.DataFrame()
    
    if truck_name_col in df.columns:
        # pivot: 矿石类型 → 列，值 = 产量之和
        truck_group_keys = ["日期", "班次", truck_name_col]
        # 先聚合产量
        pivot_df = df.pivot_table(
            index=truck_group_keys,
            columns="矿石类型",
            values="产量",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        # 聚合运次
        trips_df = df.groupby(truck_group_keys, sort=False)["运次"].sum().reset_index()
        # 合并
        df1 = pivot_df.merge(trips_df, on=truck_group_keys, how="left")
        # 统一列名
        df1 = df1.rename(columns={truck_name_col: "标准设备名称"})
        logger.info(f"矿卡聚合完成: {len(df1)} 行")

    # ── df2: 按挖机聚合 ──
    excavator_name_col = "标准设备名称（挖机）"
    if excavator_name_col not in df.columns:
        excavator_name_col = "挖机名称"
    
    df2 = pd.DataFrame()
    if excavator_name_col in df.columns:
        excavator_group_keys = ["日期", "班次", excavator_name_col]
        pivot_df2 = df.pivot_table(
            index=excavator_group_keys,
            columns="矿石类型",
            values="产量",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        trips_df2 = df.groupby(excavator_group_keys, sort=False)["运次"].sum().reset_index()
        df2 = pivot_df2.merge(trips_df2, on=excavator_group_keys, how="left")
        df2 = df2.rename(columns={excavator_name_col: "标准设备名称"})
        logger.info(f"挖机聚合完成: {len(df2)} 行")

    # ── concat ──
    if df1.empty and df2.empty:
        return None
    if df1.empty:
        return df2
    if df2.empty:
        return df1

    result = pd.concat([df1, df2], ignore_index=True)
    logger.info(f"生产数据聚合完成: {len(result)} 行（矿卡 {len(df1)} + 挖机 {len(df2)}）")
    return result



def _aggregate_fuel_data(
    fuel_sheets: dict[str, pd.DataFrame],
) -> pd.DataFrame | None:
    """
    将燃油数据的「油耗信息」sheet 按 (日期, 班次, 标准设备名称) 聚合。
    油品消耗求和，设备名称/设备编号取第一个值。
    
    Returns:
        聚合后的 DataFrame，或 None
    """
    fuel_df = fuel_sheets.get("油耗信息")
    if fuel_df is None or fuel_df.empty:
        logger.warning("油耗信息 sheet 不存在或为空，跳过聚合")
        return None

    if "标准设备名称" not in fuel_df.columns:
        logger.warning("油耗信息缺少标准设备名称列，跳过聚合")
        return None

    group_keys = ["日期", "班次", "标准设备名称"]
    missing = [k for k in group_keys if k not in fuel_df.columns]
    if missing:
        logger.warning(f"油耗信息缺少聚合 key: {missing}")
        return None

    df = fuel_df.copy()
    # 删除内部排序列
    if "shift_rank" in df.columns:
        df = df.drop(columns=["shift_rank"])

    # 构建聚合规则
    agg_dict = {}
    # 油品消耗求和
    if "油品消耗" in df.columns:
        agg_dict["油品消耗"] = "sum"
    # 设备名称/编号取第一个
    if "设备名称" in df.columns:
        agg_dict["设备名称"] = "first"
    if "设备编号" in df.columns:
        agg_dict["设备编号"] = "first"

    if not agg_dict:
        logger.warning("油耗信息无可聚合字段")
        return None

    result = df.groupby(group_keys, sort=False).agg(agg_dict).reset_index()
    logger.info(f"油耗信息聚合完成: {len(result)} 行（原 {len(df)} 行）")
    return result


# 各模块的语义化后缀
_MODULE_SUFFIXES = {
    "fuel": "燃油",
    "electrical": "电力",
    "production": "生产",
    "worktime": "工时",
}


# 固定列顺序：这些列排在最前面
_PRIORITY_COLS = ["日期", "班次", "标准设备名称", "标准设备编号", "标准公司名称"]


def _reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将优先列排在最前，其余列保持原序。"""
    priority = [c for c in _PRIORITY_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in priority]
    return df[priority + rest]


# 左合并时需要从后续 sheet 中删除的重复列（只保留基准表的一份）
_LEDGER_DUPLICATE_COLS = ["标准设备编号", "标准公司名称"]


def _left_merge(
    base: pd.DataFrame,
    right: pd.DataFrame,
    right_label: str,
    join_keys: list[str],
) -> pd.DataFrame:
    """
    将 right 按 join_keys 左合并到 base 上。
    列名冲突时使用语义化后缀，标准设备编号/标准公司名称只保留一份。
    """
    # 从 right 中删除基准表已有的 ledger 重复列
    right = right.copy()
    for col in _LEDGER_DUPLICATE_COLS:
        if col in right.columns and col in base.columns:
            right = right.drop(columns=[col])

    # 显式验证 join keys 存在
    for k in join_keys:
        if k not in base.columns:
            raise KeyError(f"基准表缺少 join key '{k}'")
        if k not in right.columns:
            raise KeyError(f"表 '{right_label}' 缺少 join key '{k}'")

    # 找出冲突列（排除 join keys 和 ledger 重复列，这些已处理过）
    base_cols = set(base.columns)
    skip_cols = set(join_keys) | set(_LEDGER_DUPLICATE_COLS)
    right_non_key_cols = [c for c in right.columns if c not in skip_cols]
    conflicts = [c for c in right_non_key_cols if c in base_cols]

    suffix = f"_{right_label}"
    if conflicts:
        rename_map = {c: f"{c}{suffix}" for c in conflicts}
        right = right.rename(columns=rename_map)
        logger.info(f"左合并 '{right_label}': 列名冲突已处理 {list(rename_map.values())}")

    merged = base.merge(right, on=join_keys, how="left", suffixes=("", suffix))
    logger.info(f"左合并 '{right_label}' 完成: {len(merged)} 行")
    return merged


def _table_merge_and_write(
    all_results: dict[str, dict[str, pd.DataFrame]],
    folder_path: str,
    year: int,
    month: int,
    table_merge_config: dict,
    progress_cb=None,
    cancel_event=None,
):
    """
    执行表内合并流程：聚合生产数据 → 左合并所有模块 → 输出单 sheet Excel。
    """
    _emit_progress(progress_cb, {"stage": "writing", "percent": 1/_MERGE_STAGE_COUNT, "current": 1, "total": _MERGE_STAGE_COUNT, "detail": "表内合并：开始聚合"})
    if _check_cancel(cancel_event):
        _emit_progress(progress_cb, {"stage": "cancelled", "percent": 1/_MERGE_STAGE_COUNT, "current": 1, "total": _MERGE_STAGE_COUNT, "detail": "用户取消，已完成部分输出"})
        return
    base_type = table_merge_config.get("base_type", "fuel")
    join_keys = ["日期", "班次", "标准设备名称"]
    default_shift = config_loader.get_default_shift() if hasattr(config_loader, 'get_default_shift') else "Night"

    # 1. 对所有 sheets 添加默认班次（如果没有）
    for module_type in all_results:
        all_results[module_type] = _add_default_shift(all_results[module_type], default_shift)

    # 2. 聚合生产数据
    production_agg = None
    if "production" in all_results:
        production_agg = _aggregate_production_data(all_results["production"])

    # 3. 聚合油耗信息
    fuel_agg = None
    if "fuel" in all_results:
        fuel_agg = _aggregate_fuel_data(all_results["fuel"])

    # 4. 确保生产数据聚合结果有标准设备名称列
    if production_agg is not None and "标准设备名称" not in production_agg.columns:
        # 尝试从矿卡/挖机列回退
        for fallback in ["矿卡名称", "挖机名称", "设备名称"]:
            if fallback in production_agg.columns:
                production_agg = production_agg.rename(columns={fallback: "标准设备名称"})
                logger.info(f"聚合数据回退列名 '{fallback}' -> '标准设备名称'")
                break
        if "标准设备名称" not in production_agg.columns:
            logger.warning(f"聚合数据缺少标准设备名称列，列: {list(production_agg.columns)}")

    # 4. 确定基准表
    if base_type == "fuel":
        base_df = fuel_agg
        base_label = "油耗信息（聚合）"
    else:
        base_sheets = all_results.get("worktime", {})
        base_df = base_sheets.get("工时数据")
        base_label = "工时数据"

    if base_df is None or base_df.empty:
        logger.error(f"基准表 '{base_label}' 不存在或为空，无法进行表内合并")
        return

    merged = base_df.copy()
    logger.info(f"表内合并基准表: {base_label} ({len(merged)} 行)")

    # 5. 按顺序左合并其他 sheet
    if base_type == "fuel":
        # 顺序: 设备信息 → 工时 → 电力 → 运行数据 → 产量数据
        merge_queue = []
        # 设备信息
        if "fuel" in all_results and "设备信息" in all_results["fuel"]:
            merge_queue.append(("设备信息", all_results["fuel"]["设备信息"]))
        # 工时数据
        if "worktime" in all_results and "工时数据" in all_results["worktime"]:
            merge_queue.append(("工时数据", all_results["worktime"]["工时数据"]))
        # 油耗信息已在基准表中，无需重复合并
    else:
        # base_type == "worktime"
        # 顺序: 设备信息 → 油耗信息 → 电力 → 运行数据 → 产量数据
        merge_queue = []
        if "fuel" in all_results and "设备信息" in all_results["fuel"]:
            merge_queue.append(("设备信息", all_results["fuel"]["设备信息"]))
        if fuel_agg is not None:
            merge_queue.append(("油耗信息", fuel_agg))

    # 电力数据
    if "electrical" in all_results and "电力消耗" in all_results["electrical"]:
        merge_queue.append(("电力消耗", all_results["electrical"]["电力消耗"]))

    # 运行数据
    if "production" in all_results and "运行数据" in all_results["production"]:
        merge_queue.append(("运行数据", all_results["production"]["运行数据"]))

    # 产量数据（聚合后）
    if production_agg is not None:
        merge_queue.append(("产量数据", production_agg))

    # 执行左合并
    for label, right_df in merge_queue:
        if right_df is None or right_df.empty:
            logger.warning(f"跳过空表: {label}")
            continue
        # 确保 join_keys 同时存在于 base 和 right
        available_keys = [k for k in join_keys if k in merged.columns and k in right_df.columns]
        missing_in_right = [k for k in join_keys if k not in right_df.columns]
        missing_in_base = [k for k in join_keys if k not in merged.columns]
        if missing_in_right:
            logger.info(f"表 '{label}' 缺少 join key {missing_in_right}，将使用 {available_keys}")
        if missing_in_base:
            logger.warning(f"基准表缺少 join key {missing_in_base}，将使用 {available_keys}")
        if not available_keys:
            logger.warning(f"表 '{label}' 无可用 join key，跳过合并")
            continue
        try:
            merged = _left_merge(merged, right_df, label, available_keys)
        except Exception as e:
            logger.error(f"合并 '{label}' 失败: {e}")

    # 6. 列排序 & 输出
    _emit_progress(progress_cb, {"stage": "writing", "percent": 2/_MERGE_STAGE_COUNT, "current": 2, "total": _MERGE_STAGE_COUNT, "detail": "表内合并：开始写入"})
    if _check_cancel(cancel_event):
        _emit_progress(progress_cb, {"stage": "cancelled", "percent": 2/_MERGE_STAGE_COUNT, "current": 2, "total": _MERGE_STAGE_COUNT, "detail": "用户取消，已完成部分输出"})
        return
    merged = _reorder_columns(merged)
    merged = dedup_dataframe(merged, "表内合并")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(folder_path, f"表内合并结果_{year}{month:02d}_{timestamp}.xlsx")
    merged.to_excel(output_file, index=False, sheet_name="合并数据")
    logger.info(f"表内合并完成: {output_file} ({len(merged)} 行)")
    _emit_progress(progress_cb, {"stage": "finished", "percent": 1.0, "current": _MERGE_STAGE_COUNT, "total": _MERGE_STAGE_COUNT, "detail": "表内合并：写入完成"})

# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _write_merged(
    all_results: dict[str, dict[str, pd.DataFrame]],
    folder_path: str,
    year: int,
    month: int,
    progress_cb=None,
    cancel_event=None,
):
    """将所有模块的结果合并到单个 Excel 文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(folder_path, f"批量处理结果_{year}{month:02d}_{timestamp}.xlsx")

    total = sum(len(sheets) for sheets in all_results.values())
    current = 0
    _emit_progress(progress_cb, {"stage": "writing", "percent": 0.0, "current": 0, "total": total, "detail": "开始合并输出"})
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for module_type, sheets in all_results.items():
            prefix = MODULE_PREFIXES.get(module_type, f"{module_type}_")
            for sheet_name, df in sheets.items():
                if _check_cancel(cancel_event):
                    _emit_progress(progress_cb, {"stage": "cancelled", "percent": max(current / total if total else 0.0, 0.0), "current": current, "total": total, "detail": "用户取消，已完成部分输出"})
                    return
                prefixed_name = f"{prefix}{sheet_name}"
                if len(prefixed_name) > MAX_SHEET_NAME_LENGTH:
                    prefixed_name = prefixed_name[:MAX_SHEET_NAME_LENGTH]
                df = dedup_dataframe(df, prefixed_name)
                df.to_excel(writer, sheet_name=prefixed_name, index=False)
                current += 1
                logger.info(f"写入 Sheet: {prefixed_name} ({len(df)} 行)")
                _emit_progress(progress_cb, {"stage": "writing", "percent": current / total if total else 1.0, "current": current, "total": total, "detail": f"写入 Sheet: {prefixed_name}"})

    logger.info(f"合并输出完成: {output_file}")
    _emit_progress(progress_cb, {"stage": "finished", "percent": 1.0, "current": total, "total": total, "detail": "合并输出完成"})


def _write_separate(
    all_results: dict[str, dict[str, pd.DataFrame]],
    folder_path: str,
    year: int,
    month: int,
    progress_cb=None,
    cancel_event=None,
):
    """将各模块结果分别输出为独立 Excel 文件"""
    total = sum(1 for sheets in all_results.values() if sheets)
    current = 0
    _emit_progress(progress_cb, {"stage": "writing", "percent": 0.0, "current": 0, "total": total, "detail": "开始分开输出"})
    for module_type, sheets in all_results.items():
        if not sheets:
            continue
        if _check_cancel(cancel_event):
            _emit_progress(progress_cb, {"stage": "cancelled", "percent": max(current / total if total else 0.0, 0.0), "current": current, "total": total, "detail": "用户取消，已完成部分输出"})
            return
        output_file = os.path.join(folder_path, get_output_filename(module_type, year, month) or f"{module_type}.xlsx")
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df = dedup_dataframe(df, sheet_name)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.info(f"写入: {output_file} / {sheet_name} ({len(df)} 行)")
        current += 1
        logger.info(f"单独输出完成: {output_file}")
        _emit_progress(progress_cb, {"stage": "writing", "percent": current / total if total else 1.0, "current": current, "total": total, "detail": f"已输出 {os.path.basename(output_file)}"})
    _emit_progress(progress_cb, {"stage": "finished", "percent": 1.0, "current": total, "total": total, "detail": "分开输出完成"})
