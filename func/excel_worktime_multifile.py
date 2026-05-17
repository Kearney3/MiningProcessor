import sys
import pandas as pd
import os
import re
import argparse
from pathlib import Path

# 定位到当前项目的根目录
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
from func.logger import get_logger
logger = get_logger(__name__)


def extract_data_from_sheet(df_raw, year, month, day):
    """
    核心业务逻辑：从单个 DataFrame 中提取白班和夜班数据
    """
    date_str = f"{year}-{month:02d}-{day:02d}"

    # 表头在第2行 (index 1)
    if len(df_raw) < 2:
        return None

    header_row = df_raw.iloc[1]

    # 找出表头中有效的列（非NaN且非空白）用于比对
    valid_mask = header_row.notna() & (header_row.astype(str).str.strip() != '')
    valid_cols = valid_mask[valid_mask].index.tolist()
    valid_headers = header_row[valid_cols].astype(str).str.strip().tolist()

    if not valid_headers:
        return None

    split_idx = -1
    # 从第3行（index 2）开始向下遍历，寻找再次出现的表头
    for idx in range(2, len(df_raw)):
        current_row_vals = df_raw.iloc[idx][valid_cols].astype(str).str.strip().tolist()
        if current_row_vals[0] == valid_headers[0]:
            split_idx = idx
            break

    if split_idx == -1:
        # 没有找到夜班表头，视作全白班
        day_data = df_raw.iloc[2:].copy()
        day_data.columns = header_row
        day_data['班次'] = 'Day'
        combined_day_df = day_data
    else:
        # 处理白班数据 (从第3行 到 夜班表头前一行)
        day_data = df_raw.iloc[2:split_idx].copy()
        day_data.columns = header_row
        day_data['班次'] = 'Day'

        # 处理夜班数据 (从夜班表头的下一行 到最后)
        night_data = df_raw.iloc[split_idx + 1:].copy()
        night_data.columns = header_row
        night_data['班次'] = 'Night'

        combined_day_df = pd.concat([day_data, night_data], axis=0, ignore_index=True)

    # 插入日期列到第一列
    combined_day_df.insert(0, '日期', date_str)

    # 清理：忽略空表头列
    combined_day_df = combined_day_df.loc[:, combined_day_df.columns.notna()]
    if '' in combined_day_df.columns:
        combined_day_df = combined_day_df.drop(columns=[''])

    # 去掉第二列(索引为1的列)为空的行 (保留你原有的清理逻辑)
    if len(combined_day_df.columns) > 1:
        check_idx = -1
        # 找到包含”Техникийн”的列索引
        for idx, col in enumerate(combined_day_df.columns):
            if 'Техникийн' in col:
                check_idx = idx
                break
        if check_idx != -1:
            check_col = combined_day_df.columns[check_idx]
            combined_day_df.dropna(subset=[check_col], inplace=True)

    # 去掉除了“日期”和“班次”之外全部为空的行
    subset_cols = [c for c in combined_day_df.columns if c not in ['日期', '班次']]
    combined_day_df.dropna(how='all', subset=subset_cols, inplace=True)

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
                if sheet.strip().isdigit() and int(sheet.strip()) == target_day:
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
    final_df['日期'] = pd.to_datetime(final_df['日期'], format='%Y-%m-%d').dt.date
    final_df.sort_values(by=['日期', '班次'], ascending=[True, True], inplace=True)

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
            is_header_row = is_header_row & (final_df[col].astype(str).str.strip() == str(col).strip())

        initial_len = len(final_df)
        # 仅保留 不是表头 的行 (使用 ~ 取反)
        final_df = final_df[~is_header_row]

        removed_count = initial_len - len(final_df)
        if removed_count > 0:
            logger.info(f"自动清理了 {removed_count} 行混入数据的重复表头！")
    # ---------------------------------------------------------

    # 保存
    final_df.to_excel(output_file, index=False)
    logger.info(f"数据处理并合并完成，已保存至: {output_file}")


if __name__ == "__main__":
    try:
        from func.logger import setup_logging
        setup_logging()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="按目录结构合并多个排班Excel文件。")
    parser.add_argument("input_dir", help="包含按日期命名的文件夹的根目录")
    parser.add_argument("--year", type=int, default=2025, help="目标年份")
    parser.add_argument("--month", type=int, default=1, help="目标月份")
    args = parser.parse_args()

    # 构造输出路径：保存在根目录下
    base_dir = args.input_dir
    output_xlsx = os.path.join(base_dir, f"{args.year}{args.month:02d}_多文件合并_工作效率表.xlsx")

    process_directory(base_dir, args.year, args.month, output_xlsx)
