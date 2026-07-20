"""
多文件夹工时报表处理器。

处理按日期分文件夹存放的多日工时报表，目录结构假设如下：
    base_dir/
    ├── 01_xxx/          ← 文件夹名以数字开头 → 日期=1
    │   └── xxxTsag.xlsx ← 文件名含 "Tsag"/"工作效率"/"Цаг"
    ├── 02_xxx/
    │   └── yyy.xlsx
    └── ...

与 excel_worktime.py 共享后续处理逻辑（分割班次、清洗、排序、表头映射、去重）。
"""

import os
import re

import pandas as pd

from func.logger import get_logger
from func.string_utils import clean_string
from func.excel_utils import (
    apply_header_mapping,
    adjust_index_for_hidden,
    clean_split_dataframe,
    dedup_dataframe,
    filter_hidden_from_df,
    get_hidden_indices,
    open_workbook,
    sort_by_date_shift,
    split_day_night_shifts,
    strip_date_column,
)
from func.anomaly import detect_and_filter
from func.anomaly.rules import AnomalyConfig
from func import config_loader

logger = get_logger(__name__)

# 文件名关键字：文件名包含任一关键字才处理
_FILE_KEYWORDS = ("Tsag", "工作效率", "Цаг")


def process_directory(
    base_dir: str,
    year: int,
    month: int,
    output_file: str | None = None,
    return_sheets: bool = False,
    header_mapping: dict | None = None,
    skip_hidden: bool = False,
    skip_hidden_rows: bool = False,
    skip_hidden_cols: bool = False,
    anomaly_config=None,
) -> dict | None:
    """遍历按日期分文件夹的工时报表目录，合并为单一 DataFrame。

    Args:
        base_dir: 包含按日期命名子文件夹的根目录。
        year: 目标年份。
        month: 目标月份。
        output_file: 输出文件路径，None 时自动生成。
        return_sheets: 若为 True，返回 {"工时数据": DataFrame} 字典而非写入文件。
        header_mapping: 表头映射配置，None 时不映射。
        skip_hidden: 向后兼容，True 时等价于 skip_hidden_rows=True, skip_hidden_cols=True。
        skip_hidden_rows: 若为 True，跳过 Excel 中的隐藏行。
        skip_hidden_cols: 若为 True，跳过 Excel 中的隐藏列。

    Returns:
        return_sheets=True 且有数据时返回 sheets 字典；否则返回 None。

    Raises:
        FileNotFoundError: base_dir 不存在。
        ValueError: 未提取到任何有效数据。
    """
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"找不到目录 '{base_dir}'")

    # 向后兼容
    if skip_hidden:
        skip_hidden_rows = True
        skip_hidden_cols = True
    need_hidden = skip_hidden_rows or skip_hidden_cols

    all_data: list[pd.DataFrame] = []
    success_count = 0
    processed_days: list[int] = []

    logger.info(f"开始遍历目录: {base_dir}")

    for item in sorted(os.listdir(base_dir)):
        folder_path = os.path.join(base_dir, item)

        if not os.path.isdir(folder_path):
            continue

        # 文件夹名以数字开头 → 提取日期
        match = re.match(r"^(\d+)", item)
        if not match:
            continue

        target_day = int(match.group(1))

        # 遍历该文件夹下的 Excel 文件
        for file in sorted(os.listdir(folder_path)):
            if file.startswith("~$"):
                continue
            if not (file.endswith(".xlsx") or file.endswith(".xls")):
                continue
            if not any(kw in file for kw in _FILE_KEYWORDS):
                continue

            excel_path = os.path.join(folder_path, file)
            logger.info(f"正在处理文件: {os.path.join(item, file)}")

            try:
                xls = pd.ExcelFile(excel_path)
            except Exception as e:
                logger.error(f"读取文件失败 '{excel_path}': {e}")
                continue

            with xls:
                # 匹配 Sheet：优先找名称为 target_day 的 Sheet，否则单 Sheet 自动选用
                target_sheet = _find_target_sheet(xls, target_day)
                if not target_sheet:
                    continue

                df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None)

                # 隐藏行列过滤
                h_rows: set = set()
                if need_hidden:
                    h_rows, h_cols = get_hidden_indices(excel_path, target_sheet)
                    df_raw = filter_hidden_from_df(
                        df_raw,
                        h_rows if skip_hidden_rows else set(),
                        h_cols if skip_hidden_cols else set(),
                    )

                df_processed = _extract_one_day(
                    df_raw, year, month, target_day, h_rows,
                )

                if df_processed is not None and not df_processed.empty:
                    all_data.append(df_processed)
                    success_count += 1
                    processed_days.append(target_day)
                    logger.info(f"成功提取日期 {target_day}，共 {len(df_processed)} 行")
                else:
                    logger.warning(f"日期 {target_day} 的 Sheet 「{target_sheet}」数据提取为空")

    # 后处理
    return _finalize(
        all_data, success_count, processed_days,
        base_dir, year, month,
        header_mapping, output_file, return_sheets,
        anomaly_config,
    )


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _find_target_sheet(xls: pd.ExcelFile, target_day: int) -> str | None:
    """在 Excel 中查找与 target_day 匹配的 Sheet 名。"""
    for sheet in xls.sheet_names:
        if clean_string(sheet).isdigit() and int(clean_string(sheet)) == target_day:
            return sheet
    # 单 Sheet 文件自动选用
    if len(xls.sheet_names) == 1:
        name = xls.sheet_names[0]
        logger.warning(f"文件中只有一个 Sheet，已自动选择「{name}」")
        return name
    logger.warning(f"未找到与日期 {target_day} 匹配的 Sheet，已跳过")
    return None


