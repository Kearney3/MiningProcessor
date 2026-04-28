"""
解析电力消耗报表
"""
import os

import pandas as pd
import re
from datetime import datetime
import argparse
import sys
from pathlib import Path

# 定位到当前项目的根目录
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
from func.logger import get_logger

logger = get_logger(__name__)


def parse_excel_data(file_path, target_year=None):
    """
    解析复杂的Excel电力消耗报表
    :param file_path: 输入文件路径
    :param target_year: 如果指定，则将所有日期的年份修改为此年份
    """
    all_extracted_data = []

    # 1. 加载Excel，读取所有Sheet
    xl = pd.ExcelFile(file_path)
    sheet_names = [s for s in xl.sheet_names if "Electrical" in s]

    for sheet_name in sheet_names:
        logger.info(f"正在处理 Sheet: {sheet_name}")
        df = xl.parse(sheet_name, header=None)  # 不设表头，手动定位

        # 2. 找到“日期”所在行
        date_row_idx = None
        for idx, val in df.iloc[:, 0].items():
            if "日期" in str(val).strip():
                date_row_idx = idx
                break

        if date_row_idx is None:
            logger.warning(f"跳过 Sheet {sheet_name}: 未找到关键字'日期'")
            continue

        # 3. 解析日期列 (从E列开始，即索引4)
        date_row = df.iloc[date_row_idx]
        date_mapping = {}  # 存储 {列索引: 日期对象}

        for col_idx in range(4, len(date_row)):
            cell_val = date_row[col_idx]
            try:
                # 尝试解析日期
                dt = pd.to_datetime(cell_val)
                if pd.isna(dt): continue

                # 如果用户指定了年份，进行更正
                if target_year:
                    dt = dt.replace(year=int(target_year))

                date_mapping[col_idx] = dt
            except:
                continue  # 无法识别则跳过

        # 4. 寻找数据行并提取设备名称
        # 我们只关注 A列包含 "电力总消耗" 且包含 "EX-" 的行
        for idx in range(date_row_idx + 1, len(df)):
            a_val = str(df.iloc[idx, 0])

            # 过滤规则：必须包含“电力总消耗”且不能包含“每立方”
            if "电力总消耗" in a_val and "每立方产量" not in a_val:
                # 使用正则提取 EX-xxxx 格式的设备名称
                device_match = re.search(r'(EX-[\w#.-]+)', a_val)
                if device_match:
                    device_name = device_match.group(1)

                    # 5. 提取对应日期的消耗数值
                    for col_idx, current_date in date_mapping.items():
                        power_val = df.iloc[idx, col_idx]

                        # 只记录有数值的数据
                        if pd.notna(power_val) and isinstance(power_val, (int, float)):
                            all_extracted_data.append({
                                "日期": current_date,
                                "设备名称": device_name,
                                "电力消耗": power_val
                            })

    # 6. 整合结果并导出
    if not all_extracted_data:
        logger.warning("未提取到任何数据，请检查文件格式。")
        return

    result_df = pd.DataFrame(all_extracted_data)
    # 日期去掉时间部分
    result_df["日期"] = pd.to_datetime(result_df["日期"]).dt.date

    # 按日期排序
    result_df = result_df.sort_values(by="日期").reset_index(drop=True)

    # 导出
    output_file = os.path.join(os.path.dirname(file_path), "电力消耗统计.xlsx")
    result_df.to_excel(output_file, index=False, sheet_name="电力消耗")
    logger.info(f"处理完成！结果已保存至: {output_file}")


# --- 使用示例 ---
if __name__ == "__main__":
    from logger import setup_logging

    setup_logging()
    # 使用cli
    parser = argparse.ArgumentParser(description="解析电力消耗报表")
    parser.add_argument("input_file", type=str, help="输入Excel文件路径")
    parser.add_argument("--year", type=int, help="如果指定，则将所有日期的年份修改为此年份")
    args = parser.parse_args()
    parse_excel_data(args.input_file, target_year=args.year)
