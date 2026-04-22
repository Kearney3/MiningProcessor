import pandas as pd
import os

def process_excel_data(file_path, year, month, output_file):
    """
    解析非标准结构的Excel文件并合并数据
    """
    # 加载所有sheet
    xls = pd.ExcelFile(file_path)
    all_data = []
    success_count = 0
    day_list = []
    for sheet_name in xls.sheet_names:
        # 确保sheet名称是数字（代表日期）
        if not sheet_name.strip().isdigit():
            print(f"跳过非日期Sheet: {sheet_name}")
            continue

        # 读取整个sheet，不设表头
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        
        # 1. 确定日期字符串 (YYYY-MM-DD)
        day = int(sheet_name.strip())
        date_str = f"{year}-{month:02d}-{day:02d}"
        day_list.append(day)

        # 2. 寻找“夜班”关键字在B列（索引1）的位置
        # 注意：这里假设“夜班”字样在B列
        night_shift_index = df_raw[df_raw[1].astype(str).str.contains("夜班", na=False)].index
        
        if len(night_shift_index) == 0:
            print(f"警告: Sheet {sheet_name} 未找到'夜班'标记")
            # 如果没找到夜班，则认为全表为白班（视情况调整逻辑）
            continue

        split_idx = night_shift_index[0]

        # --- 处理白班数据 ---
        # 表头在第2行 (index 1)
        header_row = df_raw.iloc[1]
        # 白班数据从第3行 (index 2) 到 split_idx - 1
        day_data = df_raw.iloc[2:split_idx].copy()
        day_data.columns = header_row
        day_data['班次'] = 'Day'
        
        # --- 处理夜班数据 ---
        # 夜班关键字所在行的下一行为表头 (split_idx + 1)
        night_header_row = df_raw.iloc[split_idx + 1]
        # 夜班数据从 (split_idx + 2) 开始到最后
        night_data = df_raw.iloc[split_idx + 2:].copy()
        night_data.columns = night_header_row
        night_data['班次'] = 'Night'

        # 合并当前Sheet的白班和夜班
        combined_day_df = pd.concat([day_data, night_data], axis=0, ignore_index=True)
        
        # 插入日期列到第一列
        combined_day_df.insert(0, '日期', date_str)
        
        # 3. 清理：忽略空表头列，并去掉全是空值的行
        # 去掉列名为 NaN 的列
        combined_day_df = combined_day_df.loc[:, combined_day_df.columns.notna()]
        # 去掉第二列为空的行
        combined_day_df.dropna(subset=[combined_day_df.columns[1]], inplace=True)

        # 去掉包含在“日期”和“班次”之外全部为空的行
        subset_cols = [c for c in combined_day_df.columns if c not in ['日期', '班次']]
        combined_day_df.dropna(how='all', subset=subset_cols, inplace=True)

        all_data.append(combined_day_df)
        success_count += 1
        print(f"成功处理日期: {day}, 数据行数: {len(combined_day_df)}")

    # 4. 合并所有日期的数据
    if not all_data:
        print("未提取到任何有效数据。")
        return

    print(f"成功处理 {success_count} 个日期数据")
    print(f"成功导入的日期为: {sorted(day_list)}")
    final_df = pd.concat(all_data, axis=0, ignore_index=True)
    final_df.to_excel(output_file, index=False)

    # 5. 排序：按日期排序,并且使用格式2025-01-01, 并将日期列转换为日期类型,去除时间部分

    final_df['日期'] = pd.to_datetime(final_df['日期'], format='%Y-%m-%d').dt.date

    final_df.to_excel(output_file, index=False)
    final_df.sort_values(by=['日期', '班次'], ascending=[True, False], inplace=True) # 白班在夜班前（拼音排序）

    # 把日期和班次的位置放在第一列和第二列
    final_df = final_df[['日期', '班次'] + [col for col in final_df.columns if col not in ['日期', '班次']]]

    # 6. 输出到Excel
    final_df.to_excel(output_file, index=False)
    print(f"数据处理完成，已保存至: {output_file}")

# --- 参数配置 ---
if __name__ == "__main__":
    # 使用cli参数解析
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--year", type=int, default=2025, help="目标年份")
    parser.add_argument("--month", type=int, default=1, help="目标月份")
    args = parser.parse_args()
    # 输出文件名
    file_dir = os.path.dirname(args.input_file)
    output_xlsx = os.path.join(file_dir, f"{args.year}{args.month:02d}_工作效率表.xlsx")

    if os.path.exists(args.input_file):
        process_excel_data(args.input_file, args.year, args.month, output_xlsx)
    else:
        print("错误：找不到输入文件！")