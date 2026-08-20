"""ledger_enrichment 模块测试：resolve_equipment_attributes 与 enrich_dataframe_device。"""

from unittest.mock import MagicMock

import pandas as pd

from func.ledger_enrichment import enrich_dataframe_device, resolve_equipment_attributes

# ---------------------------------------------------------------------------
# helpers: mock ledger factories
# ---------------------------------------------------------------------------

def _make_equipment_ledger(matches: dict | None):
    """返回一个 mock EquipmentLedger，match_device 按 name/device_id 返回 matches 或 None。"""
    ledger = MagicMock()
    ledger.match_device.return_value = matches
    return ledger


def _make_model_ledger(matches: dict | None):
    """返回一个 mock ModelLedger，match_by_standard_id 返回 matches 或 None。"""
    ledger = MagicMock()
    ledger.match_by_standard_id.return_value = matches
    return ledger


DEFAULT_RESULT = {
    "标准设备名称": "",
    "标准设备编号": "",
    "标准公司名称": "",
    "所有权": "",
    "设备型号": "",
    "设备类型": "",
    "内部分类": "",
}


# ===========================================================================
# resolve_equipment_attributes
# ===========================================================================


class TestResolveNoLedgers:
    """无 ledger 时直接返回默认空值。"""

    def test_returns_defaults_when_no_ledgers(self):
        # Arrange & Act
        result = resolve_equipment_attributes(name="挖掘机A", device_id="D001")

        # Assert
        assert result == DEFAULT_RESULT

    def test_returns_defaults_when_both_none(self):
        # Arrange & Act
        result = resolve_equipment_attributes(
            name="X", device_id="Y", equipment_ledger=None, model_ledger=None
        )

        # Assert
        assert result == DEFAULT_RESULT

    def test_defaults_when_name_and_id_none(self):
        # Arrange & Act
        result = resolve_equipment_attributes(name=None, device_id=None)

        # Assert
        assert result == DEFAULT_RESULT


class TestResolveEquipmentOnly:
    """只有设备台账时，只填写标准设备名称/编号/公司名称。"""

    def test_equipment_match_populates_basic_fields(self):
        # Arrange
        eq_match = {
            "标准设备名称": "标准卡车",
            "标准设备编号": "S001",
            "标准公司名称": "公司甲",
        }
        eq_ledger = _make_equipment_ledger(eq_match)

        # Act
        result = resolve_equipment_attributes(
            name="卡车A", device_id="001", equipment_ledger=eq_ledger
        )

        # Assert
        assert result["标准设备名称"] == "标准卡车"
        assert result["标准设备编号"] == "S001"
        assert result["标准公司名称"] == "公司甲"
        assert result["设备型号"] == ""  # model fields stay empty

    def test_equipment_no_match_returns_defaults(self):
        # Arrange
        eq_ledger = _make_equipment_ledger(None)

        # Act
        result = resolve_equipment_attributes(
            name="未知设备", equipment_ledger=eq_ledger
        )

        # Assert
        assert result == DEFAULT_RESULT


class TestResolveModelOnly:
    """只有型号台账且无设备台账时，标准设备编号为空，型号字段不会被填充。"""

    def test_model_ledger_alone_does_nothing(self):
        # Arrange
        model_match = {
            "标准公司名称": "模型公司",
            "所有权": "自有",
            "设备型号": "CAT320",
            "设备类型": "挖掘机",
            "内部分类": "大型",
        }
        model_ledger = _make_model_ledger(model_match)

        # Act
        result = resolve_equipment_attributes(
            name="挖掘机A", device_id="D001", model_ledger=model_ledger
        )

        # Assert — 标准设备编号为空，所以 model_ledger 不会被调用
        model_ledger.match_by_standard_id.assert_not_called()
        assert result == DEFAULT_RESULT


