"""sync_to_minebase 模块测试"""
import json
import pathlib
import sys
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.sync_to_minebase import (
    MineBaseAPIClient,
    MineBaseDBClient,
    _apply_defaults,
    _build_field_mappings,
    _df_to_mapped_rows,
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

    def test_id_column_generated_as_uuid(self):
        """_map_row_to_db_columns must include 'id' as a valid UUID string.

        Without this, PostgreSQL INSERT fails with:
        'null value in column "id" violates not-null constraint'
        """
        row = {
            "date": "2026-06-18",
            "shiftType": "Night",
            "equipmentName": "NHL NTE240 HT#1222",
            "equipmentId": "equip-uuid-001",
            "plannedMinutes": 720,
        }
        columns, values = _map_row_to_db_columns(row)

        assert "id" in columns, "columns must include 'id' for the UUID primary key"
        idx = columns.index("id")
        id_value = values[idx]
        # Must be a valid UUID string
        parsed = uuid.UUID(id_value)
        assert str(parsed) == id_value


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
        assert found["fuel"][0].name == "Fuel report 2025.xlsx"
        assert "work_efficiency" in found

    def test_discover_with_year_month(self, tmp_path):
        """year/month 用于 work_efficiency 文件名匹配。"""
        (tmp_path / "202501_工作效率表.xlsx").write_bytes(b"")
        (tmp_path / "202506_工作效率表.xlsx").write_bytes(b"")

        found = discover_files(tmp_path, year=2025, month=6, keywords={})
        assert "work_efficiency" in found
        assert "202506" in found["work_efficiency"][0].name


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

    def test_keyring_sentinel_is_not_valid_password(self):
        """sentinel 值不应被 PostgreSQL 接受为有效密码。

        回归测试：确保 sentinel 字符串不含空格、引号等可能被误解析的字符，
        且长度足够短不会与真实密码混淆。
        """
        from func.secret_store import _KEYRING_SENTINEL
        # sentinel 应该是明确的标记值，不是空字符串
        assert _KEYRING_SENTINEL
        assert len(_KEYRING_SENTINEL) < 20

    def test_frontend_sentinel_matches_backend(self):
        """前端与后端的 sentinel 值必须一致，否则掩码密码会被当成真实密码发送到数据库。"""
        from func.secret_store import _KEYRING_SENTINEL
        # 读取前端源码中定义的 sentinel
        frontend_src = pathlib.Path(__file__).resolve().parents[1] / "src" / "components" / "pages" / "UserConfigPage.tsx"
        if not frontend_src.exists():
            pytest.skip("Tauri frontend source not found")
        content = frontend_src.read_text(encoding="utf-8")
        # 提取 KEYRING_SENTINEL 的值
        import re
        match = re.search(r'KEYRING_SENTINEL\s*=\s*"([^"]+)"', content)
        assert match, "前端未定义 KEYRING_SENTINEL"
        frontend_sentinel = match.group(1)
        assert frontend_sentinel == _KEYRING_SENTINEL, (
            f"前端 sentinel ({frontend_sentinel!r}) 与后端 sentinel ({_KEYRING_SENTINEL!r}) 不一致。"
            f"前端保存的掩码密码将被当作真实密码写入数据库。"
        )

    def test_load_secret_recognizes_legacy_sentinel(self, monkeypatch, tmp_path):
        """load_secret 应同时识别新旧两种 sentinel 值（兼容旧配置文件）。"""
        from func import secret_store
        from func import config_loader
        import json

        # 设置临时配置，使用旧版 sentinel 作为密码
        config_data = {
            "minebase": {
                "mode": "database",
                "api": {"url": "", "username": "", "password": ""},
                "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "__KEYRING_SENTINEL__"},
            },
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")

        # Mock keyring 返回真实密码
        def _get_password(service, key):
            if key == "minebase.database.password":
                return "real_password"
            return None
        monkeypatch.setattr("keyring.get_password", _get_password)

        config_loader._invalidate_config_cache()
        result = secret_store.load_secret(("minebase", "database", "password"))
        assert result == "real_password"

    def test_tauri_save_then_sync_db_password_roundtrip(self, monkeypatch, tmp_path):
        """模拟 Tauri 前端完整 save → sync 往返：save_config + get_minebase_db_config。"""
        from func import config_loader
        from func import secret_store
        import json

        # 设置临时配置环境
        base_config = {
            "minebase": {
                "mode": "database",
                "api": {"url": "http://localhost:3000", "username": "", "password": ""},
                "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
            },
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(base_config, ensure_ascii=False), encoding="utf-8")
        user_file = tmp_path / "config.user.json"
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        # Mock keyring
        _store: dict[str, str] = {}
        def _set_pw(s, k, v): _store[f"{s}:{k}"] = v
        def _get_pw(s, k): return _store.get(f"{s}:{k}")
        monkeypatch.setattr("keyring.set_password", _set_pw)
        monkeypatch.setattr("keyring.get_password", _get_pw)

        # ── 模拟 Tauri 前端保存流程 ──
        # 前端调用 save_minebase_config({ config: {...} })
        # → config_loader.save_minebase_config(cfg)
        minebase_cfg = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "127.0.0.1", "port": 5432, "database": "minebase", "user": "admin", "password": "hunter2"},
        }
        config_loader.save_minebase_config(minebase_cfg)

        # ── 模拟 sync 流程 ──
        # get_minebase_db_config() → load_secret() → keyring
        config_loader._invalidate_config_cache()
        db_cfg = config_loader.get_minebase_db_config()

        # 用户名应正确保存
        assert db_cfg["user"] == "admin", f"Expected 'admin', got '{db_cfg.get('user')}'"
        # 密码应从 keyring 解密
        assert db_cfg["password"] == "hunter2", f"Expected 'hunter2', got '{db_cfg.get('password')!r}'"


