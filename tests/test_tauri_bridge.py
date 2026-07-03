"""tauri_bridge RPC 方法测试"""
import importlib.util
import json
import pathlib
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tauri_bridge

_has_psycopg2 = importlib.util.find_spec("psycopg2") is not None


# ---------------------------------------------------------------------------
# _post_process_ledger
# ---------------------------------------------------------------------------


class TestPostProcessLedger:
    """台账匹配后处理测试。"""

    def _write_excel(self, tmp_path, sheets: dict[str, pd.DataFrame]) -> str:
        path = str(tmp_path / "output.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            for name, df in sheets.items():
                df.to_excel(w, sheet_name=name, index=False)
        return path

    def test_skip_when_both_false(self, tmp_path):
        """两个开关都为 False 时不执行任何操作。"""
        path = self._write_excel(tmp_path, {"s": pd.DataFrame({"a": [1]})})
        tauri_bridge._post_process_ledger(path, use_equipment_ledger=False, use_oil_ledger=False)
        df = pd.read_excel(path)
        assert list(df.columns) == ["a"]

    def test_skip_when_no_cache(self, tmp_path):
        """无缓存台账时不修改文件。"""
        path = self._write_excel(tmp_path, {
            "s": pd.DataFrame({"日期": ["2025-01-01"], "设备名称": ["卡车A"]}),
        })
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=False), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            tauri_bridge._post_process_ledger(path, use_equipment_ledger=True, use_oil_ledger=True)
        df = pd.read_excel(path)
        assert "标准设备名称" not in df.columns

    def test_equipment_match_single_column(self, tmp_path):
        """单列设备名称匹配。"""
        path = self._write_excel(tmp_path, {
            "设备信息": pd.DataFrame({
                "日期": ["2025-01-01"],
                "设备名称": ["卡车NTE240-001"],
                "设备编号": ["001"],
            }),
        })
        mock_ledger_data = [{"设备名称": "卡车NTE240-001", "标准设备名称": "NTE240", "标准设备编号": "001", "标准公司名称": "公司A"}]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_ledger_data), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            tauri_bridge._post_process_ledger(path, use_equipment_ledger=True, use_oil_ledger=False)
        df = pd.read_excel(path)
        assert "标准设备名称" in df.columns
        assert df["标准设备名称"].iloc[0] == "NTE240"
        assert "标准公司名称" in df.columns

    def test_oil_match(self, tmp_path):
        """油品匹配。"""
        path = self._write_excel(tmp_path, {
            "油耗": pd.DataFrame({
                "日期": ["2025-01-01"],
                "设备名称": ["卡车A"],
                "油品种类": ["0号柴油"],
                "油品消耗": [100],
            }),
        })
        mock_eq_data = []
        mock_oil_data = [{"油品名称": "0号柴油", "标准油品名称": "柴油"}]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_eq_data), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=True), \
             patch("func.config_loader.load_oil_ledger_cache", return_value=mock_oil_data):
            tauri_bridge._post_process_ledger(path, use_equipment_ledger=True, use_oil_ledger=True)
        df = pd.read_excel(path)
        assert "标准油品名称" in df.columns

    def test_production_dual_column(self, tmp_path):
        """生产数据矿卡+挖机双列匹配（后缀区分）。"""
        path = self._write_excel(tmp_path, {
            "生产数据": pd.DataFrame({
                "日期": ["2025-01-01"],
                "矿卡名称": ["NTE240-001"],
                "挖机名称": ["EX2600-01"],
                "矿石类型": ["矿石"],
                "运次": [5],
            }),
        })
        mock_eq_data = [
            {"设备名称": "NTE240-001", "标准设备名称": "NTE240", "标准设备编号": "001", "标准公司名称": "A"},
            {"设备名称": "EX2600-01", "标准设备名称": "EX2600", "标准设备编号": "E01", "标准公司名称": "B"},
        ]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_eq_data), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            tauri_bridge._post_process_ledger(path, use_equipment_ledger=True, use_oil_ledger=False)
        df = pd.read_excel(path)
        assert "标准设备名称（矿卡）" in df.columns
        assert "标准设备名称（挖机）" in df.columns
        assert df["标准设备名称（矿卡）"].iloc[0] == "NTE240"
        assert df["标准设备名称（挖机）"].iloc[0] == "EX2600"

    def test_equipment_only_skip_oil(self, tmp_path):
        """仅启用设备台账匹配时，油品列不匹配。"""
        path = self._write_excel(tmp_path, {
            "数据": pd.DataFrame({
                "日期": ["2025-01-01"],
                "设备名称": ["卡车A"],
                "油品种类": ["0号柴油"],
            }),
        })
        mock_eq_data = [
            {"设备名称": "卡车A", "标准设备名称": "NTE240", "标准设备编号": "001", "标准公司名称": "A"},
        ]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_eq_data):
            tauri_bridge._post_process_ledger(path, use_equipment_ledger=True, use_oil_ledger=False)
        df = pd.read_excel(path)
        assert "标准设备名称" in df.columns
        assert "标准油品名称" not in df.columns

    def test_oil_only_skip_equipment(self, tmp_path):
        """仅启用油品台账匹配时，设备列不匹配。"""
        path = self._write_excel(tmp_path, {
            "数据": pd.DataFrame({
                "日期": ["2025-01-01"],
                "设备名称": ["卡车A"],
                "油品种类": ["0号柴油"],
            }),
        })
        mock_oil_data = [{"油品名称": "0号柴油", "标准油品名称": "柴油"}]
        with patch("func.config_loader.has_oil_ledger_cache", return_value=True), \
             patch("func.config_loader.load_oil_ledger_cache", return_value=mock_oil_data):
            tauri_bridge._post_process_ledger(path, use_equipment_ledger=False, use_oil_ledger=True)
        df = pd.read_excel(path)
        assert "标准油品名称" in df.columns
        assert "标准设备名称" not in df.columns


