import argparse
import os

import pandas as pd
import numpy as np

from func.logger import get_logger
from func.string_utils import clean_string
from func.excel_utils import dedup_dataframe, resolve_shift

logger = get_logger(__name__)


def process_diesel_data(file_path, target_year=None, return_sheets=False):
    xl = pd.ExcelFile(file_path)
    sheet_names = [s for s in xl.sheet_names if "设备柴油消耗" in s or "Техник" in s]

    if not sheet_names:
        logger.warning("未找到包含'设备柴油消耗'或'Техник'的Sheet")
        return

    engine_data_list = []
    fuel_data_list = []

    for sheet in sheet_names:
        logger.info(f"正在处理 Sheet: {sheet}")
        df_raw = xl.parse(sheet, header=None)

        try:
            start_row_idx = df_raw[df_raw.iloc[:, 0] == 1].index[0]
            start_row = start_row_idx + 1
        except IndexError:
            logger.warning(f"Sheet {sheet} 格式异常")
            continue

        # 提取表头 4 行 (日期/班组长/班次/油品)
        header_rows = df_raw.iloc[start_row - 5:start_row - 1, :].copy().astype(object)

        # 备份最原始的日期行（用于判断该列是否是Excel中真实存在的日期格）
        raw_header_date_row = header_rows.iloc[0, :].copy()
        # 填充日期和班组长
        header_rows.iloc[0, :] = header_rows.iloc[0, :].ffill()
        header_rows.iloc[1, :] = header_rows.iloc[1, :].ffill()
        header_rows.iloc[2, :] = header_rows.iloc[2, :].ffill()
        # 3. 预解析班次位置
        col_to_shift = {}
        for col_idx in range(header_rows.shape[1]):
            h4_val = clean_string(header_rows.iloc[2, col_idx])
            if "白班" in h4_val or "өдөр" in h4_val.lower():
                col_to_shift[col_idx] = "Day"
            elif "夜班" in h4_val or "шөнө" in h4_val.lower():
                col_to_shift[col_idx] = "Night"

        # 4. 识别列属性
        col_mapping = []
        stop_signal = False
        for idx in range(header_rows.shape[1]):
            if stop_signal: break

            h2 = clean_string(header_rows.iloc[0, idx])  # 日期
            h3 = clean_string(header_rows.iloc[1, idx])  # 班组/关键字
            h4 = clean_string(header_rows.iloc[2, idx])  # 小时数或班次名
            h5 = clean_string(header_rows.iloc[3, idx])  # 油品
            if "按照班子柴油准备" in h3:
                stop_signal = True
                continue

            if idx < 3:
                col_mapping.append({"type": "info", "name": f"col_{idx}"})
                continue

            if "起运小时数" in h2 or "Эхэлсэн" in h2:
                col_mapping.append({"type": "initial_start"})
                continue

            try:
                dt = pd.to_datetime(h2)
                if target_year: dt = dt.replace(year=target_year)
            except (ValueError, TypeError):
                col_mapping.append({"type": "ignore"})
                continue

            # --- 核心改进：班次识别逻辑 ---
            current_shift = resolve_shift(
                col_to_shift, idx, max_lookahead=3, num_cols=header_rows.shape[1]
            )

            data_type = None
            if "已使用小时数" in h4 or "АМЦ" in h4:
                data_type = "work_hours"
            elif "小时数" in h4 or "мц" in h4.lower():
                data_type = "end_hours"
            else:  # 燃油列
                data_type = "fuel"

            col_mapping.append({
                "type": "data",
                "date": dt,
                "shift": current_shift if current_shift else "Day",  # 默认Day防止崩溃
                "data_type": data_type,
                "fuel_type": h5 if data_type == "fuel" else None
            })

        # 5. 提取数据体
        data_body = df_raw.iloc[start_row - 1:].copy()
        for _, row in data_body.iterrows():
            device_name = row[1]
            device_id = row[2]
            device_id = clean_string(device_id)
            if not device_id: continue

            if device_name in ["HITACHI EX2600"]:
                device_name = f"{device_name} #{device_id}"
            device_name = clean_string(device_name)
            if not device_name:
                continue

            current_row_initial_val = np.nan
            shift_data_map = {}

            for idx, col_info in enumerate(col_mapping):
                if idx >= len(row): break
                val = row[idx]
                if pd.isna(val): continue

                if col_info["type"] == "initial_start":
                    current_row_initial_val = val

                elif col_info["type"] == "data":
                    dt = col_info["date"]
                    shift = col_info["shift"]
                    key = (dt, shift)

                    if col_info["data_type"] == "fuel" and not pd.isna(col_info["fuel_type"]) and col_info[
                        "fuel_type"] != "nan":
                        fuel_data_list.append({
                            "日期": dt, "班次": shift, "设备名称": device_name,
                            "设备编号": device_id, "油品种类": clean_string(col_info["fuel_type"]), "油品消耗": val
                        })
                    elif col_info["data_type"] == "end_hours":
                        if key not in shift_data_map: shift_data_map[key] = {}
                        shift_data_map[key]['end'] = val
                    elif col_info["data_type"] == "work_hours":
                        if key not in shift_data_map: shift_data_map[key] = {}
                        shift_data_map[key]['work'] = val

            # 6. 组装发动机数据（保持小时数链条连续性）
            sorted_keys = sorted(shift_data_map.keys(), key=lambda x: (x[0], 0 if x[1] == "Day" else 1))
            prev_end = current_row_initial_val

            for key in sorted_keys:
                dt, shift = key
                curr_end = shift_data_map[key].get('end', np.nan)
                curr_work = shift_data_map[key].get('work', np.nan)

                engine_data_list.append({
                    "日期": dt, "班次": shift, "设备名称": device_name, "设备编号": device_id,
                    "发动机小时数开始": prev_end, "发动机小时数结束": curr_end, "运行小时数": curr_work
                })
                prev_end = curr_end

    # 7. 导出
    shift_order = {'Day': 0, 'Night': 1}
    df_engine = pd.DataFrame()
    if engine_data_list:
        df_engine = pd.DataFrame(engine_data_list)
        df_engine['shift_rank'] = df_engine['班次'].map(shift_order)
        df_engine.sort_values(by=["日期", "shift_rank", "设备编号"], inplace=True)
        df_engine["日期"] = df_engine["日期"].dt.date
    else:
        logger.warning("没有找到任何发动机数据")

    df_fuel = pd.DataFrame()
    if fuel_data_list:
        df_fuel = pd.DataFrame(fuel_data_list)
        df_fuel['shift_rank'] = df_fuel['班次'].map(shift_order)
        df_fuel.sort_values(by=["日期", "shift_rank", "设备编号"], inplace=True)
        df_fuel["日期"] = df_fuel["日期"].dt.date
    else:
        logger.warning("没有找到任何油耗数据")

    # 如果数据都为空，那么不导出
    if df_engine.shape[0] == 0 and df_fuel.shape[0] == 0:
        logger.error("没有找到任何发动机数据和油耗数据，导出失败")
        return None

    # 清理辅助列
    if not df_engine.empty and 'shift_rank' in df_engine.columns:
        df_engine = df_engine.drop(columns=['shift_rank'])
    if not df_fuel.empty and 'shift_rank' in df_fuel.columns:
        df_fuel = df_fuel.drop(columns=['shift_rank'])

    # 去重
    df_engine = dedup_dataframe(df_engine, "设备信息")
    df_fuel = dedup_dataframe(df_fuel, "油耗信息")

    if return_sheets:
        sheets = {}
        if df_engine.shape[0] > 0:
            sheets["设备信息"] = df_engine
        if df_fuel.shape[0] > 0:
            sheets["油耗信息"] = df_fuel
        return sheets if sheets else None

    output_file = os.path.join(os.path.dirname(file_path), "Fuel.xlsx")
    with pd.ExcelWriter(output_file) as writer:
        df_engine.to_excel(writer, sheet_name="设备信息", index=False)
        df_fuel.to_excel(writer, sheet_name="油耗信息", index=False)

    logger.info(f"处理完成！文件已保存: {output_file}")


def main():
    from func.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="处理设备柴油消耗报表")
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--year", type=int, help="目标年份")
    args = parser.parse_args()
    process_diesel_data(args.input_file, args.year)


if __name__ == "__main__":
    main()
