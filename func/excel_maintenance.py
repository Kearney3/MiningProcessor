"""维修记录处理主模块

从设备出勤统计表的单元格批注中提取维修记录，经台账匹配和故障分类后，
生成包含 10 个统计 sheet 的 Excel 报告。

支持单文件和文件夹批量处理，年月从文件名/表名自动解析。
"""
import argparse
import os

from func.building import build_sheets
from func.extraction import extract_all_records
from func.logger import get_logger, setup_logging
from func.maintenance_classification import (
    classify,
    compile_noise_patterns,
    get_default_classifications,
    is_fault_record,
)
from func.maintenance_utils import (
    extract_device_model,
    preprocess_device_name,
)
from func.writer import write_excel


# 向后兼容：重新导出子模块的公开 API
__all__ = [
    "extract_all_records",
    "process_maintenance_data",
]

logger = get_logger(__name__)


# ── 主处理入口 ────────────────────────────────────────────────

def process_maintenance_data(
    file_path: str,
    *,
    eq_ledger=None,
    classifications: dict | None = None,
    file_keywords: list[str] | None = None,
    skip_hidden_rows: bool = False,
    skip_hidden_cols: bool = False,
    return_sheets: bool = False,
    split_by_year: bool = False,
) -> str | list[str] | dict:
    """维修记录处理统一入口。

    流程: 提取 → 预处理 → 台账匹配 → 分类 → 构建 DataFrame → 输出 Excel。

    Args:
        file_path: 输入文件或文件夹路径。
        eq_ledger: EquipmentLedger 实例（可选）。
        classifications: 分类配置 dict（None 时从 config 加载或使用默认值）。
        file_keywords: 文件名关键字（None 时从 config 加载）。
        skip_hidden_rows: 跳过隐藏行。
        skip_hidden_cols: 跳过隐藏列。
        return_sheets: True 时返回 dict[str, DataFrame]，False 时写文件。
        split_by_year: True 时按年份拆分输出为多个文件。

    Returns:
        输出文件路径（str）、文件路径列表（split_by_year=True）或 sheets 字典。
    """
    if not file_path or not os.path.exists(file_path):
        raise ValueError(f"输入路径不存在: {file_path}")

    # 加载配置
    if classifications is None:
        classifications = get_default_classifications()
    if file_keywords is None:
        try:
            from func.config_loader import get_maintenance_file_keywords
            file_keywords = get_maintenance_file_keywords()
        except Exception:
            file_keywords = ["设备出勤统计表"]

    class_rules = classifications.get("classifications", [])
    noise_exact = classifications.get("noise_exact", set())
    noise_patterns = classifications.get("noise_patterns", [])
    reason_rules = classifications.get("reason_rules", {})

    # 预编译噪声正则（编译一次，复用于所有记录）
    compiled_noise = compile_noise_patterns(noise_patterns)

    # 1. 提取记录
    raw_records = extract_all_records(
        file_path, file_keywords,
        skip_hidden_rows=skip_hidden_rows,
        skip_hidden_cols=skip_hidden_cols,
    )
    if not raw_records:
        msg = "未提取到任何维修记录"
        logger.warning(msg)
        if return_sheets:
            return {}
        raise ValueError(msg)

    # 1b. 基于原始日期 + 原始设备名称 + 原始维修工时 + 原始批注去重
    seen: set[tuple] = set()
    deduped: list[dict] = []
    dup_count = 0
    for rec in raw_records:
        key = (rec["日期"], rec["原始设备名称"], rec["工时_分钟"], rec["维修内容"])
        # 处理可能不可哈希的类型
        try:
            if key in seen:
                dup_count += 1
                continue
            seen.add(key)
        except TypeError:
            pass  # 遇到不可哈希值时保留该记录
        deduped.append(rec)
    if dup_count:
        logger.warning("去重: 移除 %d 条重复记录, 保留 %d 条", dup_count, len(deduped))
    raw_records = deduped

    # 2. 预处理 + 台账匹配 + 分类
    classified: list[dict] = []
    fault_records: list[dict] = []
    matched_count = 0
    unmatched_names: set[str] = set()

    for rec in raw_records:
        # 预处理设备名
        raw_name = preprocess_device_name(rec["原始设备名称"])
        std_name = raw_name
        match_method = ""

        # 台账匹配
        if eq_ledger and raw_name:
            result = eq_ledger.match(raw_name)
            if result:
                std_name = result["标准名称"]
                match_method = result["匹配方式"]
                matched_count += 1
            else:
                unmatched_names.add(raw_name)

        model = extract_device_model(std_name) if std_name else ""

        # 故障判定（使用预编译正则）
        is_fault = is_fault_record(
            rec["原因"], rec["维修内容"],
            noise_exact=noise_exact,
            compiled_noise=compiled_noise,
            reason_rules=reason_rules,
        )

        # 分类（使用预编译正则）
        major, minor = (None, None)
        if is_fault:
            major, minor = classify(
                rec["维修内容"],
                classifications=class_rules,
                noise_exact=noise_exact,
                compiled_noise=compiled_noise,
            )

        classified_rec = {
            "日期": rec["日期"],
            "原始设备名称": raw_name,
            "标准设备名称": std_name,
            "设备型号": model,
            "原因": rec["原因"],
            "班次": rec["班次"],
            "大类": major,
            "小类": minor,
            "是否故障": "是" if is_fault else "否",
            "维修内容": rec["维修内容"],
            "工时_分钟": rec["工时_分钟"],
        }
        classified.append(classified_rec)
        if is_fault and major is not None:
            fault_records.append(classified_rec)

    logger.info("分类完成: 总 %d 条, 故障 %d 条, 台账匹配 %d 条",
                len(classified), len(fault_records), matched_count)
    if unmatched_names:
        logger.warning("未匹配设备名 %d 个: %s", len(unmatched_names),
                       ", ".join(sorted(unmatched_names)[:10]))

    # 3. 构建统计 DataFrame
    sheets = build_sheets(classified, fault_records)

    # 4. 输出
    if return_sheets:
        return sheets

    output_dir = file_path if os.path.isdir(file_path) else os.path.dirname(file_path) or "."

    if split_by_year:
        output_files = _write_split_by_year(output_dir, classified, fault_records)
        return output_files

    output_file = os.path.join(output_dir, "维修记录统计.xlsx")
    write_excel(output_file, sheets)
    logger.info("输出完成: %s", output_file)
    return output_file


