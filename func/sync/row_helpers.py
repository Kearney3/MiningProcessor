"""
行数据辅助函数、FK 解析、列映射转换、台账匹配、日期过滤。
"""
import uuid
from datetime import datetime
from typing import Any

from func.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 行数据辅助函数
# ---------------------------------------------------------------------------


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


# 各数据类型的设备名称字段（用于台账匹配）
_LEDGER_NAME_FIELDS: dict[str, list[str]] = {
    "fuel": ["equipmentName"],
    "electrical": ["equipmentName"],
    "operation": ["equipmentName"],
    "work_efficiency": ["equipmentName"],
    "production": ["truckName", "excavatorName"],
}

# 各数据类型的油品名称字段（用于油品台账匹配）
_OIL_LEDGER_NAME_FIELDS: dict[str, list[str]] = {
    "fuel": ["fuelName"],
}


def _apply_ledger_matching(
    rows: list[dict[str, Any]],
    data_type: str,
    ledger: Any,
    warnings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """使用设备台账标准化行数据中的设备名称。

    Args:
        rows: 已映射的行数据列表。
        data_type: 数据类型键。
        ledger: EquipmentLedger 实例。
        warnings: 可选警告收集列表，未匹配的设备名会追加到此列表。

    Returns:
        设备名称标准化后的新列表。
    """
    from func.equipment_ledger import EquipmentLedger

    if not ledger or not isinstance(ledger, EquipmentLedger):
        return rows

    name_fields = _LEDGER_NAME_FIELDS.get(data_type, [])
    if not name_fields:
        return rows

    matched_count = 0
    result = []
    for row in rows:
        new_row = dict(row)
        for field in name_fields:
            raw_name = row.get(field)
            if not raw_name:
                continue
            match = ledger.match(str(raw_name))
            if match and match["标准名称"] != raw_name:
                new_row[field] = match["标准名称"]
                matched_count += 1
            elif not match and warnings is not None:
                warnings.append({
                    "row": row.get("_row_num", "?"),
                    "field": field,
                    "value": str(raw_name),
                    "message": f"设备名 '{raw_name}' 未匹配到台账",
                })
        result.append(new_row)

    if matched_count:
        logger.info("[%s] 台账匹配: 标准化 %d 个设备名称", data_type, matched_count)
    return result


def _apply_oil_ledger_matching(
    rows: list[dict[str, Any]],
    data_type: str,
    ledger: Any,
    warnings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """使用油品台账标准化行数据中的油品名称。

    Args:
        rows: 已映射的行数据列表。
        data_type: 数据类型键。
        ledger: OilLedger 实例。
        warnings: 可选警告收集列表，未匹配的油品名会追加到此列表。

    Returns:
        油品名称标准化后的新列表。
    """
    from func.oil_ledger import OilLedger

    if not ledger or not isinstance(ledger, OilLedger):
        return rows

    name_fields = _OIL_LEDGER_NAME_FIELDS.get(data_type, [])
    if not name_fields:
        return rows

    matched_count = 0
    result = []
    for row in rows:
        new_row = dict(row)
        for field in name_fields:
            raw_name = row.get(field)
            if not raw_name:
                continue
            match = ledger.match(str(raw_name))
            if match and match["标准名称"] != raw_name:
                new_row[field] = match["标准名称"]
                matched_count += 1
            elif not match and warnings is not None:
                warnings.append({
                    "row": row.get("_row_num", "?"),
                    "field": field,
                    "value": str(raw_name),
                    "message": f"油品名 '{raw_name}' 未匹配到台账",
                })
        result.append(new_row)

    if matched_count:
        logger.info("[%s] 油品台账匹配: 标准化 %d 个油品名称", data_type, matched_count)
    return result


# ---------------------------------------------------------------------------
# FK 解析（直连数据库模式）
# ---------------------------------------------------------------------------


def _resolve_fks_for_db(
    data_type: str, row: dict, db_client: Any,
    warnings: list[dict[str, Any]] | None = None,
) -> dict | None:
    """为直连模式解析 FK 字段。返回解析后的行，FK 未找到时返回 None。"""
    resolved = dict(row)

    if data_type in ("production", "production_record"):
        # 矿卡
        truck_name = row.get("truckName")
        if truck_name:
            truck_id = db_client.resolve_equipment_id(truck_name)
            if not truck_id:
                msg = f"矿卡 '{truck_name}' 未找到，跳过该行"
                logger.warning(msg)
                if warnings is not None:
                    warnings.append({
                        "row": row.get("_row_num", "?"),
                        "field": "truckName",
                        "value": str(truck_name),
                        "message": msg,
                    })
                return None
            resolved["truckId"] = truck_id
        else:
            msg = "缺少矿卡名称，跳过该行"
            logger.warning(msg)
            if warnings is not None:
                warnings.append({
                    "row": row.get("_row_num", "?"),
                    "field": "truckName",
                    "value": "",
                    "message": msg,
                })
            return None

        # 挖机
        excavator_name = row.get("excavatorName")
        if excavator_name:
            excavator_id = db_client.resolve_equipment_id(excavator_name)
            if not excavator_id:
                msg = f"挖机 '{excavator_name}' 未找到，跳过该行"
                logger.warning(msg)
                if warnings is not None:
                    warnings.append({
                        "row": row.get("_row_num", "?"),
                        "field": "excavatorName",
                        "value": str(excavator_name),
                        "message": msg,
                    })
                return None
            resolved["excavatorId"] = excavator_id
        else:
            msg = "缺少挖机名称，跳过该行"
            logger.warning(msg)
            if warnings is not None:
                warnings.append({
                    "row": row.get("_row_num", "?"),
                    "field": "excavatorName",
                    "value": "",
                    "message": msg,
                })
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
                msg = f"设备 '{equip_name}' 未找到，跳过该行"
                logger.warning(msg)
                if warnings is not None:
                    warnings.append({
                        "row": row.get("_row_num", "?"),
                        "field": "equipmentName",
                        "value": str(equip_name),
                        "message": msg,
                    })
                return None
            resolved["equipmentId"] = equip_id
        else:
            msg = "缺少设备名称，跳过该行"
            logger.warning(msg)
            if warnings is not None:
                warnings.append({
                    "row": row.get("_row_num", "?"),
                    "field": "equipmentName",
                    "value": "",
                    "message": msg,
                })
            return None

    return resolved


def _map_row_to_db_columns(row: dict) -> tuple[list[str], list[Any]]:
    """将 API 字段名的行数据转换为 PostgreSQL 列名和值列表。

    自动补充数据库必需但代码未提供的字段：
    - id: UUID 主键（Prisma @default(uuid()) 仅在应用层生效，数据库无 DEFAULT）
    - updated_at: Prisma @updatedAt 仅在应用层生效，数据库无 DEFAULT
    """
    from func.sync.constants import FIELD_TO_COLUMN_MAP

    columns = ["id", "updated_at"]
    values = [str(uuid.uuid4()), datetime.now()]
    for field_name, value in row.items():
        col_name = FIELD_TO_COLUMN_MAP.get(field_name)
        if col_name is None:
            continue
        columns.append(col_name)
        values.append(value)
    return columns, values


# ---------------------------------------------------------------------------
# 日期过滤
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
