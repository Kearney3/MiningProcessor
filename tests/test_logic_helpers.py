"""gui/logic.py 辅助函数测试"""
import logging
import os
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.ledger_postprocess import _find_col, match_sheets
from gui.logic import _get_output_file, _log_message, _apply_ledger_matching


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

    def test_strip_whitespace_match(self):
        """列名有前后空格时，strip 后应能匹配"""
        cols = {" 油品种类 ", "设备名称"}
        assert _find_col(cols, ["油品种类", "油品名称"]) == " 油品种类 "

    def test_strip_whitespace_candidate_priority(self):
        """多个候选列名都能 strip 匹配时，按候选顺序返回第一个"""
        cols = {" 油品名称 ", " 油品种类 "}
        assert _find_col(cols, ["油品种类", "油品名称"]) == " 油品种类 "

    def test_exact_match_takes_priority(self):
        """精确匹配优先于 strip 匹配"""
        cols = {"油品种类", " 油品种类 "}
        assert _find_col(cols, ["油品种类"]) == "油品种类"


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
        from datetime import datetime
        input_file = str(tmp_path / "work.xlsx")
        result = _get_output_file("worktime", input_file)
        current_year = datetime.now().year
        assert f"{current_year}01_工作效率表.xlsx" in result

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


class TestApplyLedgerMatchingProductionData:
    """测试生产数据场景：同时包含矿卡名称和挖机名称时，列名添加后缀"""

    def test_production_data_adds_suffixes(self, tmp_path):
        """生产数据（同时有矿卡名称和挖机名称）应添加（矿卡）和（挖机）后缀"""
        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-01"],
            "矿卡名称": ["TR100 #1", "TR100 #2"],
            "挖机名称": ["EX2000 #1", "EX2000 #2"],
            "数量": [10, 20],
        })
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                if name and "TR100" in name:
                    return {
                        "标准设备名称": f"STD_{name}",
                        "标准设备编号": "HT#1",
                        "标准公司名称": "A公司",
                    }
                elif name and "EX2000" in name:
                    return {
                        "标准设备名称": f"STD_{name}",
                        "标准设备编号": "EX#1",
                        "标准公司名称": "B公司",
                    }
                return None

        _apply_ledger_matching(out, equipment_ledger=StubLedger())

        result = pd.read_excel(out)
        # 验证添加了带后缀的列
        assert "标准设备名称（矿卡）" in result.columns
        assert "标准设备编号（矿卡）" in result.columns
        assert "标准公司名称（矿卡）" in result.columns
        assert "标准设备名称（挖机）" in result.columns
        assert "标准设备编号（挖机）" in result.columns
        assert "标准公司名称（挖机）" in result.columns
        # 验证不添加无后缀的列
        assert "标准设备名称" not in result.columns
        # 验证数据正确
        assert result["标准设备名称（矿卡）"].iloc[0] == "STD_TR100 #1"
        assert result["标准设备名称（挖机）"].iloc[0] == "STD_EX2000 #1"

    def test_non_production_data_no_suffix(self, tmp_path):
        """非生产数据（只有设备名称）不应添加后缀"""
        df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "设备名称": ["TR100 #1"],
            "值": [100],
        })
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                return {
                    "标准设备名称": "STD_TR100",
                    "标准设备编号": "HT#1",
                    "标准公司名称": "A公司",
                }

        _apply_ledger_matching(out, equipment_ledger=StubLedger())

        result = pd.read_excel(out)
        # 验证不添加带后缀的列
        assert "标准设备名称（矿卡）" not in result.columns
        assert "标准设备名称（挖机）" not in result.columns
        # 验证添加无后缀的列
        assert "标准设备名称" in result.columns
        assert result["标准设备名称"].iloc[0] == "STD_TR100"

    def test_production_data_partial_match(self, tmp_path):
        """生产数据中部分匹配失败时，对应列为空"""
        df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "矿卡名称": ["UNKNOWN_TRUCK"],
            "挖机名称": ["EX2000 #1"],
            "数量": [10],
        })
        out = str(tmp_path / "test.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                if name and "EX2000" in name:
                    return {
                        "标准设备名称": "STD_EX2000",
                        "标准设备编号": "EX#1",
                        "标准公司名称": "B公司",
                    }
                return None

        _apply_ledger_matching(out, equipment_ledger=StubLedger())

        result = pd.read_excel(out)
        # 矿卡匹配失败
        assert pd.isna(result["标准设备名称（矿卡）"].iloc[0])
        # 挖机匹配成功
        assert result["标准设备名称（挖机）"].iloc[0] == "STD_EX2000"




# ---------------------------------------------------------------------------
# 工时模块 + 台账匹配集成测试（回归测试）
# ---------------------------------------------------------------------------
class TestWorktimeHeaderMapping:
    """验证表头映射索引在日期/班次插入后仍然正确"""

    def test_mapping_indices_before_insert(self, tmp_path):
        """表头映射的 position 索引对应原始列位置（insert 之前）"""
        from func.excel_utils import apply_header_mapping

        # 模拟 insert 之前的 DataFrame（原始 Mongolian 列 + 班次）
        df = pd.DataFrame({
            "Д/дугаар": [1],
            "Техникийн нэр": ["NTE240"],
            "Компани": ["XX公司"],
            "班次": ["Day"],
        })

        mapping = {
            "mode": "position",
            "fuzzy": False,
            "entries": [
                {"index": 1, "original": "", "new": "序号"},
                {"index": 2, "original": "", "new": "设备名称"},
                {"index": 3, "original": "", "new": "公司"},
            ],
        }

        result = apply_header_mapping(df, mapping)
        assert list(result.columns) == ["序号", "设备名称", "公司", "班次"]


class TestWorktimeLedgerMatching:
    """验证工时数据（Mongolian 列名）经过表头映射后能正确触发台账匹配"""

    def test_preloaded_sheets_with_mapped_columns(self, tmp_path):
        """表头映射后工时数据的设备名称列应被台账匹配识别"""
        df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "班次": ["Day"],
            "设备名称": ["NTE240 #1101"],
            "公司": ["XX公司"],
        })
        out = str(tmp_path / "worktime.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                if name and "NTE240" in name:
                    return {
                        "标准设备名称": "NTE240 HT#1101",
                        "标准设备编号": "HT#1101",
                        "标准公司名称": "A公司",
                    }
                return None

        preloaded = {"工时数据": df.copy()}
        _apply_ledger_matching(out, equipment_ledger=StubLedger(), preloaded_sheets=preloaded)

        result = pd.read_excel(out)
        assert "标准设备名称" in result.columns
        assert result["标准设备名称"].iloc[0] == "NTE240 HT#1101"
        assert result["标准设备编号"].iloc[0] == "HT#1101"

    def test_preloaded_sheets_with_raw_mongolian_columns(self, tmp_path):
        """未映射的工时数据（Mongolian 列名）也应通过 preloaded_sheets 匹配"""
        # 模拟未映射的原始 Mongolian 列名
        df = pd.DataFrame({
            "日期": ["2025-01-01"],
            "班次": ["Day"],
            "Техникийн нэр": ["NTE240 #1101"],
        })
        out = str(tmp_path / "worktime_raw.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                if name and "NTE240" in name:
                    return {
                        "标准设备名称": "NTE240 HT#1101",
                        "标准设备编号": "HT#1101",
                        "标准公司名称": "A公司",
                    }
                return None

        # preloaded_sheets 包含已处理的 DataFrame
        preloaded = {"工时数据": df.copy()}
        _apply_ledger_matching(out, equipment_ledger=StubLedger(), preloaded_sheets=preloaded)

        result = pd.read_excel(out)
        # Mongolian 列名不在 _find_col 的候选列表中，但 preloaded 避免了重新读取
        # 此时因为列名是 Mongolian，匹配不会触发（_find_col 找不到设备名称）
        # 这正是为什么需要 Fix 1（表头映射）的原因
        assert "标准设备名称" not in result.columns

    def test_no_preloaded_sheets_reads_from_file(self, tmp_path):
        """不传 preloaded_sheets 时应从文件读取（原有行为不变）"""
        df = pd.DataFrame({"设备名称": ["TR100 #1"], "值": [100]})
        out = str(tmp_path / "normal.xlsx")
        df.to_excel(out, index=False)

        class StubLedger:
            def match_device(self, name=None, device_id=None):
                return {
                    "标准设备名称": "STD_TR100",
                    "标准设备编号": "HT#1",
                    "标准公司名称": "A公司",
                }

        _apply_ledger_matching(out, equipment_ledger=StubLedger(), preloaded_sheets=None)

        result = pd.read_excel(out)
        assert "标准设备名称" in result.columns
        assert result["标准设备名称"].iloc[0] == "STD_TR100"


# ---------------------------------------------------------------------------
# match_sheets (ledger_postprocess)
# ---------------------------------------------------------------------------
class TestMatchSheets:
    """Tests for the in-memory match_sheets function."""

    class _StubEquipmentLedger:
        def match_device(self, name=None, device_id=None):
            return {
                "标准设备名称": f"STD_{name}",
                "标准设备编号": f"ID_{device_id or 'N/A'}",
                "标准公司名称": "测试公司",
            }

    class _StubOilLedger:
        def match(self, name):
            return {"标准名称": f"STD_{name}", "原始名称": name, "匹配方式": "精确", "相似度": 100}

    def test_returns_sheets_unchanged_when_no_ledgers(self):
        sheets = {"Sheet1": pd.DataFrame({"A": [1]})}
        result = match_sheets(sheets)
        assert result is sheets
        assert "标准设备名称" not in result["Sheet1"].columns

    def test_single_equipment_column(self):
        df = pd.DataFrame({"设备名称": ["TR100"], "值": [100]})
        sheets = {"数据": df}
        result = match_sheets(sheets, equipment_ledger=self._StubEquipmentLedger())
        assert "标准设备名称" in result["数据"].columns
        assert result["数据"]["标准设备名称"].iloc[0] == "STD_TR100"

    def test_production_dual_column(self):
        df = pd.DataFrame({"矿卡名称": ["TR100"], "挖机名称": ["EX200"], "产量": [50]})
        sheets = {"生产": df}
        result = match_sheets(sheets, equipment_ledger=self._StubEquipmentLedger())
        assert "标准设备名称（矿卡）" in result["生产"].columns
        assert "标准设备名称（挖机）" in result["生产"].columns
        assert result["生产"]["标准设备名称（矿卡）"].iloc[0] == "STD_TR100"
        assert result["生产"]["标准设备名称（挖机）"].iloc[0] == "STD_EX200"

    def test_oil_matching(self):
        df = pd.DataFrame({"油品种类": ["0# 柴油"], "值": [50]})
        sheets = {"油耗": df}
        result = match_sheets(sheets, oil_ledger=self._StubOilLedger())
        assert "标准油品名称" in result["油耗"].columns
        assert result["油耗"]["标准油品名称"].iloc[0] == "STD_0# 柴油"

    def test_equipment_and_oil_combined(self):
        df = pd.DataFrame({"设备名称": ["TR100"], "油品种类": ["0# 柴油"], "值": [50]})
        sheets = {"数据": df}
        result = match_sheets(
            sheets,
            equipment_ledger=self._StubEquipmentLedger(),
            oil_ledger=self._StubOilLedger(),
        )
        assert "标准设备名称" in result["数据"].columns
        assert "标准油品名称" in result["数据"].columns

    def test_multiple_sheets(self):
        df1 = pd.DataFrame({"设备名称": ["TR100"], "值": [1]})
        df2 = pd.DataFrame({"设备名称": ["EX200"], "值": [2]})
        sheets = {"S1": df1, "S2": df2}
        result = match_sheets(sheets, equipment_ledger=self._StubEquipmentLedger())
        assert "标准设备名称" in result["S1"].columns
        assert "标准设备名称" in result["S2"].columns

    def test_no_matching_columns_skips_sheet(self):
        df = pd.DataFrame({"无关列": [1, 2], "值": [3, 4]})
        sheets = {"数据": df}
        result = match_sheets(sheets, equipment_ledger=self._StubEquipmentLedger())
        assert "标准设备名称" not in result["数据"].columns

    def test_with_id_column(self):
        df = pd.DataFrame({"设备名称": ["TR100"], "设备编号": ["HT#1"], "值": [1]})
        sheets = {"数据": df}
        result = match_sheets(sheets, equipment_ledger=self._StubEquipmentLedger())
        assert result["数据"]["标准设备编号"].iloc[0] == "ID_HT#1"
