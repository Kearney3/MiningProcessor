import pandas as pd
import os
import argparse

# 假设 func.logger 已经正确配置
from func.logger import get_logger
from func.string_utils import clean_string
from func.excel_utils import apply_header_mapping, split_day_night_shifts, clean_split_dataframe, strip_date_column, sort_by_date_shift, dedup_dataframe, get_hidden_indices, filter_hidden_from_df, adjust_index_for_hidden, open_workbook
from func.anomaly import detect_and_filter
from func.anomaly.rules import AnomalyConfig
from func import config_loader

logger = get_logger(__name__)


def process_excel_data(file_path, year, month, output_file=None, return_sheets=False,
                       header_mapping=None, skip_hidden=False,
                       skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None):
    """
    解析非标准结构的Excel文件并合并数据

    Args:
        file_path: 输入文件路径
        year: 目标年份
        month: 目标月份
        output_file: 输出文件路径（可选）
        return_sheets: 是否返回 sheets 字典（供批量处理用）
        header_mapping: 表头映射字典 {原始列名: 新列名}，为 None 或空时不映射
        skip_hidden: 若为 True，跳过 Excel 中的隐藏行和隐藏列（兼容旧调用）
        skip_hidden_rows: 若为 True，仅跳过 Excel 中的隐藏行
        skip_hidden_cols: 若为 True，仅跳过 Excel 中的隐藏列
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到输入文件 '{file_path}'")

    # 向后兼容：skip_hidden 打开时同时跳过隐藏行和列
    if skip_hidden:
        skip_hidden_rows = True
        skip_hidden_cols = True
    need_hidden = skip_hidden_rows or skip_hidden_cols

    logger.info(f"正在读取文件: {file_path} ...")
    try:
        # 读取所有的 sheet
        xls = pd.ExcelFile(file_path)
    except (FileNotFoundError, PermissionError, ValueError) as e:
        raise RuntimeError(f"读取 Excel 文件失败: {e}") from e

    with xls:
        all_data = []
        success_count = 0
        day_list = []

        # 需要跳过隐藏行列时预先加载 workbook，避免每个 sheet 重复 load_workbook
        hidden_wb = open_workbook(file_path) if need_hidden else None
        try:
            for sheet_name in xls.sheet_names:
                # 确保sheet名称是数字（代表日期）
                if not clean_string(sheet_name).isdigit():
                    logger.warning(f"跳过非日期Sheet: {sheet_name}")
                    continue

                # 读取整个sheet，不设表头
                df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)

                if need_hidden:
                    h_rows, h_cols = get_hidden_indices(file_path, sheet_name, _workbook=hidden_wb)
                    df_raw = filter_hidden_from_df(
                        df_raw,
                        h_rows if skip_hidden_rows else set(),
                        h_cols if skip_hidden_cols else set(),
                    )
                else:
                    h_rows = set()

                # 1. 确定日期字符串 (YYYY-MM-DD)
                day = int(clean_string(sheet_name))
                date_str = f"{year}-{month:02d}-{day:02d}"
                day_list.append(day)

                # 2. 分割 Day/Night 班次
                # Adjust hardcoded row indices for hidden rows that were removed
                if h_rows:
                    adj_header = adjust_index_for_hidden(1, h_rows, one_based=True)
                    adj_data = adjust_index_for_hidden(2, h_rows, one_based=True)
                    combined_day_df = split_day_night_shifts(
                        df_raw, header_row_index=adj_header, data_start_index=adj_data,
                    )
                else:
                    combined_day_df = split_day_night_shifts(df_raw)

                # 插入日期列到第一列
                combined_day_df.insert(0, '日期', date_str)

                # 3. 清洗
                combined_day_df = clean_split_dataframe(combined_day_df)

                all_data.append(combined_day_df)
                success_count += 1
                logger.info(f"成功处理日期: {day}, 有效数据行数: {len(combined_day_df)}")
        finally:
            if hidden_wb is not None:
                hidden_wb.close()

        # 4. 合并所有日期的数据
        if not all_data:
            logger.warning("未提取到任何有效数据。")
            return

        logger.info(f"成功处理 {success_count} 个日期数据")
        logger.info(f"成功导入的日期为: {sorted(day_list)}")

    final_df = pd.concat(all_data, axis=0, ignore_index=True)

    # 5. 排序：按日期排序, 并将日期列转换为日期类型, 去除时间部分
    final_df = strip_date_column(final_df, date_format="%Y-%m-%d")
    final_df = sort_by_date_shift(final_df)

    # 把日期和班次的位置放在第一列和第二列
    other_cols = [col for col in final_df.columns if col not in ['日期', '班次']]
    final_df = final_df[['日期', '班次'] + other_cols]

    # 6. 应用表头映射（数据处理完成后，对最终列结构进行重命名）
    if header_mapping and header_mapping.get('entries'):
        final_df = apply_header_mapping(final_df, header_mapping)

    # 去重
    final_df = dedup_dataframe(final_df, "工时数据")

    # 异常值检测
    output_dir = os.path.dirname(file_path) or "."
    if anomaly_config is None:
        anomaly_config = AnomalyConfig.from_config(config_loader.get_anomaly_detection_config())
    if anomaly_config.enabled:
        final_df, _ = detect_and_filter(
            final_df, "worktime", anomaly_config, output_dir=output_dir)

    # 7. 输出到Excel（跳过写入当 return_sheets=True）
    if return_sheets:
        return {"工时数据": final_df}

    if output_file is None:
        file_dir = os.path.dirname(file_path) or "."
        output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
    from func.excel_formatter import write_formatted_excel

    write_formatted_excel(output_file, {"工时数据": final_df})
    logger.info(f"数据处理完成，已保存至: {output_file}")


# --- 参数配置 ---
def main():
    from func.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="处理并合并Excel排班表")
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--year", type=int, default=2025, help="目标年份")
    parser.add_argument("--month", type=int, default=1, help="目标月份")
    parser.add_argument("--skiphidden", action="store_true", help="跳过 Excel 中的隐藏行和隐藏列（等价于同时指定 --skip-hidden-rows 和 --skip-hidden-cols）")
    parser.add_argument("--skip-hidden-rows", action="store_true", help="跳过 Excel 中的隐藏行")
    parser.add_argument("--skip-hidden-cols", action="store_true", help="跳过 Excel 中的隐藏列")
    args = parser.parse_args()
    file_dir = os.path.dirname(args.input_file) or "."
    output_xlsx = os.path.join(file_dir, f"{args.year}{args.month:02d}_工作效率表.xlsx")
    if os.path.exists(args.input_file):
        process_excel_data(args.input_file, args.year, args.month, output_xlsx,
                           skip_hidden=args.skiphidden,
                           skip_hidden_rows=args.skip_hidden_rows,
                           skip_hidden_cols=args.skip_hidden_cols)
    else:
        logger.error(f"错误：找不到输入文件 '{args.input_file}'！")


# 统一命名别名（L-01）
process_worktime_data = process_excel_data


if __name__ == "__main__":
    main()
