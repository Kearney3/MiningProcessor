"""
MineBase 数据同步包

将 MiningProcessor 处理后的 Excel 数据同步到 MineBase 数据库。
支持两种模式：
- API 模式：通过 MineBase HTTP API 推送（session → batch → confirm）
- 直连模式：通过 psycopg2 直接写入 PostgreSQL
"""
from func.config_loader import get_minebase_api_config
from func.sync.api_client import (
    MineBaseAPIClient,
    MineBaseAPIError,
    SessionExpiredError,
    SessionLimitReachedError,
)
from func.sync.constants import (
    BATCH_SIZE,
    CONTRACT_VERSION,
    DATA_TYPE_REGISTRY,
    DEDUP_FIELDS_MAP,
    FIELD_TO_COLUMN_MAP,
    VALID_TABLES,
)
from func.sync.core import (
    load_column_mapping,
    main,
    sync,
)
from func.sync.db_client import MineBaseDBClient
from func.sync.export import export_anomaly_records_to_excel, export_dry_run_to_excel
from func.sync.file_processors import (
    _df_to_mapped_rows,
    _process_electrical_file,
    _process_fuel_file,
    _process_production_file,
    _process_work_efficiency_file,
    discover_files,
    process_file_generic,
    read_and_map_excel,
)
from func.sync.row_helpers import (
    _apply_defaults,
    _apply_ledger_matching,
    _apply_oil_ledger_matching,
    _build_field_mappings,
    _filter_by_date_range,
    _map_row_to_db_columns,
    _resolve_fks_for_db,
)
from func.sync.sync_engines import (
    sync_via_api,
    sync_via_db,
    test_api_connection,
    test_db_connection,
)

__all__ = [
    "BATCH_SIZE",
    "CONTRACT_VERSION",
    "DATA_TYPE_REGISTRY",
    "DEDUP_FIELDS_MAP",
    "FIELD_TO_COLUMN_MAP",
    "VALID_TABLES",
    "MineBaseAPIClient",
    "MineBaseAPIError",
    "MineBaseDBClient",
    "SessionExpiredError",
    "SessionLimitReachedError",
    "_apply_defaults",
    "_apply_ledger_matching",
    "_apply_oil_ledger_matching",
    "_build_field_mappings",
    "_df_to_mapped_rows",
    "_filter_by_date_range",
    "_map_row_to_db_columns",
    "_process_electrical_file",
    "_process_fuel_file",
    "_process_production_file",
    "_process_work_efficiency_file",
    "_resolve_fks_for_db",
    "discover_files",
    "export_dry_run_to_excel",
    "export_anomaly_records_to_excel",
    "get_minebase_api_config",
    "load_column_mapping",
    "main",
    "process_file_generic",
    "read_and_map_excel",
    "sync",
    "sync_via_api",
    "sync_via_db",
    "test_api_connection",
    "test_db_connection",
]
