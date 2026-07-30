"""tauri_bridge RPC 方法测试"""
import importlib.util
import io
import json
import logging
import pathlib
import sys
from datetime import date
from unittest.mock import MagicMock, patch

from func.orchestration import postprocess_from_cache

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tauri_bridge

_has_psycopg2 = importlib.util.find_spec("psycopg2") is not None


class TestStructuredStderrLogging:
    def test_exception_event_keeps_short_message_and_full_detail(self):
        stream = io.StringIO()
        handler = tauri_bridge._StderrLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger = logging.getLogger("test.tauri.structured")
        test_logger.handlers = [handler]
        test_logger.propagate = False
        test_logger.setLevel(logging.DEBUG)

        with patch.object(tauri_bridge.sys, "stderr", stream):
            try:
                raise ValueError("diagnostic detail")
            except ValueError:
                test_logger.exception("processing failed")

        event = json.loads(stream.getvalue())
        data = event["data"]
        assert event["event"] == "log"
        assert data["message"] == "processing failed"
        assert "Traceback" in data["detail"]
        assert "ValueError: diagnostic detail" in data["detail"]
        assert data["logger"] == "test.tauri.structured"
        assert data["seq"] == 1
        assert data["timestamp"]

    def test_sequence_increments_for_each_record(self):
        stream = io.StringIO()
        handler = tauri_bridge._StderrLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger = logging.getLogger("test.tauri.sequence")
        test_logger.handlers = [handler]
        test_logger.propagate = False
        test_logger.setLevel(logging.INFO)

        with patch.object(tauri_bridge.sys, "stderr", stream):
            test_logger.info("first")
            test_logger.warning("second")

        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        assert [event["data"]["seq"] for event in events] == [1, 2]