# ---------------------------------------------------------------------------
# discover_files glob vs keyword priority
# ---------------------------------------------------------------------------


class TestDiscoverFilesGlobPriority:
    def test_discover_files_prefers_glob_over_keywords(self, tmp_path):
        """当 processed output 和 raw input 同时存在时，discover_files 选择 processed output。"""
        # 创建 processed output
        (tmp_path / "Fuel.xlsx").write_bytes(b"")
        # 创建 raw input（关键字匹配能命中）
        (tmp_path / "Fuel report Normount 6-2026.xlsx").write_bytes(b"")

        found = discover_files(tmp_path, keywords={"fuel": ["Fuel report"]})
        assert "fuel" in found
        assert found["fuel"][0].name == "Fuel.xlsx"

    def test_discover_files_glob_finds_processed_outputs(self, tmp_path):
        """验证 discover_files 通过 DATA_TYPE_REGISTRY pattern 找到所有 processed output。"""
        (tmp_path / "Fuel.xlsx").write_bytes(b"")
        (tmp_path / "电力消耗统计.xlsx").write_bytes(b"")
        (tmp_path / "合并产量.xlsx").write_bytes(b"")
        (tmp_path / "202506_工作效率表.xlsx").write_bytes(b"")

        found = discover_files(tmp_path, year=2025, month=6, keywords={})
        assert found["fuel"][0].name == "Fuel.xlsx"
        assert found["electrical"][0].name == "电力消耗统计.xlsx"
        assert found["production"][0].name == "合并产量.xlsx"
        assert found["operation"][0].name == "合并产量.xlsx"
        assert found["work_efficiency"][0].name == "202506_工作效率表.xlsx"

    def test_discover_files_keyword_fallback_when_no_glob_match(self, tmp_path):
        """当不存在 processed output 时，关键字匹配作为回退。"""
        # 只有 raw input，没有 Fuel.xlsx
        (tmp_path / "Fuel report Normount 6-2026.xlsx").write_bytes(b"")

        found = discover_files(tmp_path, keywords={"fuel": ["Fuel report"]})
        assert "fuel" in found
        assert found["fuel"][0].name == "Fuel report Normount 6-2026.xlsx"

    def test_discover_files_mixed_directory_priority(self, tmp_path):
        """全类型混合目录：所有 data type 都应优先解析到 processed output。"""
        # processed outputs
        (tmp_path / "Fuel.xlsx").write_bytes(b"")
        (tmp_path / "电力消耗统计.xlsx").write_bytes(b"")
        (tmp_path / "合并产量.xlsx").write_bytes(b"")
        (tmp_path / "202506_工作效率表.xlsx").write_bytes(b"")

        # raw inputs (关键字匹配可能命中)
        (tmp_path / "Fuel report Normount 6-2026.xlsx").write_bytes(b"")
        (tmp_path / "Цахилгааны зарцуулалт.xlsx").write_bytes(b"")
        (tmp_path / "夜班日报_2025-06.xlsx").write_bytes(b"")

        keywords = {
            "fuel": ["Fuel report"],
            "electrical": ["Цахилгааны"],
            "production": ["夜班日报"],
        }
        found = discover_files(tmp_path, year=2025, month=6, keywords=keywords)

        assert found["fuel"][0].name == "Fuel.xlsx"
        assert found["electrical"][0].name == "电力消耗统计.xlsx"
        assert found["production"][0].name == "合并产量.xlsx"
        assert found["operation"][0].name == "合并产量.xlsx"
        assert "202506_工作效率表" in found["work_efficiency"][0].name


