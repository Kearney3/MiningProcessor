import pandas as pd
import os
import argparse

# 假设 func.logger 已经正确配置
from func.logger import get_logger
from func.string_utils import clean_string
from func.excel_utils import split_day_night_shifts, clean_split_dataframe, strip_date_column, sort_by_date_shift

logger = get_logger(__name__)


def _apply_header_mapping(df: pd.DataFrame, mapping_config: dict) -> pd.DataFrame:
    """根据映射配置重命名 DataFrame 列。

    mapping_config 格式::

        {
            "mode": "position" | "name",
            "fuzzy": False,
            "entries": [{"index": int|None, "original": str, "new": str}, ...]
        }

    - position 模式: 按列索引（行号）匹配并重命名
    - name 模式:   按原始列名匹配，可选模糊匹配（rapidfuzz）
    """
    if not mapping_config or not mapping_config.get("entries"):
        return df

    mode = mapping_config.get("mode", "position")
    fuzzy = mapping_config.get("fuzzy", False)
    entries = mapping_config["entries"]
    cols = list(df.columns)
    rename_map: dict[str, str] = {}

    if mode == "position":
        for entry in entries:
            idx = entry.get("index")
            new_name = clean_string(entry.get("new"))
            if idx is None or not new_name:
                continue
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue
            # 用户界面使用 1-based 索引，内部转换为 0-based
            if 1 <= idx <= len(cols):
                idx = idx - 1
                old_name = cols[idx]
                rename_map[old_name] = new_name
    else:
        # name 模式
        orig_to_new: dict[str, str] = {}
        for entry in entries:
            orig = clean_string(entry.get("original"))
            new_name = clean_string(entry.get("new"))
            if orig and new_name:
                orig_to_new[orig] = new_name

        if fuzzy:
            try:
                from rapidfuzz import fuzz
                for col in cols:
                    col_str = clean_string(col)
                    best_score = 0
                    best_target = None
                    for orig, new_name in orig_to_new.items():
                        score = fuzz.ratio(col_str, orig)
                        if score > best_score:
                            best_score = score
                            best_target = new_name
                    if best_score >= 70 and best_target:
                        rename_map[col] = best_target
            except ImportError:
                logger.warning("rapidfuzz 未安装，回退到精确匹配")
                for col in cols:
                    col_str = clean_string(col)
                    if col_str in orig_to_new:
                        rename_map[col] = orig_to_new[col_str]
        else:
            for col in cols:
                col_str = clean_string(col)
                if col_str in orig_to_new:
                    rename_map[col] = orig_to_new[col_str]

    if rename_map:
        logger.info(f"表头映射生效（模式: {mode}），重命名 {len(rename_map)} 列: {rename_map}")
    return df.rename(columns=rename_map)


def process_excel_data(file_path, year, month, output_file=None, return_sheets=False,
                       header_mapping=None):
    """
    解析非标准结构的Excel文件并合并数据

    Args:
        file_path: 输入文件路径
        year: 目标年份
        month: 目标月份
        output_file: 输出文件路径（可选）
        return_sheets: 是否返回 sheets 字典（供批量处理用）
        header_mapping: 表头映射字典 {原始列名: 新列名}，为 None 或空时不映射
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到输入文件 '{file_path}'")

    logger.info(f"正在读取文件: {file_path} ...")
    try:
        # 读取所有的 sheet
        xls = pd.ExcelFile(file_path)
    except (FileNotFoundError, PermissionError, ValueError) as e:
        raise RuntimeError(f"读取 Excel 文件失败: {e}") from e

    all_data = []
    success_count = 0
    day_list = []

    for sheet_name in xls.sheet_names:
        # 确保sheet名称是数字（代表日期）
        if not clean_string(sheet_name).isdigit():
            logger.warning(f"跳过非日期Sheet: {sheet_name}")
            continue

        # 读取整个sheet，不设表头
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        # 1. 确定日期字符串 (YYYY-MM-DD)
        day = int(clean_string(sheet_name))
        date_str = f"{year}-{month:02d}-{day:02d}"
        day_list.append(day)

        # 2. 分割 Day/Night 班次（day_end_offset=-1 对应原 worktime 行为）
        combined_day_df = split_day_night_shifts(df_raw)

        # 插入日期列到第一列
        combined_day_df.insert(0, '日期', date_str)

        # 3. 清洗
        combined_day_df = clean_split_dataframe(combined_day_df)

        all_data.append(combined_day_df)
        success_count += 1
        logger.info(f"成功处理日期: {day}, 有效数据行数: {len(combined_day_df)}")

    # 4. 合并所有日期的数据
    if not all_data:
        logger.warning("未提取到任何有效数据。")
        return

    logger.info(f"成功处理 {success_count} 个日期数据")
    logger.info(f"成功导入的日期为: {sorted(day_list)}")

    final_df = pd.concat(all_data, axis=0, ignore_index=True)

    # 5. 排序：按日期排序, 并将日期列转换为日期类型, 去除时间部分
    strip_date_column(final_df, date_format="%Y-%m-%d")
    sort_by_date_shift(final_df)

    # 把日期和班次的位置放在第一列和第二列
    other_cols = [col for col in final_df.columns if col not in ['日期', '班次']]
    final_df = final_df[['日期', '班次'] + other_cols]

    # 6. 应用表头映射（数据处理完成后，对最终列结构进行重命名）
    if header_mapping and header_mapping.get('entries'):
        final_df = _apply_header_mapping(final_df, header_mapping)

    # 7. 输出到Excel
    if output_file is None:
        file_dir = os.path.dirname(file_path) or "."
        output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
    final_df.to_excel(output_file, index=False)
    logger.info(f"数据处理完成，已保存至: {output_file}")

    if return_sheets:
        return {"工时数据": final_df}


# --- 参数配置 ---
def main():
    from func.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="处理并合并Excel排班表")
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--year", type=int, default=2025, help="目标年份")
    parser.add_argument("--month", type=int, default=1, help="目标月份")
    args = parser.parse_args()
    file_dir = os.path.dirname(args.input_file) or "."
    output_xlsx = os.path.join(file_dir, f"{args.year}{args.month:02d}_工作效率表.xlsx")
    if os.path.exists(args.input_file):
        process_excel_data(args.input_file, args.year, args.month, output_xlsx)
    else:
        logger.error(f"错误：找不到输入文件 '{args.input_file}'！")


if __name__ == "__main__":
    main()