def test_process_maintenance_llm_rpc_forwards_sheet_and_tuning(tmp_path):
    """Tauri 选择的 Sheet、并发数和批次大小必须传到处理器。"""
    source = tmp_path / "maintenance.xlsx"
    source.touch()
    captured = {}

    def _fake_process(path, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return {"llm_completed": 0}

    config = {
        "url": "https://example.test/v1",
        "api_key": "secret",
        "model": "model-a",
        "format": "openai",
        "concurrency": 4,
        "batch_size": 20,
        "timeout": 30,
        "max_retries": 2,
    }

    with patch(
        "func.label_maintenance_with_llm.process_maintenance_llm",
        side_effect=_fake_process,
    ), patch(
        "func.config_loader.get_llm_config",
        return_value=config,
    ), patch.object(
        tauri_bridge,
        "_CANCEL_FILE",
        tmp_path / "cancel",
    ):
        result = tauri_bridge._process_maintenance_llm({
            "path": str(source),
            "sheet_name": "夜班维修",
            "content_column": "内容",
            "category_column": "大类",
            "minor_column": "小类",
            "status_column": "方式",
            "filter_values": ["待确认"],
            "export_mode": "details",
        })

    assert result["cancelled"] is False
    assert captured["sheet_name"] == "夜班维修"
    assert captured["concurrency"] == 4
    assert captured["batch_size"] == 20


# ---------------------------------------------------------------------------
# postprocess_from_cache (formerly postprocess_from_cache)
# ---------------------------------------------------------------------------


class TestPostProcessLedger:
    """台账匹配后处理测试（委托 func.orchestration.postprocess_from_cache）。"""

    def _write_excel(self, tmp_path, sheets: dict[str, pd.DataFrame]) -> str:
        path = str(tmp_path / "output.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            for name, df in sheets.items():
                df.to_excel(w, sheet_name=name, index=False)
        return path

    def test_skip_when_both_false(self, tmp_path):
        """两个开关都为 False 时不执行任何操作。"""
        path = self._write_excel(tmp_path, {"s": pd.DataFrame({"a": [1]})})
        postprocess_from_cache(path, use_equipment_ledger=False, use_oil_ledger=False)
        df = pd.read_excel(path)
        assert list(df.columns) == ["a"]

    def test_skip_when_no_cache(self, tmp_path):
        """无缓存台账时不修改文件。"""
        path = self._write_excel(tmp_path, {
            "s": pd.DataFrame({"日期": ["2025-01-01"], "设备名称": ["卡车A"]}),
        })
        with patch("func.config_loader.has_equipment_ledger_cache", return_value=False), \
             patch("func.config_loader.has_oil_ledger_cache", return_value=False):
            postprocess_from_cache(path, use_equipment_ledger=True, use_oil_ledger=True)
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
            postprocess_from_cache(path, use_equipment_ledger=True, use_oil_ledger=False)
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
            postprocess_from_cache(path, use_equipment_ledger=True, use_oil_ledger=True)
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
            postprocess_from_cache(path, use_equipment_ledger=True, use_oil_ledger=False)
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
            postprocess_from_cache(path, use_equipment_ledger=True, use_oil_ledger=False)
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
            postprocess_from_cache(path, use_equipment_ledger=False, use_oil_ledger=True)
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
             patch("func.orchestration.postprocess_from_cache") as mock_post:
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
        """台账匹配禁用时不调用 postprocess_from_cache。"""
        input_file = str(tmp_path / "fuel_input.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)

        expected_output = str(tmp_path / "Fuel.xlsx")
        with patch("func.excel_fuel.process_diesel_data", return_value=expected_output), \
             patch("func.orchestration.postprocess_from_cache") as mock_post:
            result = tauri_bridge._process_fuel({
                "path": input_file,
                "use_equipment_ledger": False,
                "use_oil_ledger": False,
            })
        assert result["output_file"] == expected_output
        mock_post.assert_not_called()

    def test_returns_output_path_even_when_processing_fails(self, tmp_path):
        """处理失败时 output_file 仍为计算的路径（process_single 独立计算）。"""
        input_file = str(tmp_path / "bad.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(input_file, index=False)

        with patch("func.excel_fuel.process_diesel_data", return_value=None):
            result = tauri_bridge._process_fuel({"path": input_file})
        # process_single 使用 get_output_path 独立计算输出路径
        assert result["output_file"] == str(tmp_path / "Fuel.xlsx")


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
# process_worktime RPC — header_mode
# ---------------------------------------------------------------------------


class TestProcessWorktimeRPC:
    """process_worktime handler 测试。"""

    def test_header_mode_injected(self, tmp_path):
        """header_mode 应注入到 mapping 中。"""
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
            })
        assert captured_mapping.get("mode") == "name"


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
        with patch("func.excel_batch.process_files", return_value=({"fuel": {"success": 1}}, {})):
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
             patch("func.orchestration.postprocess_from_cache") as mock_post:
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
             patch("func.orchestration.postprocess_from_cache") as mock_post:
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
# process_maintenance RPC
# ---------------------------------------------------------------------------


class TestProcessMaintenanceRPC:
    def test_forwards_ml_fallback_switch(self, tmp_path):
        input_file = tmp_path / "maintenance.xlsx"
        input_file.touch()
        expected_output = str(tmp_path / "维修记录统计.xlsx")

        with patch(
            "func.excel_maintenance.process_maintenance_data",
            return_value=expected_output,
        ) as process:
            result = tauri_bridge._process_maintenance(
                {"path": str(input_file), "use_ml_fallback": False}
            )

        assert result["output_file"] == expected_output
        assert process.call_args.kwargs["use_ml_fallback"] is False

    def test_ml_fallback_defaults_to_enabled(self, tmp_path):
        input_file = tmp_path / "maintenance.xlsx"
        input_file.touch()

        with patch(
            "func.excel_maintenance.process_maintenance_data",
            return_value=str(tmp_path / "output.xlsx"),
        ) as process:
            tauri_bridge._process_maintenance({"path": str(input_file)})

        assert process.call_args.kwargs["use_ml_fallback"] is True


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

    def test_get_load_map_version(self):
        result = tauri_bridge._get_load_map_version({})
        assert "version" in result
        assert result["version"] in ("new", "old")

    def test_set_load_map_version(self):
        result = tauri_bridge._set_load_map_version({"version": "old"})
        assert result["ok"] is True
        # Verify it was persisted
        from func.config_loader import get_load_map_version
        assert get_load_map_version() == "old"
        # Reset to new
        tauri_bridge._set_load_map_version({"version": "new"})


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


# ---------------------------------------------------------------------------
# get_anomaly_config / save_anomaly_config RPC
# ---------------------------------------------------------------------------


class TestAnomalyConfigRPC:
    """get_anomaly_config / save_anomaly_config handler 测试。"""

    def test_get_returns_merged_config(self):
        """应返回包含所有必需字段的合并配置。"""
        result = tauri_bridge._get_anomaly_config({})
        assert isinstance(result, dict)
        assert "use_threshold" in result
        assert "use_sigma" in result
        assert "use_percentile" in result
        assert "sigma_n" in result
        assert "percentile_low" in result
        assert "percentile_high" in result
        assert "thresholds" in result
        assert "handling_rules" in result

    def test_get_default_sigma_n(self):
        """默认 σ 倍数应为 3.0。"""
        result = tauri_bridge._get_anomaly_config({})
        assert result["sigma_n"] == 3.0

    def test_get_default_thresholds_include_fuel(self):
        """默认阈值应包含 fuel 数据类型。"""
        result = tauri_bridge._get_anomaly_config({})
        assert "fuel" in result["thresholds"]

    def test_save_with_updates_merges(self):
        """updates 模式应增量合并，不覆盖其他字段。"""
        original = tauri_bridge._get_anomaly_config({})
        original_sigma = original["sigma_n"]

        try:
            tauri_bridge._save_anomaly_config({"updates": {"sigma_n": 5.0}})
            result = tauri_bridge._get_anomaly_config({})
            assert result["sigma_n"] == 5.0
            # 其他字段应保持不变
            assert result["use_threshold"] == original["use_threshold"]
        finally:
            # 恢复
            tauri_bridge._save_anomaly_config({"updates": {"sigma_n": original_sigma}})

    def test_save_with_config_replaces(self):
        """config 模式应整体替换 anomaly_detection 段。"""
        original = tauri_bridge._get_anomaly_config({})
        try:
            tauri_bridge._save_anomaly_config({"config": {"sigma_n": 10.0}})
            result = tauri_bridge._get_anomaly_config({})
            # sigma_n 被替换为 10.0，但默认值仍通过 DEFAULT_ANOMALY_DETECTION 合并回来
            assert result["sigma_n"] == 10.0
        finally:
            # 恢复：用 updates 恢复 sigma_n
            tauri_bridge._save_anomaly_config({"updates": {"sigma_n": original["sigma_n"]}})

    def test_save_with_empty_config_resets(self):
        """空 config 应清除用户覆盖，回到默认值。"""
        try:
            tauri_bridge._save_anomaly_config({"config": {}})
            result = tauri_bridge._get_anomaly_config({})
            assert result["sigma_n"] == 3.0
            assert result["use_threshold"] is True
        finally:
            pass  # 已恢复默认

    def test_save_updates_returns_ok(self):
        """save_anomaly_config 应返回 ok: True。"""
        result = tauri_bridge._save_anomaly_config({"updates": {"sigma_n": 3.0}})
        assert result == {"ok": True}

    def test_save_no_params_returns_ok(self):
        """无 updates 也无 config 时仍返回 ok（不修改）。"""
        result = tauri_bridge._save_anomaly_config({})
        assert result == {"ok": True}

    def test_save_handling_rules(self):
        """应能保存处理规则。"""
        original = tauri_bridge._get_anomaly_config({})
        try:
            tauri_bridge._save_anomaly_config({
                "updates": {
                    "handling_rules": {
                        "test_type": {
                            "test_col": {"strategy": "default_value", "default": 42},
                        },
                    },
                },
            })
            result = tauri_bridge._get_anomaly_config({})
            assert "test_type" in result["handling_rules"]
            assert result["handling_rules"]["test_type"]["test_col"]["default"] == 42
        finally:
            tauri_bridge._save_anomaly_config({
                "updates": {"handling_rules": original.get("handling_rules", {})},
            })
