import argparse
import os
import pandas as pd
import numpy as np


def process_diesel_data(file_path, target_year=None):
    xl = pd.ExcelFile(file_path)
    sheet_names = [s for s in xl.sheet_names if "设备柴油消耗" in s]

    if not sheet_names:
        print("未找到包含'设备柴油消耗'的Sheet")
        return

    engine_data_list = []
    fuel_data_list = []

    for sheet in sheet_names:
        print(f"正在处理 Sheet: {sheet}")
        df_raw = xl.parse(sheet, header=None)

        try:
            start_row_idx = df_raw[df_raw.iloc[:, 0] == 1].index[0]
            start_row = start_row_idx + 1
        except IndexError:
            print(f"Sheet {sheet} 格式异常")
            continue

        # 2. 处理表头
        # # 我们只对日期(h2)和班组长(h3)进行向右填充
        # # 对h4(小时数/班次行)需要特殊处理
        # header_rows = df_raw.iloc[start_row - 5:start_row - 1, :].copy()
        # header_rows.iloc[0, :] = header_rows.iloc[0, :].ffill()  # 日期填充
        # header_rows.iloc[1, :] = header_rows.iloc[1, :].ffill()  # 班组长填充

        # 提取表头 4 行 (日期/班组长/班次/油品)
        header_rows = df_raw.iloc[start_row - 5:start_row - 1, :].copy().astype(object)

        # 备份最原始的日期行（用于判断该列是否是Excel中真实存在的日期格）
        raw_header_date_row = header_rows.iloc[0, :].copy()
        # 填充日期和班组长
        header_rows.iloc[0, :] = header_rows.iloc[0, :].ffill()
        header_rows.iloc[1, :] = header_rows.iloc[1, :].ffill()
        # 3. 预解析班次位置
        col_to_shift = {}
        for col_idx in range(header_rows.shape[1]):
            h4_val = str(header_rows.iloc[2, col_idx]).strip()
            if "白班" in h4_val or "өдөр" in h4_val.lower():
                col_to_shift[col_idx] = "Day"
            elif "夜班" in h4_val or "шөнө" in h4_val.lower():
                col_to_shift[col_idx] = "Night"

        # 3. 预解析班次位置
        # 建立一个列索引到班次的映射
        col_to_shift = {}
        for col_idx in range(header_rows.shape[1]):
            h4_val = str(header_rows.iloc[2, col_idx]).strip()
            if "白班" in h4_val or "өдөр" in h4_val.lower():
                col_to_shift[col_idx] = "Day"
            elif "夜班" in h4_val or "шөнө" in h4_val.lower():
                col_to_shift[col_idx] = "Night"

        # 4. 识别列属性
        col_mapping = []
        stop_signal = False

        for idx in range(header_rows.shape[1]):
            if stop_signal: break

            h2 = str(header_rows.iloc[0, idx]).strip()  # 日期
            h3 = str(header_rows.iloc[1, idx]).strip()  # 班组/关键字
            h4 = str(header_rows.iloc[2, idx]).strip()  # 小时数或班次名
            h5 = str(header_rows.iloc[3, idx]).strip()  # 油品

            if "按照班子柴油准备" in h3:
                stop_signal = True
                continue

            if idx < 3:
                col_mapping.append({"type": "info", "name": f"col_{idx}"})
                continue

            if "起运小时数" in h2 or "Начальный" in h2:
                col_mapping.append({"type": "initial_start"})
                continue

            try:
                dt = pd.to_datetime(h2)
                if target_year: dt = dt.replace(year=target_year)
            except:
                col_mapping.append({"type": "ignore"})
                continue

            # --- 核心改进：班次识别逻辑 ---
            current_shift = None

            # 如果当前列标题直接写了班次（通常是燃油列）
            if idx in col_to_shift:
                current_shift = col_to_shift[idx]
            else:
                # 如果当前是小时数列，班次在右边，我们需要向右寻找最近的班次标识
                # 寻找范围设为往后看 3 列
                for search_idx in range(idx, min(idx + 3, header_rows.shape[1])):
                    if search_idx in col_to_shift:
                        current_shift = col_to_shift[search_idx]
                        break

            # 如果实在没找到，尝试向前看（ffill效果）
            if not current_shift:
                for search_idx in range(idx, 2, -1):
                    if search_idx in col_to_shift:
                        current_shift = col_to_shift[search_idx]
                        break

            data_type = None
            if "已使用小时数" in h4 or "АМЦ" in h4:
                data_type = "work_hours"
            elif "小时数" in h4 or "мц" in h4.lower():
                data_type = "end_hours"
            elif "/" in h5 or (idx in col_to_shift):  # 燃油列
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
            if pd.isna(device_id) or str(device_id).strip() == "": continue

            if device_name in ["HITACHI EX2600"]:
                device_name = f"{device_name} #{device_id}"

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

                    if col_info["data_type"] == "fuel":
                        fuel_data_list.append({
                            "日期": dt, "班次": shift, "设备名称": device_name,
                            "设备编号": device_id, "油品种类": col_info["fuel_type"], "油品消耗": val
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
    if not engine_data_list: return

    df_engine = pd.DataFrame(engine_data_list)
    shift_order = {'Day': 0, 'Night': 1}
    df_engine['shift_rank'] = df_engine['班次'].map(shift_order)
    df_engine.sort_values(by=["日期", "shift_rank", "设备编号"], inplace=True)
    df_engine["日期"] = df_engine["日期"].dt.date

    df_fuel = pd.DataFrame(fuel_data_list)
    df_fuel['shift_rank'] = df_fuel['班次'].map(shift_order)
    df_fuel.sort_values(by=["日期", "shift_rank", "设备编号"], inplace=True)
    df_fuel["日期"] = df_fuel["日期"].dt.date

    output_file = os.path.join(os.path.dirname(file_path), "Fuel.xlsx")
    with pd.ExcelWriter(output_file) as writer:
        df_engine.drop(columns=['shift_rank']).to_excel(writer, sheet_name="设备信息", index=False)
        df_fuel.drop(columns=['shift_rank']).to_excel(writer, sheet_name="油耗信息", index=False)

    print(f"处理完成！文件已保存: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--year", type=int)
    args = parser.parse_args()
    process_diesel_data(args.input_file, args.year)