"""
解析电力消耗报表
"""
import os

import numpy as np
import pandas as pd
import re
import argparse

from func.logger import get_logger
from func.excel_utils import dedup_dataframe, detect_shift
from func.string_utils import clean_string

logger = get_logger(__name__)


def parse_excel_data(file_path, target_year=None, return_sheets=False, add_shift_column=False, default_shift="Day"):
    """
    解析复杂的Excel电力消耗报表
    :param file_path: 输入文件路径
    :param target_year: 如果指定，则将所有日期的年份修改为此年份
    :param add_shift_column: 是否在日期列右侧新增班次列 (Day/Night)
    :param default_shift: 当无法从表头识别班次时使用的默认值，"Day" 或 "Night"
    """
    all_extracted_data = []

    # 1. 加载Excel，读取所有Sheet
    with pd.ExcelFile(file_path) as xl:
        sheet_names = [s for s in xl.sheet_names if "Electrical" in s]

        for sheet_name in sheet_names:
            logger.info(f"正在处理 Sheet: {sheet_name}")
            df = xl.parse(sheet_name, header=None)  # 不设表头，手动定位

            if df.empty or df.shape[1] == 0:
                logger.warning(f"跳过 Sheet {sheet_name}: 空表")
                continue

            # 2. 找到"日期"所在行
            date_row_idx = None
            for idx, val in df.iloc[:, 0].items():
                if "日期" in clean_string(val):
                    date_row_idx = idx
                    break

            if date_row_idx is None:
                logger.warning(f"跳过 Sheet {sheet_name}: 未找到关键字'日期'")
                continue

            # 3. 解析日期列 (从E列开始，即索引4)
            date_row = df.iloc[date_row_idx]
            date_mapping = {}  # 存储 {列索引: 日期对象}
            col_to_shift = {}  # 存储 {列索引: 班次}，仅 add_shift_column 时使用

            # 如果需要班次列，尝试从日期行上方的行中识别白班/夜班
            if add_shift_column:
                for scan_row in range(max(0, date_row_idx - 3), date_row_idx):
                    for col_idx in range(4, len(df.columns)):
                        try:
                            cell_val = clean_string(df.iloc[scan_row, col_idx])
                        except Exception:
                            continue
                        shift = detect_shift(cell_val)
                        if shift:
                            col_to_shift[col_idx] = shift

            for col_idx in range(4, len(date_row)):
                cell_val = date_row[col_idx]
                try:
                    # 尝试解析日期
                    # 处理 Excel 序列号日期（自 1899-12-30 起的天数）
                    if isinstance(cell_val, (int, float, np.integer, np.floating)) and not pd.isna(cell_val) and cell_val > 30000:
                        dt = pd.to_datetime(cell_val, unit='D', origin='1899-12-30')
                    else:
                        dt = pd.to_datetime(cell_val)
                    if pd.isna(dt): continue

                    # 如果用户指定了年份，进行更正
                    if target_year:
                        dt = dt.replace(year=int(target_year))

                    date_mapping[col_idx] = dt
                except (ValueError, TypeError):
                    continue  # 无法识别则跳过

            # 4. 寻找数据行并提取设备名称
            # 我们只关注 A列包含 "电力总消耗" 且包含 "EX-" 的行
            for idx in range(date_row_idx + 1, len(df)):
                a_val = clean_string(df.iloc[idx, 0])

                # 过滤规则：必须包含"电力总消耗"且不能包含"每立方"
                if "电力总消耗" in a_val and "每立方产量" not in a_val:
                    # 使用正则提取 EX-xxxx 格式的设备名称
                    device_match = re.search(r'(EX-[\w#.-]+)', a_val)
                    if device_match:
                        device_name = clean_string(device_match.group(1))

                        # 5. 提取对应日期的消耗数值
                        for col_idx, current_date in date_mapping.items():
                            power_val = df.iloc[idx, col_idx]

                            # 只记录有数值的数据
                            if pd.notna(power_val) and isinstance(power_val, (int, float, np.integer, np.floating)):
                                record = {
                                    "日期": current_date,
                                    "设备名称": device_name,
                                    "电力消耗": power_val,
                                }
                                if add_shift_column:
                                    # 优先从表头读取；未识别到则使用用户指定的默认班次
                                    shift = col_to_shift.get(col_idx)
                                    if not shift:
                                        # 向前查找最近的班次标识
                                        for search in range(col_idx, 3, -1):
                                            if search in col_to_shift:
                                                shift = col_to_shift[search]
                                                break
                                    record["班次"] = shift or default_shift
                                all_extracted_data.append(record)

    # 6. 整合结果并导出
    if not all_extracted_data:
        logger.warning("未提取到任何数据，请检查文件格式。")
        return

    result_df = pd.DataFrame(all_extracted_data)
    # 日期去掉时间部分
    result_df["日期"] = pd.to_datetime(result_df["日期"]).dt.date

    # 班次列排序辅助（Day 在 Night 前）
    if add_shift_column and "班次" in result_df.columns:
        shift_rank = result_df["班次"].map({"Day": 0, "Night": 1}).fillna(2)
        result_df = result_df.assign(_shift_rank=shift_rank)
        result_df = result_df.sort_values(by=["日期", "_shift_rank"]).drop(columns=["_shift_rank"])
        # 确保列顺序：日期, 班次, 设备名称, 电力消耗
        result_df = result_df[["日期", "班次", "设备名称", "电力消耗"]]
    else:
        result_df = result_df.sort_values(by="日期").reset_index(drop=True)

    # 去重
    result_df = dedup_dataframe(result_df, "电力消耗")

    if return_sheets:
        return {"电力消耗": result_df}

    from func.excel_formatter import write_formatted_excel

    # 导出
    output_file = os.path.join(os.path.dirname(file_path), "电力消耗统计.xlsx")
    write_formatted_excel(output_file, {"电力消耗": result_df})
    logger.info(f"处理完成！结果已保存至: {output_file}")


# --- 使用示例 ---
def main():
    from func.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="解析电力消耗报表")
    parser.add_argument("input_file", type=str, help="输入Excel文件路径")
    parser.add_argument("--year", type=int, help="如果指定，则将所有日期的年份修改为此年份")
    parser.add_argument("--add-shift", action="store_true", help="在日期列右侧新增班次列 (Day/Night)")
    parser.add_argument("--default-shift", choices=["Day", "Night"], default="Day",
                        help="当无法从表头识别班次时使用的默认值 (默认: Day)")
    args = parser.parse_args()
    parse_excel_data(args.input_file, target_year=args.year,
                     add_shift_column=args.add_shift, default_shift=args.default_shift)


# 统一命名别名（L-01）
process_electrical_data = parse_excel_data


if __name__ == "__main__":
    main()
