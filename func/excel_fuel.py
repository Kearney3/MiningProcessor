import argparse
import os

import pandas as pd
import numpy as np

from func.logger import get_logger
from func.string_utils import clean_string
from func.excel_utils import dedup_dataframe, resolve_shift, detect_shift, get_hidden_indices, filter_hidden_from_df, open_workbook
from func.anomaly import detect_and_filter
from func.anomaly.rules import AnomalyConfig
from func import config_loader

logger = get_logger(__name__)

# 油品品牌关键字，用于在表头行中动态定位油品品牌行
_FUEL_BRAND_KEYWORDS = frozenset({"НИК", "IC IC", "Primary"})


def _find_header_anchor(df_raw, search_limit=20):
    """在 df_raw 前 search_limit 行中查找含 "Д/д" 或 "Парк дугаар" 的行，返回 (0-based 位置, 首个数据行位置)。
    未找到时返回 None。
    """
    search_area = df_raw.iloc[:search_limit]
    for label in search_area.index:
        row_vals = search_area.loc[label].astype(str)
        if row_vals.str.contains("Д/д", na=False).any() or row_vals.str.contains("Парк дугаар", na=False).any():
            anchor_pos = df_raw.index.get_loc(label)
            # 首个数据行：anchor 之后第一个 col[0] 可转为数字的行
            for after_label in df_raw.index[anchor_pos + 1:]:
                after_pos = df_raw.index.get_loc(after_label)
                val = df_raw.iloc[after_pos, 0]
                if pd.notna(val):
                    try:
                        float(val)
                        return anchor_pos, after_pos
                    except (ValueError, TypeError):
                        pass
            return anchor_pos, anchor_pos + 1
    return None


def _find_date_row(header_rows):
    """在 header_rows 中动态查找日期行，返回 (行位置, 日期列位置列表)。
    遍历每行，找首个含可解析日期的行。
    """
    for row_idx in range(header_rows.shape[0]):
        date_positions = []
        for col_idx in range(header_rows.shape[1]):
            val = header_rows.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    pd.to_datetime(val)
                    date_positions.append(col_idx)
                except (ValueError, TypeError):
                    pass
        if date_positions:
            return row_idx, date_positions
    return -1, []


def _find_fuel_brand_row(header_rows):
    """在 header_rows 中查找油品品牌行（含 НИК/IC IC/Primary 的行），返回行位置或 -1。"""
    for row_idx in range(header_rows.shape[0]):
        row_vals = [clean_string(header_rows.iloc[row_idx, c]) for c in range(min(9, header_rows.shape[1]))]
        if row_vals[6:9] and any(any(kw in v for kw in _FUEL_BRAND_KEYWORDS) for v in row_vals[6:9] if v):
            return row_idx
    # 后备：在所有行中搜索品牌关键字
    for row_idx in range(header_rows.shape[0]):
        for col_idx in range(header_rows.shape[1]):
            cv = clean_string(header_rows.iloc[row_idx, col_idx])
            if cv and any(kw in cv for kw in _FUEL_BRAND_KEYWORDS):
                return row_idx
    return -1


