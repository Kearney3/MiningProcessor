import sys
import pandas as pd
import os
import argparse

# 假设 func.logger 已经正确配置
from func.logger import get_logger

logger = get_logger(__name__)


def process_excel_data(file_path, year, month, output_file):
    """
    解析非标准结构的Excel文件并合并数据
    """
    if not os.path.exists(file_path):
        logger.error(f"错误：找不到输入文件 '{file_path}'")
        sys.exit(1)

    logger.info(f"正在读取文件: {file_path} ...")
    try:
        # 读取所有的 sheet
        xls = pd.ExcelFile(file_path)
    except Exception as e:
        logger.error(f"读取 Excel 文件失败: {e}")
        sys.exit(1)

    all_data = []
    success_count = 0
    day_list = []

    for sheet_name in xls.sheet_names:
        # 确保sheet名称是数字（代表日期）
        if not sheet_name.strip().isdigit():
            logger.warning(f"跳过非日期Sheet: {sheet_name}")
            continue

        # 读取整个sheet，不设表头
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        # 1. 确定日期字符串 (YYYY-MM-DD)
        day = int(sheet_name.strip())
        date_str = f"{year}-{month:02d}-{day:02d}"
        day_list.append(day)

        # 2. 提取白班表头并寻找夜班表头 (通过表头复现来切割)
        # 表头在第2行 (index 1)
        header_row = df_raw.iloc[1]

        # 找出表头中有效的列（非NaN且非空白）用于比对
        valid_mask = header_row.notna() & (header_row.astype(str).str.strip() != '')
        valid_cols = valid_mask[valid_mask].index.tolist()
        valid_headers = header_row[valid_cols].astype(str).str.strip().tolist()

        split_idx = -1
        # 从第3行（index 2）开始向下遍历，寻找再次出现的表头
        for idx in range(2, len(df_raw)):
            current_row_vals = df_raw.iloc[idx][valid_cols].astype(str).str.strip().tolist()
            # 如果当前行的有效列内容与提取的表头完全一致，则判定为夜班表头
            if current_row_vals == valid_headers:
                split_idx = idx
                break

        if split_idx == -1:
            logger.warning(f"警告: Sheet {sheet_name} 未找到再次出现的表头，视作全天只有白班处理")
            day_data = df_raw.iloc[2:].copy()
            day_data.columns = header_row
            day_data['班次'] = 'Day'
            combined_day_df = day_data
        else:
            # --- 处理白班数据 ---
            # 白班数据从第3行 (index 2) 到 夜班表头前一行 (split_idx - 1)
            day_data = df_raw.iloc[2:split_idx].copy()
            day_data.columns = header_row
            day_data['班次'] = 'Day'

            # --- 处理夜班数据 ---
            # 夜班数据从夜班表头的下一行 (split_idx + 1) 开始到最后
            night_data = df_raw.iloc[split_idx + 1:].copy()
            night_data.columns = header_row  # 夜班表头结构一致，直接套用
            night_data['班次'] = 'Night'

            # 合并当前Sheet的白班和夜班
            combined_day_df = pd.concat([day_data, night_data], axis=0, ignore_index=True)

        # 插入日期列到第一列
        combined_day_df.insert(0, '日期', date_str)

        # 3. 清理：忽略空表头列，并去掉全是空值的行
        # 去掉列名为 NaN 的列
        combined_day_df = combined_day_df.loc[:, combined_day_df.columns.notna()]

        # 去掉第二列(索引为1的列)为空的行 (保留你原有的清理逻辑)
        if len(combined_day_df.columns) > 1:
            check_idx = -1
            # 找到包含“Техникийн”的列索引
            for idx, col in enumerate(combined_day_df.columns):
                if 'Техникийн' in col:
                    check_idx = idx
                    break
            check_col = combined_day_df.columns[check_idx]
            if check_idx != -1:
                combined_day_df.dropna(subset=[check_col], inplace=True)

        # 去掉除了“日期”和“班次”之外全部为空的行
        subset_cols = [c for c in combined_day_df.columns if c not in ['日期', '班次']]
        combined_day_df.dropna(how='all', subset=subset_cols, inplace=True)

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
    final_df['日期'] = pd.to_datetime(final_df['日期'], format='%Y-%m-%d').dt.date

    # 白班在夜班前（Day 排在 Night 前面符合拼音/字母排序）
    final_df.sort_values(by=['日期', '班次'], ascending=[True, True], inplace=True)

    # 把日期和班次的位置放在第一列和第二列
    other_cols = [col for col in final_df.columns if col not in ['日期', '班次']]
    final_df = final_df[['日期', '班次'] + other_cols]

    # 6. 输出到Excel
    final_df.to_excel(output_file, index=False)
    logger.info(f"数据处理完成，已保存至: {output_file}")


# --- 参数配置 ---
if __name__ == "__main__":
    try:
        from func.logger import setup_logging

        setup_logging()
    except ImportError:
        pass  # 若没有此初始化函数则跳过

    parser = argparse.ArgumentParser(description="处理并合并Excel排班表。")
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--year", type=int, default=2025, help="目标年份")
    parser.add_argument("--month", type=int, default=1, help="目标月份")
    args = parser.parse_args()

    # 输出文件名构造
    file_dir = os.path.dirname(args.input_file)
    if not file_dir:
        file_dir = "."
    output_xlsx = os.path.join(file_dir, f"{args.year}{args.month:02d}_工作效率表.xlsx")

    if os.path.exists(args.input_file):
        process_excel_data(args.input_file, args.year, args.month, output_xlsx)
    else:
        logger.error(f"错误：找不到输入文件 '{args.input_file}'！")