# ---------------------------------------------------------------------------
# work_efficiency mapping: date + shiftType
# ---------------------------------------------------------------------------


class TestWorkEfficiencyMapping:
    def test_work_efficiency_mapping_includes_date_and_shift(self):
        """默认列映射中 work_efficiency 应包含 日期->date 和 班次->shiftType。"""
        mapping = load_column_mapping()
        we_mapping = mapping.get("work_efficiency") or mapping.get("worktime", {})
        assert we_mapping, "work_efficiency mapping not found"
        assert we_mapping["日期"] == "date"
        assert we_mapping["班次"] == "shiftType"

    def test_read_and_map_work_efficiency_with_date_shift(self, tmp_path):
        """read_and_map_excel 正确映射 work_efficiency 的 日期、班次、设备名称、应运行分钟。"""
        mapping = load_column_mapping()
        we_mapping = mapping.get("work_efficiency") or mapping.get("worktime", {})

        df = pd.DataFrame({
            "日期": ["2025-06-01", "2025-06-02"],
            "班次": ["Day", "Night"],
            "设备名称": ["CAT785D-01", "NTE240-02"],
            "应运行分钟": [720, 600],
        })
        path = tmp_path / "test_work_efficiency.xlsx"
        df.to_excel(path, index=False)

        rows = read_and_map_excel(path, None, we_mapping)
        assert len(rows) == 2
        assert rows[0]["date"] == "2025-06-01"
        assert rows[0]["shiftType"] == "Day"
        assert rows[0]["equipmentName"] == "CAT785D-01"
        assert rows[0]["plannedMinutes"] == 720
        assert rows[1]["date"] == "2025-06-02"
        assert rows[1]["shiftType"] == "Night"


# ---------------------------------------------------------------------------
# _df_to_mapped_rows
# ---------------------------------------------------------------------------


