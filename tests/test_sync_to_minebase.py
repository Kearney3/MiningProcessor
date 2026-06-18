"""sync_to_minebase 模块测试"""
import json
import pathlib
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.sync_to_minebase import (
    MineBaseAPIClient,
    _apply_defaults,
    _build_field_mappings,
    _filter_by_date_range,
    _map_row_to_db_columns,
    discover_files,
    load_column_mapping,
    read_and_map_excel,
    sync,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_mapping(tmp_path):
    """创建临时映射配置文件。"""
    mapping = {
        "fuel_consumption": {
            "日期": "date",
            "班次": "shiftType",
            "设备名称": "equipmentName",
            "油品种类": "fuelName",
            "油品消耗": "consumption",
        },
        "electricity_consumption": {
            "日期": "date",
            "班次": "shiftType",
            "设备名称": "equipmentName",
            "电力消耗": "consumption",
        },
        "equipment_operation": {
            "日期": "date",
            "班次": "shiftType",
            "设备名称": "equipmentName",
            "运行小时数": "runningHours",
            "趟数": "tripCount",
        },
        "production_record": {
            "日期": "date",
            "班次": "shiftType",
            "矿卡名称": "truckName",
            "挖机名称": "excavatorName",
            "矿石类型": "materialTypeName",
            "运次": "tripCount",
            "产量": "production",
        },
        "work_efficiency": {
            "设备名称": "equipmentName",
            "应运行分钟": "plannedMinutes",
            "停车/换班": "parkShift",
        },
    }
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return path, mapping


@pytest.fixture
def sample_fuel_excel(tmp_path_factory):
    """创建模拟的 Fuel.xlsx 油耗信息 sheet。"""
    tmp = tmp_path_factory.mktemp("fuel")
    df = pd.DataFrame({
        "日期": [date(2025, 6, 1), date(2025, 6, 1)],
        "班次": ["Day", "Night"],
        "设备名称": ["CAT785D-01", "NTE240-02"],
        "设备编号": ["CAT785D-01", "NTE240-02"],
        "油品种类": ["0#柴油", "0#柴油"],
        "油品消耗": [150.5, 200.0],
    })
    path = tmp / "Fuel.xlsx"
    df.to_excel(path, sheet_name="油耗信息", index=False)
    return path


@pytest.fixture
def sample_electrical_excel(tmp_path_factory):
    """创建模拟的电力消耗统计.xlsx。"""
    tmp = tmp_path_factory.mktemp("elec")
    df = pd.DataFrame({
        "日期": [date(2025, 6, 1), date(2025, 6, 2)],
        "班次": ["Day", "Day"],
        "设备名称": ["EX-001", "EX-002"],
        "电力消耗": [500.0, 600.0],
    })
    path = tmp / "电力消耗统计.xlsx"
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def sample_production_excel(tmp_path_factory):
    """创建模拟的合并产量.xlsx（两个 sheet）。"""
    tmp = tmp_path_factory.mktemp("prod")
    running = pd.DataFrame({
        "日期": [date(2025, 6, 1)],
        "班次": ["Day"],
        "设备名称": ["CAT785D-01"],
        "公司": ["测试公司"],
        "小时数仪表开始": [100.0],
        "小时数仪表结束": [108.0],
        "运行小时数": [8.0],
        "公里数仪表开始": [1000.0],
        "公里数仪表结束": [1050.0],
        "运行里程": [50.0],
        "趟数": [10],
    })
    production = pd.DataFrame({
        "日期": [date(2025, 6, 1)],
        "班次": ["Day"],
        "矿卡名称": ["CAT785D-01"],
        "挖机名称": ["EX-001"],
        "矿石类型": ["WASTE"],
        "运次": [10],
        "产量": [850.0],
    })
    path = tmp / "合并产量.xlsx"
    with pd.ExcelWriter(path) as writer:
        running.to_excel(writer, sheet_name="运行数据", index=False)
        production.to_excel(writer, sheet_name="生产数据", index=False)
    return path


@pytest.fixture
def sample_worktime_excel(tmp_path_factory):
    """创建模拟的工作效率表。"""
    tmp = tmp_path_factory.mktemp("wt")
    df = pd.DataFrame({
        "日期": ["2025-06-01"],
        "班次": ["Day"],
        "设备名称": ["CAT785D-01"],
        "应运行分钟": [720],
        "停车/换班": [30],
    })
    path = tmp / "202506_工作效率表.xlsx"
    df.to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------------
# load_column_mapping
# ---------------------------------------------------------------------------


class TestLoadColumnMapping:
    def test_load_existing_file(self, sample_mapping):
        path, expected = sample_mapping
        result = load_column_mapping(path)
        assert result == expected

    def test_load_nonexistent_file_returns_defaults(self, tmp_path):
        result = load_column_mapping(tmp_path / "nonexistent.json")
        assert "fuel_consumption" in result
        assert "work_efficiency" in result

    def test_load_default_file(self):
        """默认映射文件应该存在且包含所有 5 种数据类型。"""
        result = load_column_mapping()
        assert "fuel_consumption" in result
        assert "electricity_consumption" in result
        assert "equipment_operation" in result
        assert "production_record" in result
        assert "work_efficiency" in result

    def test_default_mapping_has_remark_fields(self):
        """默认映射应包含 remark 字段映射（有备注列的数据类型）。"""
        result = load_column_mapping()
        assert result["equipment_operation"].get("备注") == "remark"
        assert result["production_record"].get("备注") == "remark"
        assert result["work_efficiency"].get("注释") == "remark"

    def test_default_mapping_has_company_for_operation(self):
        """equipment_operation 映射应包含公司 → company。"""
        result = load_column_mapping()
        assert result["equipment_operation"].get("公司") == "company"


# ---------------------------------------------------------------------------
# read_and_map_excel
# ---------------------------------------------------------------------------


class TestReadAndMapExcel:
    def test_read_fuel(self, sample_fuel_excel, sample_mapping):
        _, mapping = sample_mapping
        rows = read_and_map_excel(sample_fuel_excel, "油耗信息", mapping["fuel_consumption"])
        assert len(rows) == 2
        assert rows[0]["date"] == "2025-06-01"
        assert rows[0]["shiftType"] == "Day"
        assert rows[0]["equipmentName"] == "CAT785D-01"
        assert rows[0]["fuelName"] == "0#柴油"
        assert rows[0]["consumption"] == pytest.approx(150.5)

    def test_read_electrical(self, sample_electrical_excel, sample_mapping):
        _, mapping = sample_mapping
        rows = read_and_map_excel(sample_electrical_excel, None, mapping["electricity_consumption"])
        assert len(rows) == 2
        assert rows[0]["equipmentName"] == "EX-001"
        assert rows[0]["consumption"] == pytest.approx(500.0)

    def test_read_production_running(self, sample_production_excel, sample_mapping):
        _, mapping = sample_mapping
        rows = read_and_map_excel(sample_production_excel, "运行数据", mapping["equipment_operation"])
        assert len(rows) == 1
        assert rows[0]["equipmentName"] == "CAT785D-01"
        assert rows[0]["runningHours"] == pytest.approx(8.0)
        assert rows[0]["tripCount"] == 10

    def test_read_production_production(self, sample_production_excel, sample_mapping):
        _, mapping = sample_mapping
        rows = read_and_map_excel(sample_production_excel, "生产数据", mapping["production_record"])
        assert len(rows) == 1
        assert rows[0]["truckName"] == "CAT785D-01"
        assert rows[0]["excavatorName"] == "EX-001"
        assert rows[0]["production"] == pytest.approx(850.0)

    def test_read_empty_excel(self, tmp_path, sample_mapping):
        _, mapping = sample_mapping
        df = pd.DataFrame(columns=["日期", "班次", "设备名称", "油品种类", "油品消耗"])
        path = tmp_path / "empty.xlsx"
        df.to_excel(path, index=False)
        rows = read_and_map_excel(path, None, mapping["fuel_consumption"])
        assert rows == []

    def test_nan_values_skipped(self, tmp_path, sample_mapping):
        _, mapping = sample_mapping
        df = pd.DataFrame({
            "日期": [date(2025, 6, 1)],
            "班次": ["Day"],
            "设备名称": ["TEST-01"],
            "油品种类": ["0#柴油"],
            "油品消耗": [float("nan")],
        })
        path = tmp_path / "nan.xlsx"
        df.to_excel(path, index=False)
        rows = read_and_map_excel(path, None, mapping["fuel_consumption"])
        assert len(rows) == 1
        assert "consumption" not in rows[0]


# ---------------------------------------------------------------------------
# _build_field_mappings
# ---------------------------------------------------------------------------


class TestBuildFieldMappings:
    def test_fuel_mappings(self, sample_mapping):
        _, mapping = sample_mapping
        result = _build_field_mappings(mapping["fuel_consumption"], "fuel_consumption")
        assert len(result) == 5
        # equipmentName 应有 fkResolve
        equip_mapping = next(m for m in result if m["systemField"] == "equipmentName")
        assert equip_mapping["fkResolve"]["relation"] == "equipment"
        # date 不应有 fkResolve
        date_mapping = next(m for m in result if m["systemField"] == "date")
        assert "fkResolve" not in date_mapping

    def test_production_mappings(self, sample_mapping):
        _, mapping = sample_mapping
        result = _build_field_mappings(mapping["production_record"], "production_record")
        truck_mapping = next(m for m in result if m["systemField"] == "truckName")
        assert truck_mapping["fkResolve"]["relation"] == "truck"
        excavator_mapping = next(m for m in result if m["systemField"] == "excavatorName")
        assert excavator_mapping["fkResolve"]["relation"] == "excavator"
        material_mapping = next(m for m in result if m["systemField"] == "materialTypeName")
        assert material_mapping["fkResolve"]["relation"] == "materialType"


# ---------------------------------------------------------------------------
# _map_row_to_db_columns
# ---------------------------------------------------------------------------


class TestMapRowToDbColumns:
    def test_basic_mapping(self):
        row = {
            "date": "2025-06-01",
            "shiftType": "Day",
            "equipmentName": "TEST-01",
            "equipmentId": "uuid-123",
            "consumption": 150.5,
        }
        columns, values = _map_row_to_db_columns(row)
        assert "date" in columns
        assert "shift_type" in columns
        assert "equipment_name" in columns
        assert "equipment_id" in columns
        assert "consumption" in columns

    def test_unknown_fields_ignored(self):
        row = {"date": "2025-06-01", "unknownField": "value"}
        columns, values = _map_row_to_db_columns(row)
        assert "unknownField" not in columns
        assert len(columns) == 1


# ---------------------------------------------------------------------------
# _apply_defaults
# ---------------------------------------------------------------------------


class TestApplyDefaults:
    def test_electrical_no_shift_gets_night(self):
        rows = [
            {"date": "2025-06-01", "equipmentName": "EX-001", "consumption": 500.0},
            {"date": "2025-06-02", "equipmentName": "EX-002", "consumption": 600.0},
        ]
        result = _apply_defaults(rows, "electrical")
        assert all(r["shiftType"] == "Night" for r in result)
        assert len(result) == 2

    def test_electrical_with_shift_not_overridden(self):
        rows = [
            {"date": "2025-06-01", "shiftType": "Day", "equipmentName": "EX-001", "consumption": 500.0},
        ]
        result = _apply_defaults(rows, "electrical")
        assert result[0]["shiftType"] == "Day"

    def test_non_electrical_not_affected(self):
        rows = [
            {"date": "2025-06-01", "equipmentName": "CAT785D-01", "consumption": 150.0},
        ]
        result = _apply_defaults(rows, "fuel")
        assert "shiftType" not in result[0]

    def test_empty_rows(self):
        result = _apply_defaults([], "electrical")
        assert result == []

    def test_returns_new_list(self):
        """不修改原始列表（不可变性）。"""
        rows = [{"date": "2025-06-01", "consumption": 500.0}]
        result = _apply_defaults(rows, "electrical")
        assert result is not rows
        assert "shiftType" not in rows[0]
        assert result[0]["shiftType"] == "Night"


# ---------------------------------------------------------------------------
# _filter_by_date_range
# ---------------------------------------------------------------------------


class TestFilterByDateRange:
    SAMPLE_ROWS = [
        {"date": "2025-06-01", "equipmentName": "A", "consumption": 100},
        {"date": "2025-06-02", "equipmentName": "B", "consumption": 200},
        {"date": "2025-06-03", "equipmentName": "C", "consumption": 300},
        {"date": "2025-06-04", "equipmentName": "D", "consumption": 400},
    ]

    def test_no_filter_returns_all(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, None, None)
        assert len(result) == 4

    def test_start_date_filter(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, "2025-06-02", None)
        assert len(result) == 3
        assert result[0]["date"] == "2025-06-02"

    def test_end_date_filter(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, None, "2025-06-03")
        assert len(result) == 3
        assert result[-1]["date"] == "2025-06-03"

    def test_both_dates_filter(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, "2025-06-02", "2025-06-03")
        assert len(result) == 2
        assert result[0]["date"] == "2025-06-02"
        assert result[1]["date"] == "2025-06-03"

    def test_exact_date_match(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, "2025-06-03", "2025-06-03")
        assert len(result) == 1
        assert result[0]["date"] == "2025-06-03"

    def test_no_match(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, "2025-07-01", "2025-07-31")
        assert len(result) == 0

    def test_rows_without_date_kept(self):
        rows = [{"equipmentName": "X"}, {"date": "2025-06-01"}]
        result = _filter_by_date_range(rows, "2025-06-02", None)
        assert len(result) == 1  # 无 date 的行保留

    def test_returns_new_list(self):
        result = _filter_by_date_range(self.SAMPLE_ROWS, "2025-06-02", None)
        assert result is not self.SAMPLE_ROWS

    def test_empty_rows(self):
        result = _filter_by_date_range([], "2025-06-01", "2025-06-30")
        assert result == []


# ---------------------------------------------------------------------------
# discover_files (keyword-based)
# ---------------------------------------------------------------------------


class TestDiscoverFiles:
    def test_discover_all(self, tmp_path, sample_fuel_excel, sample_electrical_excel, sample_production_excel, sample_worktime_excel):
        # Copy files to same directory
        import shutil
        shutil.copy(sample_fuel_excel, tmp_path / "Fuel.xlsx")
        shutil.copy(sample_electrical_excel, tmp_path / "电力消耗统计.xlsx")
        shutil.copy(sample_production_excel, tmp_path / "合并产量.xlsx")
        shutil.copy(sample_worktime_excel, tmp_path / "202506_工作效率表.xlsx")

        found = discover_files(tmp_path)
        assert "fuel" in found
        assert "electrical" in found
        assert "operation" in found
        assert "production" in found
        assert "work_efficiency" in found

    def test_discover_partial(self, tmp_path, sample_fuel_excel):
        import shutil
        shutil.copy(sample_fuel_excel, tmp_path / "Fuel.xlsx")
        found = discover_files(tmp_path)
        assert "fuel" in found
        assert "electrical" not in found

    def test_discover_with_keywords(self, tmp_path):
        """关键字匹配模式与 excel_batch 一致。"""
        import shutil
        # 创建带有关键字的文件
        (tmp_path / "Fuel report 2025.xlsx").write_bytes(b"")
        (tmp_path / "工作效率表_2025.xlsx").write_bytes(b"")

        keywords = {
            "fuel": ["Fuel report"],
            "worktime": ["工作效率表"],
        }
        found = discover_files(tmp_path, keywords=keywords)
        assert "fuel" in found
        assert found["fuel"].name == "Fuel report 2025.xlsx"
        assert "work_efficiency" in found

    def test_discover_with_year_month(self, tmp_path):
        """year/month 用于 work_efficiency 文件名匹配。"""
        (tmp_path / "202501_工作效率表.xlsx").write_bytes(b"")
        (tmp_path / "202506_工作效率表.xlsx").write_bytes(b"")

        found = discover_files(tmp_path, year=2025, month=6, keywords={})
        assert "work_efficiency" in found
        assert "202506" in found["work_efficiency"].name


# ---------------------------------------------------------------------------
# MineBaseAPIClient
# ---------------------------------------------------------------------------


class TestMineBaseAPIClient:
    def test_init(self):
        client = MineBaseAPIClient("http://localhost:3000", "admin", "pass")
        assert client.base_url == "http://localhost:3000"
        assert client.token is None

    def test_init_trailing_slash(self):
        client = MineBaseAPIClient("http://localhost:3000/", "admin", "pass")
        assert client.base_url == "http://localhost:3000"


# ---------------------------------------------------------------------------
# sync (integration with mocks)
# ---------------------------------------------------------------------------


class TestSyncAPI:
    @patch("func.sync_to_minebase.MineBaseAPIClient")
    def test_sync_fuel_dry_run(self, mock_api_cls, tmp_path, sample_fuel_excel, sample_mapping):
        import shutil
        mapping_path, _ = sample_mapping
        shutil.copy(sample_fuel_excel, tmp_path / "Fuel.xlsx")

        results = sync(tmp_path, mode="api", data_types=["fuel"], dry_run=True, mapping_file=mapping_path)
        assert "fuel" in results
        assert results["fuel"]["success"] == 0  # dry-run

    @patch("func.sync_to_minebase.MineBaseAPIClient")
    def test_sync_no_files(self, mock_api_cls, tmp_path, sample_mapping):
        mapping_path, _ = sample_mapping
        results = sync(tmp_path, mode="api", mapping_file=mapping_path)
        assert results == {}


class TestSyncDB:
    @patch("func.sync_to_minebase.MineBaseDBClient")
    def test_sync_fuel_dry_run(self, mock_db_cls, tmp_path, sample_fuel_excel, sample_mapping):
        import shutil
        mapping_path, _ = sample_mapping
        shutil.copy(sample_fuel_excel, tmp_path / "Fuel.xlsx")

        results = sync(tmp_path, mode="database", data_types=["fuel"], dry_run=True, mapping_file=mapping_path)
        assert "fuel" in results
        assert results["fuel"]["success"] == 0


# ---------------------------------------------------------------------------
# config_loader MineBase 配置
# ---------------------------------------------------------------------------


class TestMineBaseConfig:
    def test_get_minebase_config_defaults(self, monkeypatch):
        from func import config_loader
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", pathlib.Path("/nonexistent"))
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", pathlib.Path("/nonexistent"))
        cfg = config_loader.get_minebase_config()
        assert cfg["mode"] == "api"
        assert cfg["api"]["url"] == "http://localhost:3000"
        assert cfg["database"]["port"] == 5432

    def test_get_minebase_mode_default(self, monkeypatch):
        from func import config_loader
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", pathlib.Path("/nonexistent"))
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", pathlib.Path("/nonexistent"))
        assert config_loader.get_minebase_mode() == "api"
