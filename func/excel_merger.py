import argparse
import json
import os
import sys
from typing import List, Tuple

import pandas as pd
from func.logger import get_logger

logger = get_logger(__name__)


def find_first_datetime_column(df: pd.DataFrame) -> str | None:
    """找到 DataFrame 中第一个可解析为日期时间的列，返回列名或 None"""
    for col in df.columns:
        series = df[col]
        # 跳过完全为空的列
        if series.notna().sum() == 0:
            continue
        # 跳过纯数值列（整数/浮点），避免小整数被误判为纳秒时间戳
        if pd.api.types.is_numeric_dtype(series):
            continue
        # 采样前 5 个非空值做检测，避免全列转换的性能开销
        sample = series.dropna().head(5)
        if sample.empty:
            continue
        try:
            converted = pd.to_datetime(sample, errors="coerce")
            if converted.notna().sum() > 0:
                return col
        except (ValueError, TypeError):
            continue
    return None


def merge_excel_files(
        folder_path: str,
        keyword: str,
        output_file: str | None = None,
        strip_time: bool = False,
        sort_configs: List[dict] | None = None,
) -> str:
    """
    合并指定文件夹中包含关键字的 Excel 文件。

    参数:
        folder_path: 要扫描的文件夹路径
        keyword: 文件名需包含的关键字
        output_file: 输出文件路径（可选，默认在 folder_path 下生成）
        strip_time: 为 True 时，第一个时间列仅保留日期部分（YYYY-MM-DD）
        sort_configs: 排序配置列表，如 [{"column": "日期", "ascending": True}, ...]
                      提供时优先使用，不再自动按日期排序

    返回:
        输出文件的完整路径
    """
    # 1. 收集匹配的 Excel 文件
    matched_files: List[str] = []
    # 预设的输出文件名（用于自我排除）
    expected_output_name = f"{keyword}_合并.xlsx"
    for fname in sorted(os.listdir(folder_path)):
        lower = fname.lower()
        if lower.endswith("_合并.xlsx"):
            continue  # 排除已生成的合并文件
        if keyword.lower() in lower and (lower.endswith(".xlsx") or lower.endswith(".xls")):
            matched_files.append(os.path.join(folder_path, fname))

    if not matched_files:
        raise FileNotFoundError(
            f"在 '{folder_path}' 中未找到包含关键字 '{keyword}' 的 Excel 文件"
        )

    logger.info(f"找到 {len(matched_files)} 个匹配文件:")
    for f in matched_files:
        logger.info(f"  - {os.path.basename(f)}")

    # 2. 第一遍扫描：只收集 sheet 名和表头（轻量，不加载数据）
    all_sheet_names: set[str] = set()
    header_dict: dict = {}
    file_sheet_names: dict[str, list[str]] = {}  # file -> [sheet_names]

    for fpath in matched_files:
        xl = pd.ExcelFile(fpath)
        header_dict[os.path.basename(fpath)] = {}
        file_sheet_names[fpath] = []
        for sname in xl.sheet_names:
            all_sheet_names.add(sname)
            file_sheet_names[fpath].append(sname)
            try:
                df_head = pd.read_excel(xl, sheet_name=sname, nrows=0)
                header_dict[os.path.basename(fpath)][sname] = tuple(str(h) for h in df_head.columns)
            except (ValueError, KeyError) as e:
                logger.error(f"读取文件 '{fpath}' 的 Sheet '{sname}' 表头失败: {e}")
                header_dict[os.path.basename(fpath)][sname] = ()

    # 3. 按 sheet_name 逐组合并（逐文件读取，避免同时缓存所有文件数据）
    merged_sheets: dict[str, pd.DataFrame] = {}
    for sname in sorted(all_sheet_names):
        sheet_dataframes: List[pd.DataFrame] = []
        expected_headers: Tuple | None = None

        for fpath in matched_files:
            if sname not in file_sheet_names.get(fpath, []):
                logger.warning(f"  警告: {os.path.basename(fpath)} 缺少 Sheet '{sname}'，已跳过")
                continue

            # 逐文件读取，用完即弃，不缓存
            try:
                df = pd.read_excel(fpath, sheet_name=sname)
            except (ValueError, KeyError, FileNotFoundError) as e:
                logger.error(f"读取文件 '{fpath}' 的 Sheet '{sname}' 失败: {e}")
                continue

            if df.empty:
                logger.warning(f"  警告: {os.path.basename(fpath)} 的 Sheet '{sname}' 为空，已跳过")
                continue

            current_headers = tuple(str(h) for h in df.columns)
            if expected_headers is None:
                expected_headers = current_headers
            else:
                if current_headers != expected_headers:
                    # 格式化输出所有文件的表名和对应的表头（header_dict）
                    error_string = ""
                    # 遍历外层字典
                    for outer_key, inner_dict in header_dict.items():
                        error_string += f"【{outer_key}】\n"
                        # 遍历内层字典
                        for inner_key, value_tuple in inner_dict.items():
                            error_string += f"  {inner_key}: {value_tuple}\t"
                        error_string += f"\n-{'-' * 30}\n"  # 分隔线

                    raise ValueError(
                        f"Sheet '{sname}' 的表头不一致！\n"
                        f"  期望: {expected_headers}\n"
                        f"  实际 ({os.path.basename(fpath)}): {current_headers}\n"
                        f"请检查并修正后再合并。"
                        f"  所有已导入的表头: \n{error_string}"
                    )

            # 去掉空行/全空行（可选，保留原样更稳妥，只在非首表时去掉表头）
            sheet_dataframes.append(df)

        if not sheet_dataframes:
            logger.warning(f"Sheet '{sname}' 无有效数据，跳过")
            continue

        # 合并：第一个保留表头，其余直接拼接
        merged_df = pd.concat(sheet_dataframes, ignore_index=True)

        # 4. 排序处理
        if sort_configs:
            # 使用用户配置的排序规则
            sort_columns = []
            sort_ascending = []
            for cfg in sort_configs:
                col = cfg.get("column", "").strip()
                asc = bool(cfg.get("ascending", True))
                if not col:
                    continue
                if col not in merged_df.columns:
                    logger.warning(f"  警告: Sheet '{sname}' 中不存在列 '{col}'，跳过该排序条件")
                    continue
                sort_columns.append(col)
                sort_ascending.append(asc)

            if sort_columns:
                logger.info(
                    f"Sheet '{sname}' 正在按以下规则排序: {list(zip(sort_columns, ['升序' if a else '降序' for a in sort_ascending]))}")
                try:
                    merged_df = merged_df.sort_values(by=sort_columns, ascending=sort_ascending,
                                                      na_position="last").reset_index(drop=True)
                except (TypeError, ValueError) as e:
                    logger.error(f"Sheet '{sname}' 排序时出错: {e}")
            else:
                logger.warning(f"Sheet '{sname}' 无可用的排序条件，跳过排序")
        else:
            # 默认：自动识别第一个时间列并升序排序
            time_col = find_first_datetime_column(merged_df)
            if time_col:
                logger.info(f"Sheet '{sname}' 识别到时间列: '{time_col}'，正在按时间升序排序...")
                merged_df[time_col] = pd.to_datetime(merged_df[time_col], errors="coerce")
                merged_df = merged_df.sort_values(by=time_col, na_position="last").reset_index(drop=True)
            else:
                logger.warning(f"Sheet '{sname}' 未识别到时间列，跳过排序")

        # 5. 仅保留日期（独立于排序逻辑）
        if strip_time:
            time_col = find_first_datetime_column(merged_df)
            if time_col:
                merged_df[time_col] = pd.to_datetime(merged_df[time_col], errors="coerce")
                merged_df[time_col] = merged_df[time_col].dt.date
                logger.info(f"Sheet '{sname}' 时间列 '{time_col}' 已格式化为日期（YYYY-MM-DD）")
            else:
                logger.warning(f"Sheet '{sname}' 未识别到时间列，跳过日期格式化")

        merged_sheets[sname] = merged_df

    # 5. 输出文件
    if output_file is None:
        output_file = os.path.join(folder_path, f"{keyword}_合并.xlsx")

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sname, df in merged_sheets.items():
            df.to_excel(writer, sheet_name=sname, index=False)

    logger.info(f"\n合并完成！输出文件: {output_file}")
    return output_file


def main():
    try:
        from func.logger import setup_logging
        setup_logging()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="合并包含相同关键字的多个 Excel 文件")
    parser.add_argument("folder", help="要扫描的文件夹路径")
    parser.add_argument("keyword", help="文件名需包含的关键字")
    parser.add_argument("-o", "--output", help="输出文件路径（可选）")
    parser.add_argument("-s", "--strip-time", action="store_true", help="时间列仅保留日期（YYYY-MM-DD）")
    parser.add_argument("--sort", type=str, default=None, help='排序规则 JSON，如: [{"column":"日期","ascending":true}]')
    args = parser.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        logger.error(f"错误: '{folder}' 不是有效的文件夹路径")
        sys.exit(1)

    try:
        sort_configs = None
        if args.sort:
            try:
                sort_configs = json.loads(args.sort)
                if not isinstance(sort_configs, list):
                    raise ValueError("排序规则必须是列表")
            except Exception as e:
                logger.error(f"错误: 排序规则 JSON 解析失败: {e}")
                sys.exit(1)
        merge_excel_files(folder, args.keyword, args.output, strip_time=args.strip_time, sort_configs=sort_configs)
    except Exception as e:
        logger.error(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    from func.logger import setup_logging

    setup_logging()
    main()
