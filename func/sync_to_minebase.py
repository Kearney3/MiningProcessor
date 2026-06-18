"""
MineBase 数据同步脚本

将 MiningProcessor 处理后的 Excel 数据同步到 MineBase 数据库。
支持两种模式：
- API 模式：通过 MineBase HTTP API 推送（session → batch → confirm）
- 直连模式：通过 psycopg2 直接写入 PostgreSQL

用法：
    python func/sync_to_minebase.py <输出目录>
    python func/sync_to_minebase.py <输出目录> --mode api
    python func/sync_to_minebase.py <输出目录> --mode database
    python func/sync_to_minebase.py <输出目录> --type fuel electrical
    python func/sync_to_minebase.py <输出目录> --dry-run
"""
import argparse
import glob
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from func.config_loader import (
    get_file_keywords,
    get_minebase_api_config,
    get_minebase_column_mapping,
    get_minebase_config,
    get_minebase_db_config,
    get_minebase_mode,
    load_config,
)
from func.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 数据类型 → (MineBase 表名, Excel 文件名模式, sheet 名或 None)
DATA_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    "fuel": {
        "table": "fuel_consumption",
        "file_pattern": "Fuel.xlsx",
        "sheet": "油耗信息",
    },
    "electrical": {
        "table": "electricity_consumption",
        "file_pattern": "电力消耗统计.xlsx",
        "sheet": None,  # 默认第一个 sheet
    },
    "operation": {
        "table": "equipment_operation",
        "file_pattern": "合并产量.xlsx",
        "sheet": "运行数据",
    },
    "production": {
        "table": "production_record",
        "file_pattern": "合并产量.xlsx",
        "sheet": "生产数据",
    },
    "work_efficiency": {
        "table": "work_efficiency",
        "file_pattern": "*工作效率表*.xlsx",
        "sheet": None,
    },
}

# 每批发送的行数
BATCH_SIZE = 100

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
    if mapping_file is None:
        return get_minebase_column_mapping()
    path = Path(mapping_file)
    if not path.exists():
        logger.info("映射配置文件不存在: %s，使用默认映射", path)
        return get_minebase_column_mapping()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Excel 读取与列映射
# ---------------------------------------------------------------------------


