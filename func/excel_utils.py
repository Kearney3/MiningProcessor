"""
Excel 处理共享工具函数

提供各处理器共用的 DataFrame 后处理逻辑：
- 日期列标准化（去时间、可选覆盖年份）
- 按日期+班次排序
- 工时报表 Day/Night 班次分割与清洗
"""

import pandas as pd

from func.string_utils import clean_string


def strip_date_column(
    df: pd.DataFrame,
    date_column: str = "日期",
    target_year: int | None = None,
    date_format: str | None = None,
) -> pd.DataFrame:
    """将 DataFrame 的日期列标准化为 date 对象（去除时间部分）。

    Args:
        df: 待处理的 DataFrame（原地修改）。
        date_column: 日期列名。
        target_year: 若指定，覆盖所有日期的年份。
        date_format: pd.to_datetime 的 format 参数，None 时自动推断。

    Returns:
        处理后的 DataFrame（同引用）。
    """
    if date_column not in df.columns or df.empty:
        return df

    df[date_column] = pd.to_datetime(df[date_column], format=date_format, errors="coerce")
    if target_year is not None:
        df[date_column] = df[date_column].apply(
            lambda d: d.replace(year=target_year) if pd.notna(d) else d
        )
    df[date_column] = df[date_column].dt.date
    return df


def sort_by_date_shift(
    df: pd.DataFrame,
    sort_columns: list[str] | None = None,
    kind: str = "stable",
) -> pd.DataFrame:
    """按日期和班次排序。

    Args:
        df: 待排序的 DataFrame（原地排序）。
        sort_columns: 排序列，默认 ["日期", "班次"]。
        kind: 排序算法，默认 "stable"。

    Returns:
        排序后的 DataFrame（同引用）。
    """
    if sort_columns is None:
        sort_columns = ["日期", "班次"]

    existing = [c for c in sort_columns if c in df.columns]
    if existing:
        df.sort_values(by=existing, kind=kind, inplace=True)
    return df


def split_day_night_shifts(
    df_raw: pd.DataFrame,
    header_row_index: int = 1,
    data_start_index: int = 2,
    day_end_offset: int = -1,
) -> pd.DataFrame:
    """将工时报表按 Day/Night 班次分割。

    检测 header_row 中的有效列，然后在数据行中查找与 header 首列
    相同的行作为 Day/Night 分割点。分割点之前为 Day 数据，之后为 Night 数据。

    Args:
        df_raw: 原始 DataFrame（header=None 读入）。
        header_row_index: 表头行索引，默认 1。
        data_start_index: 数据起始行索引，默认 2。
        day_end_offset: Day 数据结束位置相对 split_idx 的偏移量。
            默认 -1 表示 `df_raw.iloc[data_start:split_idx - 1]`（excel_worktime.py 行为）。
            设为 0 表示 `df_raw.iloc[data_start:split_idx]`（excel_worktime_multifile.py 行为）。

    Returns:
        合并后的 DataFrame，包含 '班次' 列（'Day' 或 'Night'）。
    """
    header_row = df_raw.iloc[header_row_index]
    valid_mask = header_row.notna() & (header_row.apply(lambda x: clean_string(x)) != "")
    valid_cols = valid_mask[valid_mask].index.tolist()
    valid_headers = header_row[valid_cols].apply(clean_string).tolist()

    split_idx = -1
    for idx in range(data_start_index, len(df_raw)):
        current_row_vals = df_raw.iloc[idx][valid_cols].apply(clean_string).tolist()
        if current_row_vals[0] == valid_headers[0]:
            split_idx = idx
            break

    if split_idx == -1:
        day_data = df_raw.iloc[data_start_index:].copy()
        day_data.columns = header_row
        day_data["班次"] = "Day"
        return day_data
    else:
        day_end = split_idx + day_end_offset
        day_data = df_raw.iloc[data_start_index:day_end].copy()
        day_data.columns = header_row
        day_data["班次"] = "Day"
        night_data = df_raw.iloc[split_idx + 1 :].copy()
        night_data.columns = header_row
        night_data["班次"] = "Night"
        return pd.concat([day_data, night_data], axis=0, ignore_index=True)


def clean_split_dataframe(
    df: pd.DataFrame,
    skip_columns: list[str] | None = None,
    check_keyword: str = "Техникийн",
) -> pd.DataFrame:
    """清洗 Day/Night 分割后的 DataFrame。

    - 移除 NaN 列
    - 移除空列名列
    - 按关键字列去空行
    - 按非元数据列全空去行

    Args:
        df: 分割后的 DataFrame（原地修改）。
        skip_columns: 不参与全空检查的列，默认 ["日期", "班次"]。
        check_keyword: 用于定位检查列的关键字。

    Returns:
        清洗后的 DataFrame（同引用）。
    """
    if skip_columns is None:
        skip_columns = ["日期", "班次"]

    # 移除 NaN 列
    df = df.loc[:, df.columns.notna()]

    # 移除空列名列
    if "" in df.columns:
        df = df.drop(columns=[""])

    # 按关键字列去空行
    if len(df.columns) > 1:
        check_idx = -1
        for idx, col in enumerate(df.columns):
            if check_keyword in col:
                check_idx = idx
                break
        if check_idx != -1:
            check_col = df.columns[check_idx]
            df.dropna(subset=[check_col], inplace=True)

    # 按非元数据列全空去行
    subset_cols = [c for c in df.columns if c not in skip_columns]
    df.dropna(how="all", subset=subset_cols, inplace=True)

    return df