def process_diesel_data(file_path, target_year=None, return_sheets=False, skip_hidden=False,
                        skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None,
                        filter_zero_engine_hours=False, filter_zero_work_hours=False):
    """处理设备柴油消耗报表，提取发动机与油耗数据。

    Args:
        file_path: Excel 文件路径。
        target_year: 覆盖日期年份，None 时使用原始年份。
        return_sheets: 若为 True，返回 {sheet_name: DataFrame} 字典而非写入文件。
        skip_hidden: 向后兼容，True 时等价于 skip_hidden_rows=True, skip_hidden_cols=True。
        skip_hidden_rows: 若为 True，跳过 Excel 中的隐藏行。
        skip_hidden_cols: 若为 True，跳过 Excel 中的隐藏列。
        filter_zero_engine_hours: 若为 True，过滤掉发动机小时数为 0 或为空的记录。
        filter_zero_work_hours: 若为 True，过滤掉运行小时数为 0 或为空的记录。

    Returns:
        当 return_sheets=False 时返回输出文件路径 (str)；
        当 return_sheets=True 且有数据时返回 sheets 字典；
        当 return_sheets=True 且无数据时返回 None。

    Raises:
        ValueError: 未找到匹配的柴油消耗 Sheet，或 Sheet 中无有效数据。
    """
    if skip_hidden:
        skip_hidden_rows = True
        skip_hidden_cols = True
    need_hidden = skip_hidden_rows or skip_hidden_cols
    with pd.ExcelFile(file_path) as xl:
        sheet_names = [s for s in xl.sheet_names if "设备柴油消耗" in s or "Техник" in s]

        if not sheet_names:
            raise ValueError("未找到匹配的柴油消耗Sheet（需包含'设备柴油消耗'或'Техник'）")

        engine_data_list = []
        fuel_data_list = []

        # 需要检测隐藏属性时预先加载 workbook，避免每个 sheet 重复 load_workbook
        hidden_wb = open_workbook(file_path) if need_hidden else None
        try:
            for sheet in sheet_names:
                logger.info(f"正在处理 Sheet: {sheet}")
                df_raw = xl.parse(sheet, header=None)

                if need_hidden:
                    h_rows, h_cols = get_hidden_indices(file_path, sheet, _workbook=hidden_wb)
                    df_raw = filter_hidden_from_df(
                        df_raw,
                        h_rows if skip_hidden_rows else set(),
                        h_cols if skip_hidden_cols else set(),
                    )

                # 动态定位表头（参考生产记录模块）
                anchor = _find_header_anchor(df_raw)
                if anchor is not None:
                    _anchor_pos, data_start_pos = anchor
                    header_rows = df_raw.iloc[:data_start_pos].copy().astype(object)
                    if header_rows.shape[0] < 4:
                        logger.warning(f"Sheet {sheet} 表头行数不足（{header_rows.shape[0]}），跳过")
                        continue
                    start_row = data_start_pos + 1
                else:
                    # 后备：沿用旧逻辑（col[0] == 1）
                    try:
                        start_row_pos = df_raw.index.get_loc(df_raw[df_raw.iloc[:, 0] == 1].index[0])
                        start_row = start_row_pos + 1
                    except IndexError:
                        logger.warning(f"Sheet {sheet} 格式异常")
                        continue
                    if start_row < 6:
                        logger.warning(f"Sheet {sheet} 行数不足（start_row={start_row}），跳过")
                        continue
                    header_rows = df_raw.iloc[start_row - 5:start_row - 1, :].copy().astype(object)

                # 动态查找日期行和油品品牌行
                _date_row_idx, _date_positions = _find_date_row(header_rows)
                _fuel_brand_row_idx = _find_fuel_brand_row(header_rows)

                # 备份最原始的日期行（用于判断该列是否是Excel中真实存在的日期格）
                raw_header_date_row = header_rows.iloc[_date_row_idx if _date_row_idx >= 0 else 0, :].copy()

                # 日期行：按日期块 ffill（不跨越日期头边界，不延伸到汇总列）
                if _date_positions:
                    _dr = header_rows.iloc[_date_row_idx, :].copy()
                    _first = _date_positions[0]
                    # 首个日期之前的区域：向前填充（让 initial_start 列继承首个日期值，后续再通过位置判断类型）
                    _dr.iloc[:_first] = _dr.iloc[:_first].ffill()
                    # 日期头之间的区间做局部 ffill
                    for _i in range(len(_date_positions) - 1):
                        _s, _e = _date_positions[_i], _date_positions[_i + 1]
                        _dr.iloc[_s:_e] = _dr.iloc[_s:_e].ffill()
                    # 最后一个日期头：只填充到该日期块结束，不延伸到后面的汇总列
                    if len(_date_positions) >= 2:
                        _block_w = _date_positions[-1] - _date_positions[-2]
                    else:
                        _block_w = 12  # 典型日期块宽度
                    _last_end = _date_positions[-1] + _block_w
                    _dr.iloc[_date_positions[-1]:_last_end] = _dr.iloc[_date_positions[-1]:_last_end].ffill()
                    header_rows.iloc[_date_row_idx, :] = _dr
                else:
                    header_rows.iloc[0, :] = header_rows.iloc[0, :].ffill()

                # 班组长行 ffill（紧跟日期行的下一行）
                _leader_row_idx = _date_row_idx + 1 if _date_row_idx >= 0 else 1
                if _leader_row_idx < header_rows.shape[0]:
                    header_rows.iloc[_leader_row_idx, :] = header_rows.iloc[_leader_row_idx, :].ffill()

                # 班次行 ffill
                _shift_row_idx = _date_row_idx + 2 if _date_row_idx >= 0 else 2
                if _shift_row_idx < header_rows.shape[0]:
                    header_rows.iloc[_shift_row_idx, :] = header_rows.iloc[_shift_row_idx, :].ffill()
                # 3. 预解析班次位置（扫描所有表头行，而非固定第3行）
                col_to_shift = {}
                for col_idx in range(header_rows.shape[1]):
                    for _ri in range(header_rows.shape[0]):
                        h_val = clean_string(header_rows.iloc[_ri, col_idx])
                        shift = detect_shift(h_val)
                        if shift:
                            col_to_shift[col_idx] = shift
                            break

                # 4. 识别列属性
                col_mapping = []
                stop_signal = False
                for idx in range(header_rows.shape[1]):
                    if stop_signal: break

                    h2 = clean_string(header_rows.iloc[_date_row_idx, idx]) if _date_row_idx >= 0 else ""
                    h3 = clean_string(header_rows.iloc[_shift_row_idx, idx]) if _shift_row_idx < header_rows.shape[0] else ""
                    h5 = clean_string(header_rows.iloc[_fuel_brand_row_idx, idx]) if _fuel_brand_row_idx >= 0 else ""
                    if "按照班子柴油准备" in h3 or "Түлш зэхэлт" in h3 or "Нийт" in h3:
                        stop_signal = True
                        continue
                    # 防御性检查：汇总区标题可能在 shift 行上方一行（如 "Түлш зэхэлт ээлжээр"）
                    if _shift_row_idx > 0:
                        h_above = clean_string(header_rows.iloc[_shift_row_idx - 1, idx])
                        if "Түлш зэхэлт" in h_above or "按照班子柴油准备" in h_above:
                            stop_signal = True
                            continue

                    if idx < 3:
                        col_mapping.append({"type": "info", "name": f"col_{idx}"})
                        continue

                    if "起运小时数" in h2 or "Эхэлсэн" in h2 or (idx < _date_positions[0] if _date_positions else False):
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
                    if "已使用小时数" in h3 or "АМЦ" in h3:
                        data_type = "work_hours"
                    elif "小时数" in h3 or "мц" in h3.lower() or "мотоцаг" in h3.lower():
                        data_type = "end_hours"
                    else:  # 燃油列
                        data_type = "fuel"

                    # 燃油类型：优先从品牌行取，否则扫描所有表头行
                    _fuel_type = None
                    if data_type == "fuel":
                        _fuel_type = h5 if h5 else None
                        if not _fuel_type:
                            _fuel_keywords = ("柴油", "Бензин", "Түлш", "NIK", "Primary")
                            for _ri in range(header_rows.shape[0]):
                                if _ri == _date_row_idx:
                                    continue  # 日期行不含油品
                                _candidate = clean_string(header_rows.iloc[_ri, idx])
                                if _candidate and any(k in _candidate for k in _fuel_keywords):
                                    _fuel_type = next(k for k in _fuel_keywords if k in _candidate)
                                    break

                    col_mapping.append({
                        "type": "data",
                        "date": dt,
                        "shift": current_shift if current_shift else "Day",  # 默认Day防止崩溃
                        "data_type": data_type,
                        "fuel_type": _fuel_type
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

                            if col_info["data_type"] == "fuel" and col_info["fuel_type"]:
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
        finally:
            if hidden_wb is not None:
                hidden_wb.close()

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
        raise ValueError("柴油消耗表中未找到有效数据（发动机数据和油耗数据均为空）")

    # 清理辅助列
    if not df_engine.empty and 'shift_rank' in df_engine.columns:
        df_engine = df_engine.drop(columns=['shift_rank'])
    if not df_fuel.empty and 'shift_rank' in df_fuel.columns:
        df_fuel = df_fuel.drop(columns=['shift_rank'])

    # 过滤发动机小时数为 0 或为空的记录
    if filter_zero_engine_hours and not df_engine.empty:
        start = df_engine["发动机小时数开始"]
        end = df_engine["发动机小时数结束"]
        mask = (start.fillna(0) == 0) | (end.fillna(0) == 0)
        filtered_count = mask.sum()
        if filtered_count > 0:
            df_engine = df_engine[~mask]
            logger.info(f"已过滤 {filtered_count} 条发动机小时数为 0 或为空的记录")

    # 过滤运行小时数为 0 或为空的记录
    if filter_zero_work_hours and not df_engine.empty:
        work = df_engine["运行小时数"]
        mask = work.fillna(0) == 0
        filtered_count = mask.sum()
        if filtered_count > 0:
            df_engine = df_engine[~mask]
            logger.info(f"已过滤 {filtered_count} 条运行小时数为 0 或为空的记录")

    # 去重
    df_engine = dedup_dataframe(df_engine, "设备信息")
    df_fuel = dedup_dataframe(df_fuel, "油耗信息")

    # 异常值检测
    output_dir = os.path.dirname(file_path)
    if anomaly_config is None:
        anomaly_config = AnomalyConfig.from_config(config_loader.get_anomaly_detection_config())
    if anomaly_config.enabled:
        df_engine, _ = detect_and_filter(
            df_engine, "fuel_engine", anomaly_config, output_dir=output_dir)
        df_fuel, _ = detect_and_filter(
            df_fuel, "fuel", anomaly_config, output_dir=output_dir)

    if return_sheets:
        sheets = {}
        if df_engine.shape[0] > 0:
            sheets["设备信息"] = df_engine
        if df_fuel.shape[0] > 0:
            sheets["油耗信息"] = df_fuel
        return sheets if sheets else None

    from func.excel_formatter import write_formatted_excel

    output_file = os.path.join(os.path.dirname(file_path), "Fuel.xlsx")
    write_formatted_excel(output_file, {"设备信息": df_engine, "油耗信息": df_fuel})

    logger.info(f"处理完成！文件已保存: {output_file}")
    return output_file


def main():
    from func.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="处理设备柴油消耗报表")
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--year", type=int, help="目标年份")
    parser.add_argument("--skiphidden", action="store_true",
                        help="跳过 Excel 中的隐藏行和隐藏列（向后兼容）")
    parser.add_argument("--skip-hidden-rows", action="store_true", help="跳过 Excel 中的隐藏行")
    parser.add_argument("--skip-hidden-cols", action="store_true", help="跳过 Excel 中的隐藏列")
    args = parser.parse_args()
    process_diesel_data(args.input_file, args.year,
                        skip_hidden=args.skiphidden,
                        skip_hidden_rows=args.skip_hidden_rows,
                        skip_hidden_cols=args.skip_hidden_cols)


# 统一命名别名（L-01）
process_fuel_data = process_diesel_data


if __name__ == "__main__":
    main()
