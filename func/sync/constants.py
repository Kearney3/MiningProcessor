"""
共享常量定义。

DATA_TYPE_REGISTRY：数据类型 → (MineBase 表名, Excel 文件名模式, sheet 名)
BATCH_SIZE：每批发送的行数
VALID_TABLES：允许出现在 SQL 中的表名白名单
DEDUP_FIELDS_MAP：各表的去重字段
FIELD_TO_COLUMN_MAP：API 字段名 → PostgreSQL 列名映射
"""
from typing import Any

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

# 允许出现在 SQL 中的表名白名单（用于防御性校验，防止 SQL 注入）
VALID_TABLES: frozenset[str] = frozenset(r["table"] for r in DATA_TYPE_REGISTRY.values())

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