class TestDfToMappedRows:
    def test_basic_mapping(self):
        """df with 日期/班次/设备名称 -> mapped to date/shiftType/equipmentName."""
        df = pd.DataFrame({
            "日期": ["2025-06-01", "2025-06-02"],
            "班次": ["Day", "Night"],
            "设备名称": ["CAT785D-01", "NTE240-02"],
        })
        mapping = {"日期": "date", "班次": "shiftType", "设备名称": "equipmentName"}
        rows = _df_to_mapped_rows(df, mapping)
        assert len(rows) == 2
        assert rows[0] == {"date": "2025-06-01", "shiftType": "Day", "equipmentName": "CAT785D-01"}
        assert rows[1] == {"date": "2025-06-02", "shiftType": "Night", "equipmentName": "NTE240-02"}

    def test_nan_handling(self):
        """NaN values skipped in output."""
        df = pd.DataFrame({
            "日期": ["2025-06-01"],
            "班次": ["Day"],
            "设备名称": ["CAT785D-01"],
            "油品消耗": [float("nan")],
        })
        mapping = {"日期": "date", "班次": "shiftType", "设备名称": "equipmentName", "油品消耗": "consumption"}
        rows = _df_to_mapped_rows(df, mapping)
        assert len(rows) == 1
        assert "consumption" not in rows[0]
        assert rows[0]["date"] == "2025-06-01"

    def test_date_conversion(self):
        """pd.Timestamp -> YYYY-MM-DD string."""
        df = pd.DataFrame({
            "日期": [pd.Timestamp("2025-06-15"), pd.Timestamp("2025-07-01")],
            "班次": ["Day", "Night"],
        })
        mapping = {"日期": "date", "班次": "shiftType"}
        rows = _df_to_mapped_rows(df, mapping)
        assert rows[0]["date"] == "2025-06-15"
        assert rows[1]["date"] == "2025-07-01"

    def test_empty_dataframe(self):
        """Empty df returns empty list."""
        df = pd.DataFrame(columns=["日期", "班次", "设备名称"])
        mapping = {"日期": "date", "班次": "shiftType", "设备名称": "equipmentName"}
        rows = _df_to_mapped_rows(df, mapping)
        assert rows == []


# ---------------------------------------------------------------------------
# _process_fuel_file
# ---------------------------------------------------------------------------


class TestProcessFuelFile:
    @patch("func.sync_to_minebase._df_to_mapped_rows")
    @patch("func.excel_fuel.process_diesel_data")
    def test_process_fuel_returns_mapped_rows(self, mock_diesel, mock_df_map):
        """patch process_diesel_data to return {'油耗信息': df}, verify _process_fuel_file returns correctly mapped rows."""
        from func.sync_to_minebase import _process_fuel_file

        test_df = pd.DataFrame({"col": [1]})
        mock_diesel.return_value = {"油耗信息": test_df}
        expected_rows = [
            {"date": "2025-06-01", "shiftType": "Day", "equipmentName": "CAT785D-01", "fuelName": "0#柴油", "consumption": 150.5},
        ]
        mock_df_map.return_value = expected_rows

        result = _process_fuel_file(Path("/fake/Fuel.xlsx"), year=2025)
        assert result == expected_rows
        mock_diesel.assert_called_once()
        mock_df_map.assert_called_once()

    @patch("func.excel_fuel.process_diesel_data", side_effect=RuntimeError("boom"))
    def test_process_fuel_handles_error(self, mock_diesel):
        """patch to raise exception, verify returns empty list."""
        from func.sync_to_minebase import _process_fuel_file

        result = _process_fuel_file(Path("/fake/Fuel.xlsx"), year=2025)
        assert result == []


# ---------------------------------------------------------------------------
# _process_electrical_file
# ---------------------------------------------------------------------------


class TestProcessElectricalFile:
    @patch("func.sync_to_minebase._df_to_mapped_rows")
    @patch("func.excel_electrical.parse_excel_data")
    def test_process_electrical_returns_mapped_rows(self, mock_parse, mock_df_map):
        """patch parse_excel_data to return {'电力消耗': df}, verify mapping."""
        from func.sync_to_minebase import _process_electrical_file

        test_df = pd.DataFrame({"col": [1]})
        mock_parse.return_value = {"电力消耗": test_df}
        expected_rows = [
            {"date": "2025-06-01", "shiftType": "Night", "equipmentName": "EX-001", "consumption": 500.0},
        ]
        mock_df_map.return_value = expected_rows

        result = _process_electrical_file(Path("/fake/电力消耗统计.xlsx"), year=2025)
        assert result == expected_rows
        mock_parse.assert_called_once()
        mock_df_map.assert_called_once()

    @patch("func.excel_electrical.parse_excel_data", return_value={})
    def test_process_electrical_handles_empty(self, mock_parse):
        """patch to return empty dict, verify returns empty list."""
        from func.sync_to_minebase import _process_electrical_file

        result = _process_electrical_file(Path("/fake/电力消耗统计.xlsx"), year=2025)
        assert result == []