def read_and_map_excel(
    file_path: Path,
    sheet_name: str | int | None,
    column_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """读取 Excel 文件并按映射配置转换列名。

    Args:
        file_path: Excel 文件路径。
        sheet_name: sheet 名称或索引，None 读第一个。
        column_mapping: {源列名: 目标字段名} 映射。

    Returns:
        映射后的行数据列表。
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        # 当 sheet_name=None 时，pd.read_excel 返回 dict；取第一个 sheet
        if isinstance(df, dict):
            df = list(df.values())[0]
    except Exception as e:
        logger.error("读取 Excel 失败: %s — %s", file_path, e)
        return []

    if df.empty:
        logger.info("Excel 文件为空: %s", file_path)
        return []

    # 只保留映射中存在的列，排除标记为 __SKIP__ 的列
    _SKIP = "__SKIP__"
    source_cols = [c for c in df.columns if c in column_mapping and column_mapping[c] != _SKIP]
    if not source_cols:
        logger.warning("Excel 中没有匹配到映射列: %s (列: %s)", file_path, list(df.columns))
        return []

    rows = []
    for _, row in df.iterrows():
        mapped = {}
        for src_col in source_cols:
            target_field = column_mapping[src_col]
            value = row[src_col]
            # 处理 NaN / NaT
            if pd.isna(value):
                continue
            # 日期类型转换
            if isinstance(value, (pd.Timestamp, datetime)):
                value = value.strftime("%Y-%m-%d")
            elif isinstance(value, date):
                value = value.isoformat()
            mapped[target_field] = value
        if mapped:
            rows.append(mapped)

    logger.info("读取 %s: %d 行, 匹配列 %d/%d", file_path.name, len(rows), len(source_cols), len(df.columns))
    return rows


# ---------------------------------------------------------------------------
# API 同步模式
# ---------------------------------------------------------------------------


class MineBaseAPIClient:
    """MineBase HTTP API 客户端。"""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        """发送 HTTP 请求。"""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"连接失败: {url} — {e.reason}") from e

    def login(self) -> None:
        """登录获取 JWT token。"""
        resp = self._request("POST", "/api/auth/login", {
            "username": self.username,
            "password": self.password,
        })
        self.token = resp.get("data", {}).get("token") or resp.get("token")
        if not self.token:
            raise RuntimeError(f"登录失败，未获取到 token: {resp}")
        logger.info("MineBase 登录成功")

    def create_session(self, table: str) -> str:
        """创建导入会话。"""
        resp = self._request("POST", f"/api/import/{table}/session")
        session_id = resp.get("data", {}).get("sessionId") or resp.get("sessionId")
        if not session_id:
            raise RuntimeError(f"创建会话失败: {resp}")
        logger.info("创建导入会话: %s (table=%s)", session_id[:8], table)
        return session_id

    def send_batch(
        self,
        table: str,
        session_id: str,
        rows: list[dict],
        field_mappings: list[dict],
        batch_index: int,
        total_batches: int,
    ) -> dict:
        """发送一批数据到 staging。"""
        payload = {
            "rows": rows,
            "fieldMappings": field_mappings,
            "batchIndex": batch_index,
            "totalBatches": total_batches,
            "sessionId": session_id,
            "duplicateStrategy": "skip",
            "skipUnmatchedFK": True,
        }
        return self._request("POST", f"/api/import/{table}/batch", payload)

    def confirm_import(self, table: str, session_id: str) -> dict:
        """确认导入，将 staging 数据写入目标表。"""
        return self._request("POST", f"/api/import/{table}/confirm", {
            "sessionId": session_id,
            "table": table,
            "duplicateStrategy": "skip",
        })

    def cancel_import(self, table: str, session_id: str) -> dict:
        """取消导入。"""
        return self._request("POST", f"/api/import/{table}/cancel", {"sessionId": session_id})


def _apply_defaults(rows: list[dict[str, Any]], data_type: str) -> list[dict[str, Any]]:
    """为特定数据类型填充缺失字段的默认值。

    - electrical: 若缺少 shiftType，默认填充 "Night"。
    """
    if data_type != "electrical":
        return rows

    result = []
    for row in rows:
        if "shiftType" not in row:
            row = {**row, "shiftType": "Night"}
        result.append(row)
    return result


def _build_field_mappings(column_mapping: dict[str, str], table: str) -> list[dict]:
    """构建 MineBase API 所需的 fieldMappings 数组。"""
    # 定义哪些字段需要 FK 解析
    fk_fields = {
        "equipmentName": {"relation": "equipment", "matchField": "equipName"},
        "truckName": {"relation": "truck", "matchField": "equipName"},
        "excavatorName": {"relation": "excavator", "matchField": "equipName"},
        "materialTypeName": {"relation": "materialType", "matchField": "code"},
    }

    mappings = []
    for src_col, target_field in column_mapping.items():
        entry = {
            "excelColumn": src_col,
            "systemField": target_field,
            "confidence": 1.0,
        }
        if target_field in fk_fields:
            entry["fkResolve"] = fk_fields[target_field]
        mappings.append(entry)
    return mappings


def sync_via_api(
    data_type: str,
    rows: list[dict],
    column_mapping: dict[str, str],
    api_client: MineBaseAPIClient,
    dry_run: bool = False,
) -> dict[str, int]:
    """通过 API 模式同步数据。

    Returns:
        {"success": N, "skipped": N, "failed": N}
    """
    table = DATA_TYPE_REGISTRY[data_type]["table"]

    if not rows:
        logger.info("[%s] 无数据可同步", data_type)
        return {"success": 0, "skipped": 0, "failed": 0}

    if dry_run:
        logger.info("[DRY-RUN] %s: 将同步 %d 行到 %s", data_type, len(rows), table)
        for row in rows[:3]:
            logger.info("  示例: %s", row)
        if len(rows) > 3:
            logger.info("  ... 共 %d 行", len(rows))
        return {"success": 0, "skipped": 0, "failed": 0}

    field_mappings = _build_field_mappings(column_mapping, table)
    session_id = api_client.create_session(table)

    total_success = 0
    total_skipped = 0
    total_failed = 0

    try:
        batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        total_batches = len(batches)

        for idx, batch in enumerate(batches):
            resp = api_client.send_batch(table, session_id, batch, field_mappings, idx, total_batches)
            data = resp.get("data", {})
            s = data.get("success", 0)
            sk = data.get("skipped", 0)
            f = data.get("failed", 0)
            total_success += s
            total_skipped += sk
            total_failed += f

            if data.get("warnings"):
                for w in data["warnings"][:5]:
                    logger.warning("  [%s] 行%d: %s", data_type, w.get("row", "?"), w.get("message", ""))
            if data.get("errors"):
                for e in data["errors"][:5]:
                    logger.error("  [%s] 行%d: %s", data_type, e.get("row", "?"), e.get("message", ""))

        # 确认导入
        confirm_resp = api_client.confirm_import(table, session_id)
        confirm_data = confirm_resp.get("data", {})
        logger.info(
            "[%s] API 同步完成: 插入=%d, 更新=%d, 跳过=%d",
            data_type,
            confirm_data.get("inserted", total_success),
            confirm_data.get("updated", 0),
            confirm_data.get("skipped", total_skipped),
        )

    except Exception as e:
        logger.error("[%s] API 同步失败: %s", data_type, e)
        try:
            api_client.cancel_import(table, session_id)
        except Exception:
            pass
        total_failed += len(rows) - total_success - total_skipped

    return {"success": total_success, "skipped": total_skipped, "failed": total_failed}


# ---------------------------------------------------------------------------
# 直连数据库同步模式
# ---------------------------------------------------------------------------


def test_api_connection(url: str, username: str, password: str) -> tuple[bool, str]:
    """测试 API 连接（尝试登录），返回 (成功, 描述信息)。"""
    try:
        client = MineBaseAPIClient(url, username, password)
        client.login()
        return True, f"连接成功: {url}"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def test_db_connection(
    host: str, port: int, database: str, user: str, password: str,
) -> tuple[bool, str]:
    """测试数据库连接，返回 (成功, 描述信息)。"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=database,
            user=user, password=password, connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return True, f"连接成功: {user}@{host}:{port}/{database}"
    except psycopg2.OperationalError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


class MineBaseDBClient:
    """MineBase PostgreSQL 直连客户端。"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        import psycopg2
        self.conn = psycopg2.connect(
            host=host, port=port, dbname=database, user=user, password=password,
        )
        self.conn.autocommit = False
        logger.info("已连接 MineBase 数据库: %s@%s:%d/%s", user, host, port, database)

    def close(self) -> None:
        if self.conn and not self.conn.closed:
            self.conn.close()

    def resolve_equipment_id(self, equip_name: str) -> str | None:
        """通过 3 级级联查找设备 ID（与 MineBase API 一致）。"""
        with self.conn.cursor() as cur:
            # 1. 直接查找 equipment.equip_name
            cur.execute(
                "SELECT id FROM equipment WHERE LOWER(equip_name) = LOWER(%s) LIMIT 1",
                (equip_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])

            # 2. 精确匹配 equipment_match_table.equip_name
            cur.execute(
                "SELECT equipment_id FROM equipment_match_table WHERE LOWER(equip_name) = LOWER(%s) AND equipment_id IS NOT NULL LIMIT 1",
                (equip_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])

            # 3. 模糊匹配 equipment_match_table.equip_name（包含关系）
            cur.execute(
                "SELECT equipment_id FROM equipment_match_table WHERE LOWER(equip_name) LIKE LOWER(%s) AND equipment_id IS NOT NULL LIMIT 1",
                (f"%{equip_name}%",),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])

        return None

    def resolve_material_type_id(self, material_name: str) -> str | None:
        """通过 material_type.code 查找物料类型 ID。"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM material_type WHERE LOWER(code) = LOWER(%s) LIMIT 1",
                (material_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
        return None

    def check_duplicate(self, table: str, dedup_fields: dict[str, Any]) -> bool:
        """检查是否已存在重复记录。"""
        if not dedup_fields:
            return False
        conditions = " AND ".join(f"{k} = %s" for k in dedup_fields)
        query = f"SELECT id FROM {table} WHERE {conditions} LIMIT 1"
        with self.conn.cursor() as cur:
            cur.execute(query, list(dedup_fields.values()))
            return cur.fetchone() is not None

    def insert_rows(self, table: str, columns: list[str], values_list: list[list[Any]]) -> int:
        """批量插入数据。返回插入行数。"""
        if not values_list:
            return 0

        import psycopg2.extras

        cols_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"

        with self.conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, query, values_list, page_size=200)
        return len(values_list)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()


# 各表的 dedup 字段定义（PostgreSQL 列名）
# 与 MineBase UNIQUE 约束保持一致
DEDUP_FIELDS_MAP: dict[str, list[str]] = {
    "fuel_consumption": ["date", "shift_type", "equipment_name", "equipment_code", "fuel_name"],
    "electricity_consumption": ["date", "shift_type", "equipment_name", "equipment_code"],
    "work_efficiency": ["date", "shift_type", "equipment_name", "equipment_code", "company"],
    "equipment_operation": ["date", "shift_type", "equipment_name", "equipment_code"],
    "production_record": ["date", "shift_type", "truck_name", "excavator_name", "material_type_name"],
}

# API 字段名 → PostgreSQL 列名映射
FIELD_TO_COLUMN_MAP: dict[str, str] = {
    "date": "date",
    "shiftType": "shift_type",
    "equipmentName": "equipment_name",
    "equipmentCode": "equipment_code",
    "equipmentId": "equipment_id",
    "fuelName": "fuel_name",
    "consumption": "consumption",
    "company": "company",
    "plannedMinutes": "planned_minutes",
    "plannedHours": "planned_hours",
    "parkShift": "park_shift",
    "transfer": "transfer",
    "auxiliaryWork": "auxiliary_work",
    "waitingLoad": "waiting_load",
    "blasting": "blasting",
    "mealBreak": "meal_break",
    "refueling": "refueling",
    "plannedMaintenance": "planned_maintenance",
    "unplannedFault": "unplanned_fault",
    "standby": "standby",
    "weatherSnow": "weather_snow",
    "weatherDust": "weather_dust",
    "fillWater": "fill_water",
    "powerIssuePlanned": "power_issue_planned",
    "powerIssueUnplanned": "power_issue_unplanned",
    "totalProductionMinutes": "total_production_minutes",
    "totalProductionHours": "total_production_hours",
    "remark": "remark",
    "engineHoursStart": "engine_hours_start",
    "engineHoursEnd": "engine_hours_end",
    "runningHours": "running_hours",
    "milemeterStart": "milemeter_start",
    "milemeterEnd": "milemeter_end",
    "mileage": "mileage",
    "tripCount": "trip_count",
    "truckName": "truck_name",
    "truckId": "truck_id",
    "excavatorName": "excavator_name",
    "excavatorId": "excavator_id",
    "materialTypeName": "material_type_name",
    "materialTypeId": "material_type_id",
    "production": "production",
}


def sync_via_db(
    data_type: str,
    rows: list[dict],
    column_mapping: dict[str, str],
    db_client: MineBaseDBClient,
    dry_run: bool = False,
) -> dict[str, int]:
    """通过直连数据库模式同步数据。

    Returns:
        {"success": N, "skipped": N, "failed": N}
    """
    table = DATA_TYPE_REGISTRY[data_type]["table"]

    if not rows:
        logger.info("[%s] 无数据可同步", data_type)
        return {"success": 0, "skipped": 0, "failed": 0}

    if dry_run:
        logger.info("[DRY-RUN] %s: 将同步 %d 行到 %s", data_type, len(rows), table)
        for row in rows[:3]:
            logger.info("  示例: %s", row)
        if len(rows) > 3:
            logger.info("  ... 共 %d 行", len(rows))
        return {"success": 0, "skipped": 0, "failed": 0}

    total_success = 0
    total_skipped = 0
    total_failed = 0

    try:
        for row in rows:
            try:
                # FK 解析
                resolved_row = _resolve_fks_for_db(data_type, row, db_client)
                if resolved_row is None:
                    total_skipped += 1
                    continue

                # 转换为 PostgreSQL 列名
                columns, values = _map_row_to_db_columns(resolved_row)
                if not columns:
                    total_skipped += 1
                    continue

                # 去重检查
                dedup_cols = DEDUP_FIELDS_MAP.get(table, [])
                dedup_values = {}
                for col, val in zip(columns, values):
                    if col in dedup_cols:
                        dedup_values[col] = val

                if dedup_values and db_client.check_duplicate(table, dedup_values):
                    total_skipped += 1
                    continue

                # 插入
                db_client.insert_rows(table, columns, [values])
                total_success += 1

            except Exception as e:
                logger.error("[%s] 行处理失败: %s — %s", data_type, row, e)
                total_failed += 1

        db_client.commit()
        logger.info("[%s] DB 同步完成: 成功=%d, 跳过=%d, 失败=%d", data_type, total_success, total_skipped, total_failed)

    except Exception as e:
        logger.error("[%s] DB 同步失败，已回滚: %s", data_type, e)
        db_client.rollback()
        total_failed += len(rows) - total_success - total_skipped

    return {"success": total_success, "skipped": total_skipped, "failed": total_failed}


def _resolve_fks_for_db(data_type: str, row: dict, db_client: MineBaseDBClient) -> dict | None:
    """为直连模式解析 FK 字段。返回解析后的行，FK 未找到时返回 None。"""
    resolved = dict(row)

    if data_type == "production_record":
        # 矿卡
        truck_name = row.get("truckName")
        if truck_name:
            truck_id = db_client.resolve_equipment_id(truck_name)
            if not truck_id:
                logger.warning("矿卡 '%s' 未找到，跳过该行", truck_name)
                return None
            resolved["truckId"] = truck_id
        else:
            logger.warning("缺少矿卡名称，跳过该行")
            return None

        # 挖机
        excavator_name = row.get("excavatorName")
        if excavator_name:
            excavator_id = db_client.resolve_equipment_id(excavator_name)
            if not excavator_id:
                logger.warning("挖机 '%s' 未找到，跳过该行", excavator_name)
                return None
            resolved["excavatorId"] = excavator_id
        else:
            logger.warning("缺少挖机名称，跳过该行")
            return None

        # 物料类型
        material_name = row.get("materialTypeName")
        if material_name:
            material_id = db_client.resolve_material_type_id(material_name)
            if material_id:
                resolved["materialTypeId"] = material_id
            # material_type_id 是 nullable，找不到不跳过

    else:
        # 通用设备 FK
        equip_name = row.get("equipmentName")
        if equip_name:
            equip_id = db_client.resolve_equipment_id(equip_name)
            if not equip_id:
                logger.warning("设备 '%s' 未找到，跳过该行", equip_name)
                return None
            resolved["equipmentId"] = equip_id
        else:
            logger.warning("缺少设备名称，跳过该行")
            return None

    return resolved


def _map_row_to_db_columns(row: dict) -> tuple[list[str], list[Any]]:
    """将 API 字段名的行数据转换为 PostgreSQL 列名和值列表。"""
    columns = []
    values = []
    for field_name, value in row.items():
        col_name = FIELD_TO_COLUMN_MAP.get(field_name)
        if col_name is None:
            continue
        columns.append(col_name)
        values.append(value)
    return columns, values


# ---------------------------------------------------------------------------
# 文件发现
# ---------------------------------------------------------------------------


def discover_files(
    input_dir: Path,
    year: int | None = None,
    month: int | None = None,
    keywords: dict[str, list[str]] | None = None,
) -> dict[str, Path]:
    """在输入目录中查找各数据类型对应的 Excel 文件。

    优先使用关键字匹配（与 excel_batch.scan_files 一致），
    回退到 DATA_TYPE_REGISTRY 中的 file_pattern glob 匹配。
    work_efficiency 类型支持 year/month 构造精确文件名模式。

    Args:
        input_dir: 输入目录。
        year: 年份（用于 work_efficiency 文件名匹配）。
        month: 月份（用于 work_efficiency 文件名匹配）。
        keywords: {模块类型: [关键字]}，默认从配置读取。

    Returns:
        {data_type: file_path} 字典。
    """
    if keywords is None:
        keywords = get_file_keywords()

    # 列出目录中所有 Excel 文件（排除临时文件）
    excel_files = sorted(
        f for f in input_dir.iterdir()
        if f.suffix.lower() in (".xlsx", ".xls") and not f.name.startswith("~$")
    )

    # 关键字 → 数据类型映射（batch 模块类型 → sync 数据类型）
    kw_type_map = {
        "fuel": "fuel",
        "electrical": "electrical",
        "production": ["production", "operation"],  # 同一文件，不同 sheet
        "worktime": "work_efficiency",
    }

    found: dict[str, Path] = {}

    # 1. 关键字匹配
    for module_type, sync_types in kw_type_map.items():
        kw_list = keywords.get(module_type, [])
        if not kw_list:
            continue
        matched_files = [
            f for f in excel_files
            if any(k in f.name for k in kw_list)
        ]
        if not matched_files:
            continue

        target_file = matched_files[0]
        if isinstance(sync_types, list):
            for st in sync_types:
                found[st] = target_file
        else:
            found[sync_types] = target_file
        logger.info("关键字匹配: %s → %s", module_type, target_file.name)

    # 2. work_efficiency 回退：按 year/month 构造 glob 模式
    if "work_efficiency" not in found:
        if year and month:
            pattern = f"*{year}{month:02d}*工作效率表*.xlsx"
        else:
            pattern = "*工作效率表*.xlsx"
        matches = sorted(input_dir.glob(pattern))
        if matches:
            found["work_efficiency"] = matches[0]
            logger.info("Glob 匹配: work_efficiency → %s", matches[0].name)

    # 3. 其他类型回退到 DATA_TYPE_REGISTRY 的 file_pattern
    for data_type, info in DATA_TYPE_REGISTRY.items():
        if data_type in found:
            continue
        pattern = info["file_pattern"]
        if "*" in pattern:
            matches = sorted(input_dir.glob(pattern))
        else:
            matches = list(input_dir.glob(pattern))
        if matches:
            found[data_type] = matches[0]
            logger.info("Glob 回退: %s → %s", data_type, matches[0].name)

    for dt, fp in found.items():
        logger.info("发现文件: %s → %s", dt, fp.name)
    return found


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def _filter_by_date_range(
    rows: list[dict[str, Any]],
    date_start: str | None,
    date_end: str | None,
) -> list[dict[str, Any]]:
    """按日期范围过滤行数据。

    Args:
        rows: 已映射的行数据列表。
        date_start: 起始日期（含），格式 YYYY-MM-DD，None 不限。
        date_end: 结束日期（含），格式 YYYY-MM-DD，None 不限。

    Returns:
        过滤后的行数据列表（新列表，不修改原数据）。
    """
    if not date_start and not date_end:
        return rows

    result = []
    for row in rows:
        row_date = row.get("date")
        if not row_date:
            result.append(row)
            continue
        if date_start and str(row_date) < date_start:
            continue
        if date_end and str(row_date) > date_end:
            continue
        result.append(row)

    skipped = len(rows) - len(result)
    if skipped:
        logger.info("日期过滤: 保留 %d/%d 行 (范围: %s ~ %s)", len(result), len(rows), date_start, date_end)
    return result


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

    Returns:
        {data_type: {"success": N, "skipped": N, "failed": N}}
    """
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
    files = discover_files(input_path, year=year, month=month)
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

    # 逐类型同步
    results = {}
    try:
        for data_type, file_path in files.items():
            logger.info("=" * 50)
            logger.info("同步 %s: %s", data_type, file_path.name)

            table = DATA_TYPE_REGISTRY[data_type]["table"]
            mapping = column_mapping.get(data_type, {})
            if not mapping:
                logger.warning("[%s] 映射配置中未找到该数据类型，跳过", data_type)
                results[data_type] = {"success": 0, "skipped": 0, "failed": 0}
                continue

            sheet = DATA_TYPE_REGISTRY[data_type]["sheet"]
            rows = read_and_map_excel(file_path, sheet, mapping)
            rows = _apply_defaults(rows, data_type)
            rows = _filter_by_date_range(rows, date_start, date_end)

            if sync_mode == "api":
                results[data_type] = sync_via_api(data_type, rows, mapping, api_client, dry_run)
            else:
                results[data_type] = sync_via_db(data_type, rows, mapping, db_client, dry_run)

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

    # 一次性迁移：将 config.user.json 中明文密码转入系统 Keychain
    try:
        from func.secret_store import migrate_passwords_to_keyring
        migrate_passwords_to_keyring()
    except Exception:
        pass

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
    )


if __name__ == "__main__":
    main()
