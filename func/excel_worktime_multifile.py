import sys
import pandas as pd
import os
import re
import argparse

from func.logger import get_logger
from func.string_utils import clean_string
from func.excel_utils import split_day_night_shifts, clean_split_dataframe, strip_date_column, sort_by_date_shift, dedup_dataframe
logger = get_logger(__name__)


def extract_data_from_sheet(df_raw, year, month, day):
    “””
    核心业务逻辑：从单个 DataFrame 中提取白班和夜班数据
    “””
    date_str = f”{year}-{month:02d}-{day:02d}”

    if len(df_raw) < 2:
        return None

    # 分割 Day/Night 班次（day_end_offset=0 对应原 multifile 行为）
    combined_day_df = split_day_night_shifts(df_raw, day_end_offset=0)
    if combined_day_df is None or combined_day_df.empty:
        return None

    # 插入日期列到第一列
    combined_day_df.insert(0, “日期”, date_str)

    # 清洗
    combined_day_df = clean_split_dataframe(combined_day_df)

    return combined_day_df


def process_directory(base_dir, year, month, output_file):
    if not os.path.isdir(base_dir):
        logger.error(f"错误：找不到目录 '{base_dir}'")
        sys.exit(1)

    all_data = []
    success_count = 0
    processed_days = []

    logger.info(f"开始遍历目录: {base_dir}")

    for item in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, item)

        # 只处理文件夹
        if not os.path.isdir(folder_path):
            continue

        # 使用正则提取文件夹开头的所有数字 (如 "01_测试" -> 1, "11" -> 11)
        match = re.match(r'^(\d+)', item)
        if not match:
            logger.debug(f"跳过非数字开头的文件夹: {item}")
            continue

        target_day = int(match.group(1))

        # 遍历该文件夹下的文件
        for file in os.listdir(folder_path):
            # 排除临时文件，并且必须包含特定关键字
            if file.startswith('~$'):
                continue
            if not (file.endswith('.xlsx') or file.endswith('.xls')):
                continue
            if "Tsag" not in file and "工作效率" not in file and "Цаг" not in file:
                continue

            excel_path = os.path.join(folder_path, file)
            logger.info(f"正在处理文件: {os.path.join(item, file)}")

            try:
                xls = pd.ExcelFile(excel_path)
            except Exception as e:
                logger.error(f"读取文件失败 '{excel_path}': {e}")
                continue

            # 寻找与目标日期对应的 Sheet
            target_sheet_name = None
            for sheet in xls.sheet_names:
                if clean_string(sheet).isdigit() and int(clean_string(sheet)) == target_day:
                    target_sheet_name = sheet
                    break
            if not target_sheet_name and len(xls.sheet_names) == 1:
                target_sheet_name = xls.sheet_names[0]
                logger.warning(f"文件 '{file}' 中只有一个 Sheet，已自动选择「{target_sheet_name}」")

            if not target_sheet_name:
                logger.warning(f"未找到与日期 {target_day} 匹配的 Sheet，已跳过")
                continue

            # 读取目标 Sheet
            df_raw = pd.read_excel(xls, sheet_name=target_sheet_name, header=None)

            # 使用提取逻辑
            df_processed = extract_data_from_sheet(df_raw, year, month, target_day)

            if df_processed is not None and not df_processed.empty:
                all_data.append(df_processed)
                success_count += 1
                processed_days.append(target_day)
                logger.info(f"成功提取日期 {target_day} 的数据，共 {len(df_processed)} 行")
            else:
                logger.warning(f"日期 {target_day} 的 Sheet 「{target_sheet_name}」数据提取为空")

    if not all_data:
        logger.warning("未提取到任何有效数据。请检查文件夹结构或 Excel 内容。")
        return

    logger.info(f"提取完成！共成功处理 {success_count} 个日期的数据")
    logger.info(f"包含的日期有: {sorted(list(set(processed_days)))}")

    final_df = pd.concat(all_data, axis=0, ignore_index=True)

    # 排序与列格式化
    final_df = strip_date_column(final_df, date_format="%Y-%m-%d")
    final_df = sort_by_date_shift(final_df)

    # 将日期和班次强制排在最前面
    other_cols = [col for col in final_df.columns if col not in ['日期', '班次']]
    final_df = final_df[['日期', '班次'] + other_cols]

    # ---------------------------------------------------------
    # 新增逻辑：全局剔除所有混入的重复表头
    # ---------------------------------------------------------
    if other_cols:
        # 我们取原始表头的前几列作为特征验证（最多取前3列防止误判）
        check_cols = other_cols[:3]
        # 初始化一个全是 True 的判定序列
        is_header_row = pd.Series([True] * len(final_df), index=final_df.index)

        # 如果一行的这些关键列的数据，全部和列名（表头名）一模一样，那它一定是表头
        for col in check_cols:
            is_header_row = is_header_row & (final_df[col].apply(clean_string) == clean_string(col))

        initial_len = len(final_df)
        # 仅保留 不是表头 的行 (使用 ~ 取反)
        final_df = final_df[~is_header_row]

        removed_count = initial_len - len(final_df)
        if removed_count > 0:
            logger.info(f"自动清理了 {removed_count} 行混入数据的重复表头！")
    # ---------------------------------------------------------

    # 去重
    final_df = dedup_dataframe(final_df, "多文件工时合并")

    # 保存
    final_df.to_excel(output_file, index=False)
    logger.info(f"数据处理并合并完成，已保存至: {output_file}")


def main():
    from func.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="按目录结构合并多个排班Excel文件")
    parser.add_argument("input_dir", help="包含按日期命名的文件夹的根目录")
    parser.add_argument("--year", type=int, default=2025, help="目标年份")
    parser.add_argument("--month", type=int, default=1, help="目标月份")
    args = parser.parse_args()
    base_dir = args.input_dir
    output_xlsx = os.path.join(base_dir, f"{args.year}{args.month:02d}_多文件合并_工作效率表.xlsx")
    process_directory(base_dir, args.year, args.month, output_xlsx)


if __name__ == "__main__":
    main()