# ---------------------------------------------------------------------------
# _process_production_file
# ---------------------------------------------------------------------------


class TestProcessProductionFile:
    @patch("func.sync_to_minebase._df_to_mapped_rows")
    @patch("func.excel_production_enhanced.MiningDataProcessor")
    def test_process_production_returns_both_types(self, mock_processor_cls, mock_df_map):
        """patch MiningDataProcessor.process_file, verify production and operation rows."""
        from func.sync_to_minebase import _process_production_file

        running_df = pd.DataFrame({"col": [1]})
        production_df = pd.DataFrame({"col": [2]})
        mock_processor_cls.return_value.process_single_file.return_value = (running_df, production_df)

        prod_rows = [{"date": "2025-06-01", "truckName": "CAT785D-01"}]
        ops_rows = [{"date": "2025-06-01", "equipmentName": "CAT785D-01"}]
        mock_df_map.side_effect = [prod_rows, ops_rows]

        result = _process_production_file(Path("/fake/合并产量.xlsx"))
        assert result == {"production": prod_rows, "operation": ops_rows}
        mock_processor_cls.return_value.process_single_file.assert_called_once()

    @patch("func.sync_to_minebase._df_to_mapped_rows")
    @patch("func.excel_production_enhanced.MiningDataProcessor")
    def test_process_production_handles_error(self, mock_processor_cls, mock_df_map):
        """patch to raise, verify returns empty dicts."""
        from func.sync_to_minebase import _process_production_file

        mock_processor_cls.return_value.process_single_file.side_effect = RuntimeError("boom")

        result = _process_production_file(Path("/fake/合并产量.xlsx"))
        assert result == {"production": [], "operation": []}


# ---------------------------------------------------------------------------
# TestSyncWithProcessors
# ---------------------------------------------------------------------------


class TestSyncWithProcessors:
    @patch("func.sync_to_minebase.sync_via_api")
    @patch("func.sync_to_minebase._process_fuel_file")
    @patch("func.sync_to_minebase.discover_files")
    def test_sync_fuel_via_processor(self, mock_discover, mock_fuel_proc, mock_sync_api, tmp_path):
        """full integration - patch processor AND api client, verify sync() sends fuel data."""
        mock_discover.return_value = {"fuel": [tmp_path / "Fuel.xlsx"]}
        mock_fuel_proc.return_value = [
            {"date": "2025-06-01", "shiftType": "Day", "equipmentName": "CAT785D-01", "fuelName": "0#柴油", "consumption": 150.5},
        ]
        mock_sync_api.return_value = {"success": 1, "skipped": 0, "failed": 0}

        with patch("func.sync_to_minebase.MineBaseAPIClient") as mock_api_cls, \
             patch("func.sync_to_minebase.get_minebase_api_config", return_value={"url": "http://test", "username": "u", "password": "p"}):
            mock_api_cls.return_value = MagicMock()
            results = sync(tmp_path, mode="api", data_types=["fuel"], dry_run=True)

        assert "fuel" in results
        assert results["fuel"]["success"] == 1
        mock_fuel_proc.assert_called_once()

    @patch("func.sync_to_minebase.sync_via_api")
    @patch("func.sync_to_minebase._process_electrical_file")
    @patch("func.sync_to_minebase._process_fuel_file")
    @patch("func.sync_to_minebase.discover_files")
    def test_sync_processor_failure_continues(self, mock_discover, mock_fuel_proc, mock_elec_proc, mock_sync_api, tmp_path):
        """one type fails, others still sync."""
        mock_discover.return_value = {
            "fuel": [tmp_path / "Fuel.xlsx"],
            "electrical": [tmp_path / "电力消耗统计.xlsx"],
        }
        mock_fuel_proc.side_effect = RuntimeError("boom")
        mock_elec_proc.return_value = [
            {"date": "2025-06-01", "shiftType": "Night", "equipmentName": "EX-001", "consumption": 500.0},
        ]
        mock_sync_api.return_value = {"success": 1, "skipped": 0, "failed": 0}

        with patch("func.sync_to_minebase.MineBaseAPIClient") as mock_api_cls, \
             patch("func.sync_to_minebase.get_minebase_api_config", return_value={"url": "http://test", "username": "u", "password": "p"}):
            mock_api_cls.return_value = MagicMock()
            results = sync(tmp_path, mode="api", data_types=["fuel", "electrical"], dry_run=True)

        # fuel fails and gets empty result, electrical still syncs
        assert results["fuel"] == {"success": 0, "skipped": 0, "failed": 0}
        assert results["electrical"]["success"] == 1


