"""处理宽格式柴油消耗报表（单文件脚本，无项目内部依赖）。

适用于日期（1~31）作为列头、设备名称作为行头的柴油消耗表。
将宽格式"融化"为长格式：日期 (YYYY-MM-DD) | 设备名称 | 油品消耗。

用法:
    python excel_fuel_wide.py <输入文件> --year 2020 --month 4
"""

import argparse
import logging
import os
from datetime import date

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 默认表头行（日期编号所在行）和数据起始行
DEFAULT_DAY_HEADER_ROW = 4
DEFAULT_DATA_START_ROW = 6


def _write_formatted_excel(output_file: str, sheets: dict[str, pd.DataFrame]) -> str:
    """写入带格式的 Excel：表头蓝底白字、列宽自适应、日期列 yyyy-mm-dd、冻结首行。"""
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)

    wb = openpyxl.load_workbook(output_file)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center")

    for name, df in sheets.items():
        ws = wb[name]
        if ws.max_row is None or ws.max_row < 1:
            continue

        # 表头样式
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center

        # 列宽自适应（取前 500 行采样）
        for col_idx, col_name in enumerate(df.columns, start=1):
            max_w = len(str(col_name)) + 2
            for val in df[col_name].dropna().head(500):
                max_w = max(max_w, len(str(val)) + 2)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_w, 8), 50)

        # 日期列格式
        for col_idx, col_name in enumerate(df.columns, start=1):
            sample = df[col_name].dropna().head(20)
            if sample.apply(lambda v: isinstance(v, (date, ))).any():
                for row in range(2, ws.max_row + 1):
                    cell = ws.cell(row=row, column=col_idx)
                    if cell.value is not None:
                        cell.number_format = "yyyy-mm-dd"

        ws.freeze_panes = "A2"
        last_col = get_column_letter(ws.max_column)
        ws.auto_filter.ref = f"A1:{last_col}{ws.max_row}"

    wb.save(output_file)
    wb.close()
    return output_file


def process_fuel_wide(
    file_path: str,
    year: int,
    month: int,
    *,
    day_header_row: int = DEFAULT_DAY_HEADER_ROW,
    data_start_row: int = DEFAULT_DATA_START_ROW,
    return_df: bool = False,
) -> str | pd.DataFrame:
    """处理宽格式柴油消耗 Excel，输出长格式结果。

    Args:
        file_path: 输入 Excel 文件路径。
        year: 年份（如 2020）。
        month: 月份（如 4）。
        day_header_row: 日期编号所在行号（1-based）。
        data_start_row: 数据起始行号（1-based）。
        return_df: 若为 True 返回 DataFrame 而非写入文件。

    Returns:
        当 return_df=False 时返回输出文件路径；
        当 return_df=True 时返回 DataFrame。

    Raises:
        ValueError: 文件中未找到有效数据。
    """
    logger.info("正在处理宽格式柴油报表: %s (年=%d, 月=%d)", file_path, year, month)

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    # 从日期编号行构建列→日映射
    col_to_day: dict[int, int] = {}
    for col_idx in range(1, ws.max_column + 1):
        val = ws.cell(day_header_row, col_idx).value
        if val is not None:
            try:
                day_num = int(val)
                if 1 <= day_num <= 31:
                    col_to_day[col_idx] = day_num
            except (ValueError, TypeError):
                pass

    if not col_to_day:
        wb.close()
        raise ValueError(f"在第 {day_header_row} 行未找到有效的日期编号列")

    logger.info("检测到 %d 个日期列: %s", len(col_to_day), sorted(col_to_day.values()))

    # 遍历数据行，融化为长格式
    records: list[dict] = []
    for row_idx in range(data_start_row, ws.max_row + 1):
        raw_name = ws.cell(row_idx, 2).value  # B 列：设备名称
        if raw_name is None:
            continue
        device_name = str(raw_name).strip()
        if not device_name:
            continue

        for col_idx, day in col_to_day.items():
            val = ws.cell(row_idx, col_idx).value
            if val is None:
                continue
            try:
                fuel = float(val)
            except (ValueError, TypeError):
                continue
            if fuel == 0:
                continue

            records.append({
                "日期": date(year, month, day),
                "设备名称": device_name,
                "油品消耗": fuel,
            })

    wb.close()

    if not records:
        raise ValueError("柴油消耗表中未找到有效数据（所有消耗值为 0 或为空）")

    df = pd.DataFrame(records)
    df.sort_values(by=["日期", "设备名称"], inplace=True, ignore_index=True)

    logger.info("提取 %d 条记录，%d 台设备", len(df), df["设备名称"].nunique())

    if return_df:
        return df

    output_file = os.path.join(os.path.dirname(file_path) or ".", "Fuel_wide.xlsx")
    _write_formatted_excel(output_file, {"油耗信息": df})
    logger.info("处理完成！文件已保存: %s", output_file)
    return output_file


def main():
    parser = argparse.ArgumentParser(description="处理宽格式柴油消耗报表")
    parser.add_argument("input_file", help="输入 Excel 文件路径")
    parser.add_argument("--year", type=int, required=True, help="年份（如 2020）")
    parser.add_argument("--month", type=int, required=True, help="月份（如 4）")
    parser.add_argument("--day-header-row", type=int, default=DEFAULT_DAY_HEADER_ROW,
                        help="日期编号所在行号（默认 4）")
    parser.add_argument("--data-start-row", type=int, default=DEFAULT_DATA_START_ROW,
                        help="数据起始行号（默认 6）")
    args = parser.parse_args()

    process_fuel_wide(
        args.input_file,
        year=args.year,
        month=args.month,
        day_header_row=args.day_header_row,
        data_start_row=args.data_start_row,
    )


if __name__ == "__main__":
    main()
