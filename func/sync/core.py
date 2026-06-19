"""
同步核心流程。

包含 sync() 主入口、列映射加载、CLI main() 入口。
sync_via_api/sync_via_db 在 sync_engines.py，文件处理在 file_processors.py。
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from func.logger import get_logger
from func.sync.constants import DATA_TYPE_REGISTRY

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 映射配置加载
# ---------------------------------------------------------------------------


def load_column_mapping(mapping_file: str | Path | None = None) -> dict[str, dict[str, str]]:
    """加载列映射配置文件。

    未指定文件时通过 config_loader 读取（优先用户自定义，回退 config.json 默认值）。
    指定文件时直接读取该文件。

    Returns:
        {data_type: {源列名: 目标字段名}} 的嵌套字典。
    """
    from func.config_loader import get_minebase_column_mapping

    if mapping_file is None:
        return get_minebase_column_mapping()
    path = Path(mapping_file)
    if not path.exists():
        logger.info("映射配置文件不存在: %s，使用默认映射", path)
        return get_minebase_column_mapping()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def sync(
    input_dir: str | Path,
    mode: str | None = None,
    data_types: list[str] | None = None,
    dry_run: bool = False,
    mapping_file: str | Path | None = None,
    api_url: str | None = None,
    db_host: str | None = None,
    year: int | None = None,
    month: int | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    apply_header_mapping: bool = True,
    use_ledger: bool = False,
) -> dict[str, dict[str, int]]:
    """执行同步的主入口。

    Args:
        input_dir: MiningProcessor 输出目录。
        mode: 'api' 或 'database'，None 使用配置文件中的值。
        data_types: 要同步的数据类型列表，None 同步所有。
        dry_run: 仅预览，不实际推送。
        mapping_file: 映射配置文件路径。
        api_url: 覆盖 API URL。
        db_host: 覆盖数据库主机。
        year: 年份（用于文件发现和 work_efficiency 文件名匹配）。
        month: 月份（用于文件发现和 work_efficiency 文件名匹配）。
        date_start: 起始日期过滤（含），格式 YYYY-MM-DD。
        date_end: 结束日期过滤（含），格式 YYYY-MM-DD。
        apply_header_mapping: 是否对 work_efficiency 应用工时表头映射。
        use_ledger: 是否使用设备台账标准化设备名称。

    Returns:
        {data_type: {"success": N, "skipped": N, "failed": N}}
    """
    from func.config_loader import (
        get_minebase_api_config,
        get_minebase_db_config,
        get_minebase_mode,
    )
    from func.sync.row_helpers import (
        _apply_defaults,
        _apply_ledger_matching,
        _apply_oil_ledger_matching,
        _filter_by_date_range,
    )

    # Late-binding: resolve functions/classes through the shim module so that
    # unittest.mock.patch("func.sync_to_minebase.X") works in tests.
    _mod = sys.modules["func.sync_to_minebase"]
    MineBaseAPIClient = _mod.MineBaseAPIClient
    MineBaseDBClient = _mod.MineBaseDBClient
    _discover_files = _mod.discover_files
    _sync_via_api = _mod.sync_via_api
    _sync_via_db = _mod.sync_via_db
    _process_fuel = _mod._process_fuel_file
    _process_electrical = _mod._process_electrical_file
    _process_production = _mod._process_production_file
    _process_work_eff = _mod._process_work_efficiency_file
    _read_and_map = _mod.read_and_map_excel

    input_path = Path(input_dir)
    if not input_path.is_dir():
        logger.error("输入目录不存在: %s", input_path)
        return {}

    # 加载映射配置
    column_mapping = load_column_mapping(mapping_file)
    if not column_mapping:
        logger.error("无法加载列映射配置，同步终止")
        return {}

    # 发现文件
    files = _discover_files(input_path, year=year, month=month)
    if not files:
        logger.warning("在 %s 中未发现可同步的 Excel 文件", input_path)
        return {}

    # 过滤数据类型
    if data_types:
        files = {k: v for k, v in files.items() if k in data_types}
        if not files:
            logger.warning("指定的数据类型未找到对应文件: %s", data_types)
            return {}

    # 确定同步模式
    sync_mode = mode or get_minebase_mode()
    logger.info("同步模式: %s", sync_mode)

    # 初始化客户端
    api_client = None
    db_client = None

    if sync_mode == "api":
        cfg = get_minebase_api_config()
        url = api_url or cfg.get("url", "http://localhost:3000")
        api_client = MineBaseAPIClient(url, cfg.get("username", ""), cfg.get("password", ""))
        if not dry_run:
            api_client.login()
    elif sync_mode == "database":
        cfg = get_minebase_db_config()
        host = db_host or cfg.get("host", "localhost")
        db_client = MineBaseDBClient(
            host=host,
            port=cfg.get("port", 5432),
            database=cfg.get("database", "minebase"),
            user=cfg.get("user", "postgres"),
            password=cfg.get("password", ""),
        )
    else:
        logger.error("未知同步模式: %s (支持 'api' 或 'database')", sync_mode)
        return {}

    # 初始化台账（可选）
    ledger = None
    oil_ledger = None
    if use_ledger:
        from func.equipment_ledger import EquipmentLedger
        from func.config_loader import load_equipment_ledger_cache
        cached = load_equipment_ledger_cache()
        if cached:
            ledger = EquipmentLedger()
            ledger._df = pd.DataFrame(cached)
            ledger._build_search_cache()
            logger.info("已加载设备台账缓存: %d 条", len(cached))
        else:
            logger.warning("设备台账缓存未找到，跳过设备名称匹配")

        from func.oil_ledger import OilLedger
        from func.config_loader import load_oil_ledger_cache
        oil_cached = load_oil_ledger_cache()
        if oil_cached:
            oil_ledger = OilLedger()
            oil_ledger._df = pd.DataFrame(oil_cached)
            oil_ledger._build_search_cache()
            logger.info("已加载油品台账缓存: %d 条", len(oil_cached))
        else:
            logger.warning("油品台账缓存未找到，跳过油品名称匹配")

    # 生产文件处理缓存（production 和 operation 可能指向同一文件）
    _production_cache: dict[str, dict[str, list[dict[str, Any]]]] | None = None

    # 逐类型同步（每个类型可能对应多个文件）
    results = {}
    try:
        for data_type, file_list in files.items():
            logger.info("=" * 50)
            logger.info("同步 %s: %d 个文件", data_type, len(file_list))

            table = DATA_TYPE_REGISTRY[data_type]["table"]
            mapping = column_mapping.get(data_type) or column_mapping.get(table, {})
            if not mapping:
                logger.warning("[%s] 映射配置中未找到该数据类型，跳过", data_type)
                results[data_type] = {"success": 0, "skipped": 0, "failed": 0}
                continue

            # 聚合所有文件的行数据
            all_rows: list[dict[str, Any]] = []
            for file_path in file_list:
                logger.info("  处理文件: %s", file_path.name)
                try:
                    if data_type == "fuel":
                        rows = _process_fuel(file_path, year)
                    elif data_type == "electrical":
                        rows = _process_electrical(file_path, year)
                    elif data_type in ("production", "operation"):
                        # 缓存生产文件处理结果，避免同一文件处理两次
                        cache_key = str(file_path)
                        if _production_cache is None or cache_key not in _production_cache:
                            result = _process_production(file_path)
                            if _production_cache is None:
                                _production_cache = {}
                            _production_cache[cache_key] = result
                        rows = _production_cache[cache_key].get(data_type, [])
                    elif data_type == "work_efficiency":
                        rows = _process_work_eff(
                            file_path, year, month, apply_header_mapping,
                        )
                    else:
                        rows = _read_and_map(file_path, DATA_TYPE_REGISTRY[data_type]["sheet"], mapping)
                    all_rows.extend(rows)
                except Exception as e:
                    logger.error("[%s] 处理文件失败: %s — %s", data_type, file_path, e)

            if not all_rows:
                results[data_type] = {"success": 0, "skipped": 0, "failed": 0}
                continue

            all_rows = _apply_defaults(all_rows, data_type)
            all_rows = _apply_ledger_matching(all_rows, data_type, ledger)
            all_rows = _apply_oil_ledger_matching(all_rows, data_type, oil_ledger)
            all_rows = _filter_by_date_range(all_rows, date_start, date_end)

            if sync_mode == "api":
                results[data_type] = _sync_via_api(data_type, all_rows, mapping, api_client, dry_run)
            else:
                results[data_type] = _sync_via_db(data_type, all_rows, mapping, db_client, dry_run)

    finally:
        if db_client:
            db_client.close()

    # 汇总
    logger.info("=" * 50)
    logger.info("同步汇总:")
    total = {"success": 0, "skipped": 0, "failed": 0}
    for dt, r in results.items():
        logger.info("  %s: 成功=%d, 跳过=%d, 失败=%d", dt, r["success"], r["skipped"], r["failed"])
        for k in total:
            total[k] += r[k]
    logger.info("  合计: 成功=%d, 跳过=%d, 失败=%d", total["success"], total["skipped"], total["failed"])

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    from func.logger import setup_logging
    setup_logging()

    parser = argparse.ArgumentParser(description="将 MiningProcessor 数据同步到 MineBase")
    parser.add_argument("input_dir", help="MiningProcessor 输出目录路径")
    parser.add_argument("--mode", choices=["api", "database"], help="同步模式: api 或 database")
    parser.add_argument("--type", nargs="+", dest="data_types",
                        choices=list(DATA_TYPE_REGISTRY.keys()),
                        help="只同步指定的数据类型")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际推送")
    parser.add_argument("--mapping", help="列映射配置文件路径")
    parser.add_argument("--url", help="MineBase API 地址（覆盖配置）")
    parser.add_argument("--db-host", help="MineBase 数据库主机（覆盖配置）")
    parser.add_argument("--year", type=int, help="年份（用于文件发现）")
    parser.add_argument("--month", type=int, help="月份（用于文件发现）")
    parser.add_argument("--date-start", dest="date_start", help="起始日期过滤（含），格式 YYYY-MM-DD")
    parser.add_argument("--date-end", dest="date_end", help="结束日期过滤（含），格式 YYYY-MM-DD")
    parser.add_argument("--no-header-mapping", action="store_true", help="不对工时表应用表头映射")
    parser.add_argument("--ledger", action="store_true", help="使用设备台账标准化设备名称")
    args = parser.parse_args()

    sync(
        input_dir=args.input_dir,
        mode=args.mode,
        data_types=args.data_types,
        dry_run=args.dry_run,
        mapping_file=args.mapping,
        api_url=args.url,
        db_host=args.db_host,
        year=args.year,
        month=args.month,
        date_start=args.date_start,
        date_end=args.date_end,
        apply_header_mapping=not args.no_header_mapping,
        use_ledger=args.ledger,
    )


if __name__ == "__main__":
    main()