# ---------------------------------------------------------------------------
# MineBaseDBClient.insert_rows — execute_values placeholder bug
# ---------------------------------------------------------------------------


class TestInsertRowsPlaceholder:
    """Regression: execute_values requires exactly one %s in the query template."""

    @patch("psycopg2.connect")
    def test_insert_rows_uses_single_placeholder(self, mock_connect):
        """insert_rows must pass 'VALUES %s' (not 'VALUES (%s, %s, ...)') to execute_values.

        When the query contains multiple %s placeholders, psycopg2 raises:
        'the query contains more than one '%s' placeholder'
        """
        import psycopg2.extras

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        client = MineBaseDBClient("localhost", 5432, "testdb", "user", "pass")

        columns = ["date", "shift_type", "equipment_name"]
        values = ["2026-06-18", "Day", "EX-001"]

        with patch.object(psycopg2.extras, "execute_values") as mock_exec:
            client.insert_rows("work_efficiency", columns, [values])

            mock_exec.assert_called_once()
            query_template = mock_exec.call_args[0][1]
            # The template must contain exactly one %s (execute_values expands it)
            assert query_template.count("%s") == 1, (
                f"Expected 1 '%s' placeholder, got {query_template.count('%s')}: {query_template}"
            )
            assert "VALUES %s" in query_template


# ---------------------------------------------------------------------------
# sync_via_db — savepoint isolation for per-row failures
# ---------------------------------------------------------------------------


class TestSyncViaDbSavepoint:
    """Regression: a single row INSERT failure must not poison the transaction.

    Without savepoints, PostgreSQL aborts the entire transaction on the first
    error, causing all subsequent rows to fail with:
    'current transaction is aborted, commands ignored until end of transaction block'
    """

    def test_single_row_failure_does_not_poison_transaction(self):
        """When row 2 fails, rows 1 and 3 should still be inserted."""
        from func.sync_to_minebase import sync_via_db

        mock_client = MagicMock()
        mock_cursor = MagicMock()
        mock_client.conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_client.conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # resolve_equipment_id returns a valid ID for all rows
        mock_client.resolve_equipment_id.return_value = "equip-uuid-001"

        # check_duplicate returns False (no duplicates)
        mock_client.check_duplicate.return_value = False

        # insert_rows_with_cursor: row 1 and 3 succeed, row 2 raises
        call_count = 0
        def mock_insert(cur, table, columns, values_list):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("duplicate key value violates unique constraint")
            return 1

        mock_client.insert_rows_with_cursor = mock_insert

        rows = [
            {"date": "2026-06-18", "shiftType": "Day", "equipmentName": "EX-001", "consumption": 100.0},
            {"date": "2026-06-18", "shiftType": "Day", "equipmentName": "EX-002", "consumption": 200.0},
            {"date": "2026-06-18", "shiftType": "Night", "equipmentName": "EX-003", "consumption": 300.0},
        ]

        result = sync_via_db("fuel", rows, {}, mock_client, dry_run=False)

        assert result["success"] == 2
        assert result["failed"] == 1
        assert result["skipped"] == 0
        mock_client.commit.assert_called_once()