# ── 按年份拆分输出 ───────────────────────────────────────────

def _write_split_by_year(
    output_dir: str,
    classified: list[dict],
    fault_records: list[dict],
) -> list[str]:
    """按年份拆分输出为多个 Excel 文件。

    每个年份生成一个独立文件，另外生成一个汇总文件。
    汇总文件额外包含大类×年月和设备名称×原因两个跨年统计 sheet。

    Returns:
        输出文件路径列表。
    """
    from collections import defaultdict

    # 按年分组
    year_classified: dict[int, list] = defaultdict(list)
    year_faults: dict[int, list] = defaultdict(list)
    for rec in classified:
        if rec["日期"]:
            year_classified[rec["日期"].year].append(rec)
    for rec in fault_records:
        if rec["日期"]:
            year_faults[rec["日期"].year].append(rec)

    output_files: list[str] = []

    # 每年一个文件
    for year in sorted(year_classified.keys()):
        sheets = build_sheets(year_classified[year], year_faults.get(year, []))
        output_file = os.path.join(output_dir, f"维修记录统计_{year}年.xlsx")
        write_excel(output_file, sheets)
        output_files.append(output_file)
        logger.info("输出完成 (%d年): %s (%d 条)", year, output_file, len(year_classified[year]))

    # 汇总文件
    all_sheets = build_sheets(classified, fault_records)
    summary_file = os.path.join(output_dir, "维修记录统计_汇总.xlsx")
    write_excel(summary_file, all_sheets)
    output_files.append(summary_file)
    logger.info("汇总输出完成: %s (%d 条)", summary_file, len(classified))

    return output_files


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="维修记录处理：从出勤统计表提取维修记录并生成统计报告")
    parser.add_argument("input_path", help="输入文件或文件夹路径")
    parser.add_argument("--ledger", help="设备台账 Excel 文件路径", default=None)
    parser.add_argument("--config", help="维修分类配置 Excel 文件路径", default=None)
    parser.add_argument("--skip-hidden-rows", action="store_true", help="跳过隐藏行")
    parser.add_argument("--skip-hidden-cols", action="store_true", help="跳过隐藏列")
    args = parser.parse_args()

    setup_logging()

    # 加载分类配置
    classifications = None
    if args.config:
        from func.maintenance_classification import import_classifications_from_excel
        classifications = import_classifications_from_excel(args.config)
        logger.info("使用自定义分类配置: %s", args.config)

    # 加载台账
    eq_ledger = None
    if args.ledger:
        from func.equipment_ledger import EquipmentLedger
        eq_ledger = EquipmentLedger(args.ledger)
        logger.info("使用设备台账: %s", args.ledger)

    output = process_maintenance_data(
        args.input_path,
        eq_ledger=eq_ledger,
        classifications=classifications,
        skip_hidden_rows=args.skip_hidden_rows,
        skip_hidden_cols=args.skip_hidden_cols,
    )
    print(f"\n输出: {output}")


if __name__ == "__main__":
    main()