# ---------------------------------------------------------------------------
# process_fuel RPC — regression: must return output file path
# ---------------------------------------------------------------------------


class TestProcessFuelRPC:
    """process_fuel handler 测试。"""

    def test_returns_output_file_path(self, tmp_path):
        """process_fuel 必须返回 output_file 以便应用台账匹配。"""
        input_file = str(tmp_path / "fuel_input.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)

        expected_output = str(tmp_path / "Fuel.xlsx")
        with patch("func.excel_fuel.process_diesel_data", return_value=expected_output), \
             patch.object(tauri_bridge, "_post_process_ledger") as mock_post:
            result = tauri_bridge._process_fuel({
                "path": input_file,
                "use_equipment_ledger": True,
                "use_oil_ledger": True,
            })
        assert result["output_file"] == expected_output
        mock_post.assert_called_once_with(
            expected_output,
            use_equipment_ledger=True,
            use_oil_ledger=True,
        )

    def test_no_post_process_when_ledger_disabled(self, tmp_path):
        """台账匹配禁用时 _post_process_ledger 收到 False 参数（内部早返回）。"""
        input_file = str(tmp_path / "fuel_input.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)

        expected_output = str(tmp_path / "Fuel.xlsx")
        with patch("func.excel_fuel.process_diesel_data", return_value=expected_output), \
             patch.object(tauri_bridge, "_post_process_ledger") as mock_post:
            result = tauri_bridge._process_fuel({
                "path": input_file,
                "use_equipment_ledger": False,
                "use_oil_ledger": False,
            })
        assert result["output_file"] == expected_output
        mock_post.assert_called_once_with(
            expected_output,
            use_equipment_ledger=False,
            use_oil_ledger=False,
        )

    def test_returns_none_when_processing_fails(self, tmp_path):
        """处理失败时 output_file 为 None，不调用台账匹配。"""
        input_file = str(tmp_path / "bad.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)

        with patch("func.excel_fuel.process_diesel_data", return_value=None), \
             patch.object(tauri_bridge, "_post_process_ledger") as mock_post:
            result = tauri_bridge._process_fuel({"path": input_file})
        assert result["output_file"] is None
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# get_config RPC
# ---------------------------------------------------------------------------


class TestGetConfigRPC:
    """get_config handler 测试。"""

    def test_key_minebase(self):
        """minebase key 应返回合并后的配置。"""
        with patch("tauri_bridge._register", lambda name: (lambda fn: fn)):
            pass
        result = tauri_bridge._get_config({"key": "minebase"})
        assert "mode" in result
        assert "api" in result
        assert "database" in result

    def test_key_file_keywords(self):
        """file_keywords key 应返回关键字配置。"""
        result = tauri_bridge._get_config({"key": "file_keywords"})
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_key_worktime_header_mapping(self):
        """worktime_header_mapping key 应返回表头映射。"""
        result = tauri_bridge._get_config({"key": "worktime_header_mapping"})
        assert isinstance(result, dict)
        assert "entries" in result or "mode" in result

    def test_no_key_returns_full_config(self):
        """无 key 时返回完整配置。"""
        result = tauri_bridge._get_config({})
        assert "minebase" in result
        assert "shift_mapping" in result

    def test_unknown_key_returns_empty(self):
        """未知 key 返回空 dict。"""
        result = tauri_bridge._get_config({"key": "nonexistent"})
        assert result == {}


# ---------------------------------------------------------------------------
# test_minebase_connection RPC
# ---------------------------------------------------------------------------


class TestMinebaseConnectionRPC:
    """test_minebase_connection handler 测试。"""

    def test_api_mode_success(self):
        with patch("func.sync_to_minebase.test_api_connection", return_value=(True, "连接成功")):
            result = tauri_bridge._test_minebase_connection({"mode": "api", "url": "http://x", "username": "u", "password": "p"})
        assert result["success"] is True
        assert "连接成功" in result["message"]

    def test_api_mode_failure(self):
        with patch("func.sync_to_minebase.test_api_connection", return_value=(False, "连接失败")):
            result = tauri_bridge._test_minebase_connection({"mode": "api", "url": "http://x", "username": "u", "password": "p"})
        assert result["success"] is False

    def test_db_mode_success(self):
        with patch("func.sync_to_minebase.test_db_connection", return_value=(True, "连接成功")):
            result = tauri_bridge._test_minebase_connection({"mode": "database", "host": "h", "port": 5432, "database": "d", "user": "u", "password": "p"})
        assert result["success"] is True

    def test_db_mode_failure(self):
        with patch("func.sync_to_minebase.test_db_connection", return_value=(False, "拒绝连接")):
            result = tauri_bridge._test_minebase_connection({"mode": "database", "host": "h", "port": 5432, "database": "d", "user": "u", "password": "p"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# test_api_connection / test_db_connection
# ---------------------------------------------------------------------------


class TestConnectionFunctions:
    """底层连接测试函数。"""

    def test_api_connection_success(self):
        mock_client = MagicMock()
        with patch("func.sync_to_minebase.MineBaseAPIClient", return_value=mock_client):
            from func.sync_to_minebase import test_api_connection
            ok, msg = test_api_connection("http://localhost:3000", "admin", "pass")
        assert ok is True
        assert "连接成功" in msg
        mock_client.login.assert_called_once()

    def test_api_connection_failure(self):
        mock_client = MagicMock()
        mock_client.login.side_effect = RuntimeError("HTTP 401: Unauthorized")
        with patch("func.sync_to_minebase.MineBaseAPIClient", return_value=mock_client):
            from func.sync_to_minebase import test_api_connection
            ok, msg = test_api_connection("http://localhost:3000", "admin", "wrong")
        assert ok is False
        assert "401" in msg

    @pytest.mark.skipif(not _has_psycopg2, reason="psycopg2 not installed (optional 'db' extra)")
    def test_db_connection_success(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        with patch("psycopg2.connect", return_value=mock_conn):
            from func.sync_to_minebase import test_db_connection
            ok, msg = test_db_connection("localhost", 5432, "minebase", "postgres", "pass")
        assert ok is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    @pytest.mark.skipif(not _has_psycopg2, reason="psycopg2 not installed (optional 'db' extra)")
    def test_db_connection_failure(self):
        import psycopg2
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("refused")):
            from func.sync_to_minebase import test_db_connection
            ok, msg = test_db_connection("localhost", 5432, "minebase", "postgres", "pass")
        assert ok is False
        assert "refused" in msg


# ---------------------------------------------------------------------------
# process_worktime RPC — header_mode / header_fuzzy
# ---------------------------------------------------------------------------


class TestProcessWorktimeRPC:
    """process_worktime handler 测试。"""

    def test_header_mode_fuzzy_injected(self, tmp_path):
        """header_mode 和 header_fuzzy 应注入到 mapping 中。"""
        captured_mapping = {}

        def fake_process(path, year, month, output_file=None, return_sheets=False, header_mapping=None, **_kwargs):
            captured_mapping.update(header_mapping or {})
            return {}

        mock_mapping = {"mode": "position", "entries": []}
        with patch("func.excel_worktime.process_excel_data", side_effect=fake_process), \
             patch("func.config_loader.get_worktime_header_mapping", return_value=mock_mapping):
            input_file = str(tmp_path / "test.xlsx")
            pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)
            tauri_bridge._process_worktime({
                "path": input_file, "year": 2025, "month": 1,
                "use_header_mapping": True,
                "header_mode": "name",
                "header_fuzzy": True,
            })
        assert captured_mapping.get("mode") == "name"
        assert captured_mapping.get("fuzzy") is True


# ---------------------------------------------------------------------------
# batch_process RPC — table merge validation
# ---------------------------------------------------------------------------


class TestBatchProcessValidation:
    """batch_process 表合并基础表校验。"""

    def test_table_merge_missing_base_type_returns_error(self):
        """基础表类型缺失时应返回错误。"""
        result = tauri_bridge._batch_process({
            "folder_path": "/tmp/nonexistent",
            "matched": {"production": ["a.xlsx"]},
            "table_merge_config": {"base_type": "fuel"},
        })
        assert "error" in result
        assert "fuel" in result["error"]

    def test_table_merge_with_required_data_passes(self):
        """基础表存在时不应返回校验错误。"""
        with patch("func.excel_batch.process_files", return_value={"fuel": {"success": 1}}):
            result = tauri_bridge._batch_process({
                "folder_path": "/tmp",
                "matched": {"fuel": ["a.xlsx"], "production": ["b.xlsx"]},
                "table_merge_config": {"base_type": "fuel"},
            })
        assert "error" not in result


# ---------------------------------------------------------------------------
# process_production RPC — single file must write output
# ---------------------------------------------------------------------------


class TestProcessProductionRPC:
    """process_production handler 测试。"""

    def test_single_file_returns_output_file(self, tmp_path):
        """单文件处理必须生成输出文件并返回路径。"""
        input_file = str(tmp_path / "2025.01.01 白班.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)

        expected_output = str(tmp_path / "合并产量.xlsx")
        with patch("func.excel_production_enhanced.MiningDataProcessor.process_single_file") as mock_proc, \
             patch("func.excel_production_enhanced.MiningDataProcessor.__init__", return_value=None), \
             patch.object(tauri_bridge, "_post_process_ledger") as mock_post:
            result = tauri_bridge._process_production({
                "path": input_file,
                "use_equipment_ledger": True,
                "use_oil_ledger": False,
            })
        assert result["output_file"] == expected_output
        mock_proc.assert_called_once_with(input_file, expected_output)
        mock_post.assert_called_once_with(
            expected_output,
            use_equipment_ledger=True,
            use_oil_ledger=False,
        )

    def test_folder_returns_output_file(self, tmp_path):
        """文件夹处理必须返回输出文件路径。"""
        with patch("func.excel_production_enhanced.MiningDataProcessor.process_folder") as mock_proc, \
             patch("func.excel_production_enhanced.MiningDataProcessor.__init__", return_value=None), \
             patch.object(tauri_bridge, "_post_process_ledger") as mock_post:
            result = tauri_bridge._process_production({
                "path": str(tmp_path),
                "use_equipment_ledger": False,
                "use_oil_ledger": True,
            })
        expected_output = str(tmp_path / "合并产量.xlsx")
        assert result["output_file"] == expected_output
        mock_proc.assert_called_once()
        mock_post.assert_called_once_with(
            expected_output,
            use_equipment_ledger=False,
            use_oil_ledger=True,
        )


# ---------------------------------------------------------------------------
# apply_device_load_map / get_default_load_map RPC
# ---------------------------------------------------------------------------


class TestLoadMapRPC:
    """设备装载量 RPC 测试。"""

    def test_apply_device_load_map(self):
        result = tauri_bridge._apply_device_load_map({"map_data": {"NTE240": 85}})
        assert result["ok"] is True

    def test_get_default_load_map_new(self):
        result = tauri_bridge._get_default_load_map({"version": "new"})
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_default_load_map_old(self):
        result = tauri_bridge._get_default_load_map({"version": "old"})
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_default_load_map_default(self):
        result = tauri_bridge._get_default_load_map({})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# ledger_match_preview — result_suffix / id_column
# ---------------------------------------------------------------------------


class TestLedgerMatchPreview:
    """ledger_match_preview handler 测试。"""

    def _make_rows(self):
        return [
            {"设备名称": "NTE240-001", "设备编号": "001"},
            {"设备名称": "TR100-002", "设备编号": "002"},
        ]

    def test_suffix_namespaces_keys(self):
        """result_suffix 应将匹配结果写入带后缀的列名。"""
        mock_ledger_data = [
            {"设备名称": "NTE240-001", "标准设备名称": "NTE240", "标准设备编号": "001", "标准公司名称": "A"},
        ]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_ledger_data), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            result = tauri_bridge._ledger_match_preview({
                "rows": self._make_rows(),
                "name_column": "设备名称",
                "mode": "name",
                "result_suffix": "矿卡",
            })
        rows = result["rows"]
        assert "标准设备名称_矿卡" in rows[0]
        assert "标准设备名称" not in rows[0]
        assert rows[0]["__matched_矿卡"] is True

    def test_id_column_matching(self):
        """id_column 参数应启用 ID 匹配。"""
        mock_ledger_data = [
            {"设备编号": "001", "标准设备名称": "NTE240", "标准设备编号": "001", "标准公司名称": "A"},
        ]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_ledger_data), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            result = tauri_bridge._ledger_match_preview({
                "rows": self._make_rows(),
                "id_column": "设备编号",
                "mode": "name",
            })
        assert result["matched"] >= 1
        assert result["rows"][0]["标准设备名称"] == "NTE240"

    def test_no_suffix_no_namespace(self):
        """无 suffix 时写入原始列名。"""
        mock_ledger_data = [
            {"设备名称": "NTE240-001", "标准设备名称": "NTE240", "标准设备编号": "001", "标准公司名称": "A"},
        ]
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=True), \
             patch("func.config_loader.load_equipment_ledger_cache", return_value=mock_ledger_data), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            result = tauri_bridge._ledger_match_preview({
                "rows": self._make_rows(),
                "name_column": "设备名称",
                "mode": "name",
            })
        assert "标准设备名称" in result["rows"][0]
        assert "标准设备名称_矿卡" not in result["rows"][0]
