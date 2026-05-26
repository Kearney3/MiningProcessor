"""gui/logic.py 辅助函数测试"""
import logging
import os
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gui.logic import _find_col, _get_output_file, _log_message, _apply_ledger_matching


# ---------------------------------------------------------------------------
# _find_col
# ---------------------------------------------------------------------------
class TestFindCol:
    def test_finds_first_match(self):
        cols = {"日期", "设备名称", "值"}
        assert _find_col(cols, ["设备名称", "矿卡名称"]) == "设备名称"

    def test_returns_first_from_candidates(self):
        cols = {"矿卡名称", "设备名称"}
        result = _find_col(cols, ["设备名称", "矿卡名称"])
        assert result == "设备名称"

    def test_returns_none_when_no_match(self):
        cols = {"日期", "值"}
        assert _find_col(cols, ["设备名称", "矿卡名称"]) is None

    def test_empty_columns(self):
        assert _find_col(set(), ["设备名称"]) is None

    def test_empty_candidates(self):
        assert _find_col({"设备名称"}, []) is None


# ---------------------------------------------------------------------------
# _get_output_file
# ---------------------------------------------------------------------------
class TestGetOutputFile:
    def test_fuel_type(self, tmp_path):
        input_file = str(tmp_path / "input.xlsx")
        result = _get_output_file("fuel", input_file)
        assert result.endswith("Fuel.xlsx")
        assert os.path.dirname(result) == str(tmp_path)

    def test_production_with_file(self, tmp_path):
        input_file = str(tmp_path / "data.xlsx")
        result = _get_output_file("production", input_file)
        assert "合并产量.xlsx" in result
        assert os.path.dirname(result) == str(tmp_path)

    def test_production_with_dir(self, tmp_path):
        result = _get_output_file("production", str(tmp_path))
        assert result == os.path.join(str(tmp_path), "合并产量.xlsx")

    def test_electrical_type(self, tmp_path):
        input_file = str(tmp_path / "elec.xlsx")
        result = _get_output_file("electrical", input_file)
        assert "电力消耗统计.xlsx" in result

    def test_worktime_with_defaults(self, tmp_path):
        input_file = str(tmp_path / "work.xlsx")
        result = _get_output_file("worktime", input_file)
        assert "202501_工作效率表.xlsx" in result

    def test_worktime_with_custom_year_month(self, tmp_path):
        input_file = str(tmp_path / "work.xlsx")
        result = _get_output_file("worktime", input_file, year=2024, month=12)
        assert "202412_工作效率表.xlsx" in result

    def test_merge_type(self, tmp_path):
        result = _get_output_file("merge", str(tmp_path), keyword="产量")
        assert result == os.path.join(str(tmp_path), "产量_合并.xlsx")

    def test_unknown_type_returns_none(self, tmp_path):
        result = _get_output_file("unknown", str(tmp_path))
        assert result is None


# ---------------------------------------------------------------------------
# _log_message
# ---------------------------------------------------------------------------
class TestLogMessage:
    def test_calls_with_level(self):
        calls = []
        def mock_log(msg, level=None):
            calls.append((msg, level))

        _log_message(mock_log, "test msg", level=logging.WARNING)
        assert calls == [("test msg", logging.WARNING)]

    def test_fallback_for_old_callback(self):
        """只接受 message 的旧回调"""
        calls = []
        def old_log(msg):
            calls.append(msg)

        _log_message(old_log, "test msg", level=logging.ERROR)
        assert calls == ["test msg"]

    def test_default_level_is_info(self):
        calls = []
        def mock_log(msg, level=None):
            calls.append((msg, level))

        _log_message(mock_log, "info msg")
        assert calls == [("info msg", logging.INFO)]


# ---------------------------------------------------------------------------
# _apply_ledger_matching
# ---------------------------------------------------------------------------
class TestApplyLedgerMatching:
    def test_no_ledger_does_nothing(self, tmp_path):
        """两个 ledger 都为 None 时不做任何处理"""
        df = pd.DataFrame({"设备名称": ["A"], "值": [1]})
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        _apply_ledger_matching(out, equipment_ledger=None, oil_ledger=None)

        result = pd.read_excel(out)
        assert "标准设备名称" not in result.columns

    def test_equipment_matching_adds_columns(self, tmp_path):
        """设备台账匹配后应追加标准名称列"""
        df = pd.DataFrame({"设备名称": ["TR100 #1"], "值": [100]})
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                return {
                    "标准设备名称": "TR100 HT#1",
                    "标准设备编号": "HT#1",
                    "标准公司名称": "A公司",
                }

        _apply_ledger_matching(out, equipment_ledger=StubLedger())

        result = pd.read_excel(out)
        assert "标准设备名称" in result.columns
        assert result["标准设备名称"].iloc[0] == "TR100 HT#1"
        assert result["标准设备编号"].iloc[0] == "HT#1"

    def test_oil_matching_adds_column(self, tmp_path):
        """油品台账匹配后应追加标准油品名称列"""
        df = pd.DataFrame({"油品种类": ["0# 柴油"], "值": [50]})
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class StubOilLedger:
            def match(self, name):
                return {"标准名称": "0号柴油", "原始名称": name, "匹配方式": "精确", "相似度": 100}

        _apply_ledger_matching(out, oil_ledger=StubOilLedger())

        result = pd.read_excel(out)
        assert "标准油品名称" in result.columns
        assert result["标准油品名称"].iloc[0] == "0号柴油"

    def test_no_matching_column_skips(self, tmp_path):
        """没有匹配列时不做修改"""
        df = pd.DataFrame({"日期": ["2025-01-01"], "值": [1]})
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                return {"标准设备名称": "X", "标准设备编号": "Y", "标准公司名称": "Z"}

        _apply_ledger_matching(out, equipment_ledger=StubLedger())

        result = pd.read_excel(out)
        assert "标准设备名称" not in result.columns

    def test_unreadable_file_graceful(self, tmp_path):
        """无法读取输出文件时不崩溃"""
        _apply_ledger_matching(str(tmp_path / "nonexistent.xlsx"), equipment_ledger=object())

    def test_equipment_no_match_fills_empty(self, tmp_path):
        """设备匹配失败时写入空值（Excel 读回后为 NaN）"""
        df = pd.DataFrame({"设备名称": ["UNKNOWN"], "值": [1]})
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class NoMatchLedger:
            def match_device(self, name=None, device_id=None):
                return None

        _apply_ledger_matching(out, equipment_ledger=NoMatchLedger())

        result = pd.read_excel(out)
        assert "标准设备名称" in result.columns
        # 空字符串经过 Excel 写读后变成 NaN
        assert pd.isna(result["标准设备名称"].iloc[0])
