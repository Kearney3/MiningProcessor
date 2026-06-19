"""
Excel 文件处理器适配函数。

将各类 Excel 文件（柴油、电力、产量、工时）解析为标准化行数据。
也包含 Excel 读取、文件发现、工时表头映射。
"""
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from func.logger import get_logger
from func.sync.row_helpers import (
    _apply_defaults,
    _apply_ledger_matching,
    _apply_oil_ledger_matching,
    _build_field_mappings,
    _filter_by_date_range,
    _map_row_to_db_columns,
    _resolve_fks_for_db,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DataFrame → 行列表转换
# ---------------------------------------------------------------------------


def _df_to_mapped_rows(
    df: "pd.DataFrame",
    column_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """将 DataFrame 按映射配置转换为行字典列表。

    跳过 __SKIP__ 映射列和 NaN/NaT 值，Timestamp 转为 YYYY-MM-DD 字符串。

    Args:
        df: 源 DataFrame。
        column_mapping: {源列名: 目标字段名} 映射。

    Returns:
        映射后的行数据列表。
    """
    if df is None or df.empty:
        return []

    _SKIP = "__SKIP__"
    source_cols = [
        c for c in df.columns
        if c in column_mapping and column_mapping[c] != _SKIP
    ]
    if not source_cols:
        return []

    rows = []
    for _, row in df.iterrows():
        mapped = {}
        for src_col in source_cols:
            target_field = column_mapping[src_col]
            value = row[src_col]
            if pd.isna(value):
                continue
            if isinstance(value, (pd.Timestamp, datetime)):
                value = value.strftime("%Y-%m-%d")
            elif isinstance(value, date):
                value = value.isoformat()
            mapped[target_field] = value
        if mapped:
            rows.append(mapped)
    return rows


def _get_df_to_mapped_rows():
    """Late-binding lookup for _df_to_mapped_rows (supports unittest.mock.patch on the shim module)."""
    mod = sys.modules.get("func.sync_to_minebase")
    if mod and hasattr(mod, "_df_to_mapped_rows"):
        return mod._df_to_mapped_rows
    return _df_to_mapped_rows


# ---------------------------------------------------------------------------
# 处理器适配函数
# ---------------------------------------------------------------------------


def _process_fuel_file(
    file_path: Path,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """通过柴油处理器解析文件，返回同步行列表。"""
    try:
        from func.excel_fuel import process_diesel_data

        sheets = process_diesel_data(str(file_path), target_year=year, return_sheets=True)
        if not sheets:
            return []
        df = sheets.get("油耗信息")
        if df is None:
            return []

        mapping = {
            "日期": "date",
            "班次": "shiftType",
            "设备名称": "equipmentName",
            "设备编号": "equipmentCode",
            "油品种类": "fuelName",
            "油品消耗": "consumption",
        }
        rows = _get_df_to_mapped_rows()(df, mapping)
        logger.info("fuel 处理器: %s → %d 行", file_path.name, len(rows))
        return rows
    except Exception as e:
        logger.error("fuel 处理器失败: %s — %s", file_path, e)
        return []


def _process_electrical_file(
    file_path: Path,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """通过电力处理器解析文件，返回同步行列表。"""
    try:
        from func.excel_electrical import parse_excel_data

        sheets = parse_excel_data(
            str(file_path),
            target_year=year,
            return_sheets=True,
            add_shift_column=True,
            default_shift="Night",
        )
        if not sheets:
            return []
        df = sheets.get("电力消耗")
        if df is None:
            return []

        mapping = {
            "日期": "date",
            "班次": "shiftType",
            "设备名称": "equipmentName",
            "电力消耗": "consumption",
        }
        rows = _get_df_to_mapped_rows()(df, mapping)
        logger.info("electrical 处理器: %s → %d 行", file_path.name, len(rows))
        return rows
    except Exception as e:
        logger.error("electrical 处理器失败: %s — %s", file_path, e)
        return []


def _process_production_file(
    file_path: Path,
) -> dict[str, list[dict[str, Any]]]:
    """通过产量处理器解析文件，返回 {"production": [...], "operation": [...]}。"""
    try:
        from func.excel_production_enhanced import MiningDataProcessor

        processor = MiningDataProcessor()
        running_df, production_df = processor.process_single_file(str(file_path))

        prod_map = {
            "日期": "date",
            "班次": "shiftType",
            "矿卡名称": "truckName",
            "挖机名称": "excavatorName",
            "矿石类型": "materialTypeName",
            "运次": "tripCount",
            "产量": "production",
        }
        ops_map = {
            "日期": "date",
            "班次": "shiftType",
            "设备名称": "equipmentName",
            "公司": "company",
            "小时数仪表开始": "engineHoursStart",
            "小时数仪表结束": "engineHoursEnd",
            "运行小时数": "runningHours",
            "公里数仪表开始": "milemeterStart",
            "公里数仪表结束": "milemeterEnd",
            "运行里程": "mileage",
            "趟数": "tripCount",
            "备注": "remark",
        }
        _map = _get_df_to_mapped_rows()
        prod_rows = _map(production_df, prod_map)
        ops_rows = _map(running_df, ops_map)
        logger.info(
            "production 处理器: %s → production=%d, operation=%d",
            file_path.name, len(prod_rows), len(ops_rows),
        )
        return {"production": prod_rows, "operation": ops_rows}
    except Exception as e:
        logger.error("production 处理器失败: %s — %s", file_path, e)
        return {"production": [], "operation": []}


def _apply_header_mapping(
    df: "pd.DataFrame",
    header_mapping: dict[str, Any],
) -> "pd.DataFrame":
    """按工时表头映射配置重命名 DataFrame 列。

    Args:
        df: 原始 DataFrame。
        header_mapping: worktime_header_mapping 配置（含 mode/fuzzy/entries）。

    Returns:
        列重命名后的新 DataFrame。
    """
    if not header_mapping or not header_mapping.get("entries"):
        return df

    mode = header_mapping.get("mode", "position")
    entries = header_mapping.get("entries", [])

    rename_map = {}
    for entry in entries:
        idx = entry.get("index")
        new_name = entry.get("new", "")
        if not new_name:
            continue

        if mode == "position" and idx is not None:
            col_idx = int(idx) - 1  # 配置中 index 从 1 开始
            if 0 <= col_idx < len(df.columns):
                rename_map[df.columns[col_idx]] = new_name
        elif mode == "name":
            original = entry.get("original", "")
            if original and original in df.columns:
                rename_map[original] = new_name

    if rename_map:
        df = df.rename(columns=rename_map)
        logger.info("工时表头映射: 重命名 %d 列", len(rename_map))
    return df


def _process_work_efficiency_file(
    file_path: Path,
    year: int | None = None,
    month: int | None = None,
    apply_header_mapping: bool = True,
) -> list[dict[str, Any]]:
    """通过工时处理器解析文件，返回同步行列表。

    已处理的输出文件（含标准化 sheet 结构）直接读取并映射列；
    如需从原始文件重新处理，可扩展为调用 process_excel_data。
    """
    try:
        from func.config_loader import get_minebase_column_mapping
        mapping = get_minebase_column_mapping().get("work_efficiency", {})
        if not mapping:
            logger.warning("work_efficiency 映射配置为空")
            return []

        # 尝试用工时处理器（需要 year/month）
        if year and month:
            from func.excel_worktime import process_excel_data

            hdr_map = None
            if apply_header_mapping:
                from func.config_loader import get_worktime_header_mapping
                hdr_map = get_worktime_header_mapping()
                if hdr_map and not hdr_map.get("entries"):
                    hdr_map = None

            sheets = process_excel_data(
                str(file_path), year, month,
                return_sheets=True,
                header_mapping=hdr_map,
            )
            if sheets:
                df = sheets.get("工时数据")
                if df is not None and not df.empty:
                    # 如果处理器未应用表头映射，此处补充
                    if apply_header_mapping and hdr_map and hdr_map.get("entries"):
                        df = _apply_header_mapping(df, hdr_map)
                    rows = _get_df_to_mapped_rows()(df, mapping)
                    logger.info("work_efficiency 处理器: %s → %d 行", file_path.name, len(rows))
                    return rows

        # 回退：直接读取输出文件（已是标准格式）
        df = pd.read_excel(file_path, sheet_name=0)
        if apply_header_mapping:
            from func.config_loader import get_worktime_header_mapping
            hdr_map = get_worktime_header_mapping()
            if hdr_map and hdr_map.get("entries"):
                df = _apply_header_mapping(df, hdr_map)
        rows = _get_df_to_mapped_rows()(df, mapping)
        logger.info("work_efficiency 直接读取: %s → %d 行", file_path.name, len(rows))
        return rows
    except Exception as e:
        logger.error("work_efficiency 处理器失败: %s — %s", file_path, e)
        return []


# ---------------------------------------------------------------------------
# Excel 读取与列映射
# ---------------------------------------------------------------------------


def read_and_map_excel(
    file_path: Path,
    sheet_name: str | int | None,
    column_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """读取 Excel 文件并按映射配置转换列名。

    Args:
        file_path: Excel 文件路径。
        sheet_name: sheet 名称或索引，None 读第一个。
        column_mapping: {源列名: 目标字段名} 映射。

    Returns:
        映射后的行数据列表。
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        # 当 sheet_name=None 时，pd.read_excel 返回 dict；取第一个 sheet
        if isinstance(df, dict):
            df = list(df.values())[0]
    except Exception as e:
        logger.error("读取 Excel 失败: %s — %s", file_path, e)
        return []

    if df.empty:
        logger.info("Excel 文件为空: %s", file_path)
        return []

    # 只保留映射中存在的列，排除标记为 __SKIP__ 的列
    _SKIP = "__SKIP__"
    source_cols = [c for c in df.columns if c in column_mapping and column_mapping[c] != _SKIP]
    if not source_cols:
        logger.warning("Excel 中没有匹配到映射列: %s (列: %s)", file_path, list(df.columns))
        return []

    rows = []
    for _, row in df.iterrows():
        mapped = {}
        for src_col in source_cols:
            target_field = column_mapping[src_col]
            value = row[src_col]
            # 处理 NaN / NaT
            if pd.isna(value):
                continue
            # 日期类型转换
            if isinstance(value, (pd.Timestamp, datetime)):
                value = value.strftime("%Y-%m-%d")
            elif isinstance(value, date):
                value = value.isoformat()
            mapped[target_field] = value
        if mapped:
            rows.append(mapped)

    logger.info("读取 %s: %d 行, 匹配列 %d/%d", file_path.name, len(rows), len(source_cols), len(df.columns))
    return rows


# ---------------------------------------------------------------------------
# 文件发现
# ---------------------------------------------------------------------------


def discover_files(
    input_dir: Path,
    year: int | None = None,
    month: int | None = None,
    keywords: dict[str, list[str]] | None = None,
) -> dict[str, list[Path]]:
    """在输入目录中查找各数据类型对应的 Excel 文件。

    优先使用 DATA_TYPE_REGISTRY 中的 file_pattern 精确匹配已处理的输出文件，
    回退到关键字匹配（与 excel_batch.scan_files 一致）。
    work_efficiency 类型支持 year/month 构造精确文件名模式。

    Args:
        input_dir: 输入目录。
        year: 年份（用于 work_efficiency 文件名匹配）。
        month: 月份（用于 work_efficiency 文件名匹配）。
        keywords: {模块类型: [关键字]}，默认从配置读取。

    Returns:
        {data_type: [file_path, ...]} 字典，每个类型可对应多个文件。
    """
    from func.config_loader import get_file_keywords
    from func.sync.constants import DATA_TYPE_REGISTRY

    if keywords is None:
        keywords = get_file_keywords()

    # 列出目录中所有 Excel 文件（排除临时文件）
    excel_files = sorted(
        f for f in input_dir.iterdir()
        if f.suffix.lower() in (".xlsx", ".xls") and not f.name.startswith("~$")
    )

    found: dict[str, list[Path]] = {}

    # 1. DATA_TYPE_REGISTRY.file_pattern 精确匹配已处理输出文件（最高优先级）
    for data_type, info in DATA_TYPE_REGISTRY.items():
        if data_type in found:
            continue
        # work_efficiency: 有 year/month 时延迟到 step 2 用更精确的模式匹配
        if data_type == "work_efficiency" and year and month:
            continue
        pattern = info["file_pattern"]
        if "*" in pattern:
            matches = sorted(input_dir.glob(pattern))
        else:
            matches = list(input_dir.glob(pattern))
        if matches:
            found[data_type] = [matches[0]]
            logger.info("精确匹配: %s → %s", data_type, matches[0].name)

    # 2. work_efficiency 专用 glob: 按 year/month 构造精确文件名模式（补充）
    if "work_efficiency" not in found and year and month:
        pattern = f"*{year}{month:02d}*工作效率表*.xlsx"
        matches = sorted(input_dir.glob(pattern))
        if matches:
            found["work_efficiency"] = [matches[0]]
            logger.info("Glob 匹配: work_efficiency → %s", matches[0].name)
    elif "work_efficiency" not in found:
        pattern = "*工作效率表*.xlsx"
        matches = sorted(input_dir.glob(pattern))
        if matches:
            found["work_efficiency"] = [matches[0]]
            logger.info("Glob 匹配: work_efficiency → %s", matches[0].name)

    # 3. 关键字回退: 仅对尚未找到的类型使用关键字匹配（收集所有匹配文件）
    kw_type_map = {
        "fuel": "fuel",
        "electrical": "electrical",
        "production": ["production", "operation"],
        "worktime": "work_efficiency",
    }

    for module_type, sync_types in kw_type_map.items():
        # 检查该模块对应的所有数据类型是否已找到
        types_to_check = sync_types if isinstance(sync_types, list) else [sync_types]
        if all(t in found for t in types_to_check):
            continue

        kw_list = keywords.get(module_type, [])
        if not kw_list:
            continue
        matched_files = [
            f for f in excel_files
            if any(k in f.name for k in kw_list)
        ]
        if not matched_files:
            continue

        if isinstance(sync_types, list):
            for st in sync_types:
                if st not in found:
                    found[st] = list(matched_files)
        else:
            found[sync_types] = list(matched_files)
        logger.info("关键字回退: %s → %s (%d 个文件)", module_type, [f.name for f in matched_files], len(matched_files))

    for dt, fp_list in found.items():
        for fp in fp_list:
            logger.info("发现文件: %s → %s", dt, fp.name)
    return found