class TestResolveBothLedgers:
    """设备台账与型号台账同时存在时的完整链路。"""

    def test_full_chain_populates_all_fields(self):
        # Arrange
        eq_match = {
            "标准设备名称": "标准挖掘机",
            "标准设备编号": "EQ-200",
            "标准公司名称": "设备公司",
        }
        model_match = {
            "标准公司名称": "型号公司",  # overrides equipment value
            "所有权": "租赁",
            "设备型号": "CAT330",
            "设备类型": "挖掘机",
            "内部分类": "中型",
        }
        eq_ledger = _make_equipment_ledger(eq_match)
        model_ledger = _make_model_ledger(model_match)

        # Act
        result = resolve_equipment_attributes(
            name="挖掘机B", device_id="EQ-200",
            equipment_ledger=eq_ledger, model_ledger=model_ledger,
        )

        # Assert
        assert result["标准设备名称"] == "标准挖掘机"
        assert result["标准设备编号"] == "EQ-200"
        # model ledger overrides company name
        assert result["标准公司名称"] == "型号公司"
        assert result["所有权"] == "租赁"
        assert result["设备型号"] == "CAT330"
        assert result["设备类型"] == "挖掘机"
        assert result["内部分类"] == "中型"

    def test_model_no_match_keeps_equipment_company(self):
        # Arrange
        eq_match = {
            "标准设备名称": "卡车",
            "标准设备编号": "EQ-100",
            "标准公司名称": "设备公司",
        }
        eq_ledger = _make_equipment_ledger(eq_match)
        model_ledger = _make_model_ledger(None)  # model 未命中

        # Act
        result = resolve_equipment_attributes(
            name="卡车A", device_id="EQ-100",
            equipment_ledger=eq_ledger, model_ledger=model_ledger,
        )

        # Assert — 设备公司名称保留，扩展字段为空
        assert result["标准公司名称"] == "设备公司"
        assert result["所有权"] == ""
        assert result["设备型号"] == ""

    def test_model_match_without_company_keeps_equipment_company(self):
        # Arrange — model match has no 标准公司名称
        eq_match = {
            "标准设备名称": "卡车",
            "标准设备编号": "EQ-100",
            "标准公司名称": "设备公司",
        }
        model_match = {
            "标准公司名称": "",
            "所有权": "自有",
            "设备型号": "M100",
            "设备类型": "卡车",
            "内部分类": "小型",
        }
        eq_ledger = _make_equipment_ledger(eq_match)
        model_ledger = _make_model_ledger(model_match)

        # Act
        result = resolve_equipment_attributes(
            name="卡车A", device_id="EQ-100",
            equipment_ledger=eq_ledger, model_ledger=model_ledger,
        )

        # Assert — 空字符串不覆盖原公司名称
        assert result["标准公司名称"] == "设备公司"
        assert result["所有权"] == "自有"


class TestResolveEdgeCases:
    """边界场景：空白字符串、NaN、特殊字符。"""

    def test_whitespace_name_gets_cleaned(self):
        # Arrange
        eq_ledger = _make_equipment_ledger({
            "标准设备名称": "X",
            "标准设备编号": "S1",
            "标准公司名称": "C",
        })

        # Act
        result = resolve_equipment_attributes(
            name="  \n 挖掘机  \t", device_id="  ",
            equipment_ledger=eq_ledger,
        )

        # Assert — match_device receives cleaned name
        eq_ledger.match_device.assert_called_once_with(name="挖掘机", device_id=None)

    def test_nan_name_cleaned_to_none(self):
        # Arrange
        eq_ledger = _make_equipment_ledger(None)

        # Act
        resolve_equipment_attributes(
            name=pd.NA, device_id=None, equipment_ledger=eq_ledger
        )

        # Assert
        eq_ledger.match_device.assert_called_once_with(name=None, device_id=None)

    def test_none_match_values_cleaned_to_empty(self):
        # Arrange — ledger returns None for some values
        eq_match = {
            "标准设备名称": None,
            "标准设备编号": None,
            "标准公司名称": None,
        }
        eq_ledger = _make_equipment_ledger(eq_match)

        # Act
        result = resolve_equipment_attributes(name="X", equipment_ledger=eq_ledger)

        # Assert
        assert result["标准设备名称"] == ""
        assert result["标准设备编号"] == ""


# ===========================================================================
# enrich_dataframe_device
# ===========================================================================