def _extract_one_day(
    df_raw: pd.DataFrame,
    year: int,
    month: int,
    day: int,
    h_rows: set[int],
) -> pd.DataFrame | None:
    """从单个 DataFrame 中提取白班和夜班数据。"""
    if len(df_raw) < 2:
        return None

    date_str = f"{year}-{month:02d}-{day:02d}"

    # 隐藏行偏移修正
    if h_rows:
        adj_header = adjust_index_for_hidden(1, h_rows, one_based=True)
        adj_data = adjust_index_for_hidden(2, h_rows, one_based=True)
        combined = split_day_night_shifts(
            df_raw, header_row_index=adj_header, data_start_index=adj_data,
        )
    else:
        combined = split_day_night_shifts(df_raw)

    if combined is None or combined.empty:
        return None

    combined.insert(0, "日期", date_str)
    combined = clean_split_dataframe(combined)
    return combined


def _finalize(
    all_data: list[pd.DataFrame],
    success_count: int,
    processed_days: list[int],
    base_dir: str,
    year: int,
    month: int,
    header_mapping: dict | None,
    output_file: str | None,
    return_sheets: bool,
    anomaly_config=None,
) -> dict | None:
    """合并、排序、映射、去重、输出。"""
    if not all_data:
        logger.warning("未提取到任何有效数据。请检查文件夹结构或 Excel 内容。")
        if return_sheets:
            return None
        return None

    logger.info(f"成功处理 {success_count} 个日期的数据")
    logger.info(f"包含的日期: {sorted(set(processed_days))}")

    final_df = pd.concat(all_data, axis=0, ignore_index=True)

    # 排序与列格式化
    final_df = strip_date_column(final_df, date_format="%Y-%m-%d")
    final_df = sort_by_date_shift(final_df)

    # 日期、班次排在最前
    other_cols = [c for c in final_df.columns if c not in ("日期", "班次")]
    final_df = final_df[["日期", "班次"] + other_cols]

    # 全局剔除混入的重复表头
    final_df = _remove_header_rows(final_df, other_cols)

    # 表头映射
    if header_mapping and header_mapping.get("entries"):
        final_df = apply_header_mapping(final_df, header_mapping)

    # 去重
    final_df = dedup_dataframe(final_df, "多文件工时合并")

    # 异常值检测
    if anomaly_config is None:
        anomaly_config = AnomalyConfig.from_config(config_loader.get_anomaly_detection_config())
    if anomaly_config.enabled:
        output_dir = output_file and os.path.dirname(output_file) or base_dir
        final_df, _ = detect_and_filter(
            final_df, "worktime", anomaly_config, output_dir=output_dir)

    if return_sheets:
        return {"工时数据": final_df}

    if output_file is None:
        output_file = os.path.join(base_dir, f"{year}{month:02d}_多文件合并_工作效率表.xlsx")

    from func.excel_formatter import write_formatted_excel

    write_formatted_excel(output_file, {"工时数据": final_df})
    logger.info(f"数据处理完成，已保存至: {output_file}")
    return None


def _remove_header_rows(df: pd.DataFrame, check_cols: list[str]) -> pd.DataFrame:
    """剔除数据中混入的重复表头行。"""
    if not check_cols:
        return df

    cols_to_check = check_cols[:3]
    is_header = pd.Series([True] * len(df), index=df.index)
    for col in cols_to_check:
        is_header = is_header & (df[col].apply(clean_string) == clean_string(col))

    removed = is_header.sum()
    if removed > 0:
        logger.info(f"自动清理了 {removed} 行混入数据的重复表头")
    return df[~is_header]