class TestEnrichDataframeDevice:

    def _make_df(self, names, ids=None):
        """创建简单测试 DataFrame。"""
        data = {"设备": names}
        if ids is not None:
            data["编号"] = ids
        return pd.DataFrame(data)

    def test_no_ledgers_adds_empty_columns(self):
        # Arrange
        df = self._make_df(["卡车A", "卡车B"])

        # Act
        result = enrich_dataframe_device(df, name_col="设备")

        # Assert — 原始列 + 7 个标准字段列
        assert len(result) == 2
        for col in ("标准设备名称", "标准设备编号", "标准公司名称",
                     "标准公司名称", "所有权", "设备型号", "设备类型", "内部分类"):
            assert col in result.columns
        assert all(result["标准设备名称"] == "")

    def test_suffix_appended_to_added_columns(self):
        # Arrange
        df = self._make_df(["卡车A"])

        # Act
        result = enrich_dataframe_device(df, name_col="设备", suffix="_台账")

        # Assert
        assert "标准设备名称_台账" in result.columns
        assert "所有权_台账" in result.columns
        assert "设备型号_台账" in result.columns
        assert "标准设备名称" not in result.columns

    def test_equipment_only_populates_basic_fields(self):
        # Arrange
        df = self._make_df(["卡车A", "挖掘机B"])
        eq_ledger = _make_equipment_ledger({
            "标准设备名称": "标准卡车",
            "标准设备编号": "S001",
            "标准公司名称": "公司甲",
        })

        # Act
        result = enrich_dataframe_device(df, name_col="设备", equipment_ledger=eq_ledger)

        # Assert
        assert list(result["标准设备名称"]) == ["标准卡车", "标准卡车"]
        assert list(result["设备型号"]) == ["", ""]

    def test_both_ledgers_full_enrichment(self):
        # Arrange
        df = self._make_df(["卡车A"])
        eq_match = {
            "标准设备名称": "标准卡车",
            "标准设备编号": "S001",
            "标准公司名称": "公司甲",
        }
        model_match = {
            "标准公司名称": "型号公司",
            "所有权": "自有",
            "设备型号": "Volvo",
            "设备类型": "卡车",
            "内部分类": "大型",
        }
        eq_ledger = _make_equipment_ledger(eq_match)
        model_ledger = _make_model_ledger(model_match)

        # Act
        result = enrich_dataframe_device(
            df, name_col="设备",
            equipment_ledger=eq_ledger, model_ledger=model_ledger,
        )

        # Assert
        assert result.iloc[0]["标准设备名称"] == "标准卡车"
        assert result.iloc[0]["所有权"] == "自有"
        assert result.iloc[0]["设备型号"] == "Volvo"

    def test_id_column_passed_when_provided(self):
        # Arrange
        df = self._make_df(["卡车A"], ids=["D001"])
        eq_ledger = _make_equipment_ledger(None)

        # Act
        enrich_dataframe_device(
            df, name_col="设备", id_col="编号", equipment_ledger=eq_ledger
        )

        # Assert — match_device receives device_id from the id_col
        eq_ledger.match_device.assert_called_with(name="卡车A", device_id="D001")

    def test_id_column_ignored_when_none(self):
        # Arrange
        df = self._make_df(["卡车A"])
        eq_ledger = _make_equipment_ledger(None)

        # Act
        enrich_dataframe_device(df, name_col="设备", equipment_ledger=eq_ledger)

        # Assert
        eq_ledger.match_device.assert_called_with(name="卡车A", device_id=None)

    def test_empty_dataframe_returns_empty_with_columns(self):
        # Arrange
        df = pd.DataFrame({"设备": pd.Series([], dtype=str)})

        # Act
        result = enrich_dataframe_device(df, name_col="设备")

        # Assert
        assert len(result) == 0
        assert "标准设备名称" in result.columns
        assert "内部分类" in result.columns

    def test_original_dataframe_not_mutated(self):
        # Arrange
        df = self._make_df(["卡车A"])
        original_cols = list(df.columns)

        # Act
        enrich_dataframe_device(df, name_col="设备")

        # Assert
        assert list(df.columns) == original_cols
