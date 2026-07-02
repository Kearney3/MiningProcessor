"""func/orchestration.py 共享编排逻辑测试"""
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.orchestration import (
    build_worktime_header_mapping,
    load_equipment_ledger_from_cache,
    load_ledgers,
    load_oil_ledger_from_cache,
    postprocess_from_cache,
    postprocess_with_ledgers,
)


# ---------------------------------------------------------------------------
# load_equipment_ledger_from_cache
# ---------------------------------------------------------------------------
class TestLoadEquipmentLedgerFromCache:
    @patch("func.config_loader.load_equipment_ledger_cache")
    @patch("func.config_loader.has_equipment_ledger_cache", return_value=True)
    def test_returns_ledger_when_cache_exists(self, mock_has, mock_load):
        mock_load.return_value = [
            {"标准设备名称": "TR100 #1", "标准设备编号": "HT#1", "标准公司名称": "A公司"}
        ]
        ledger = load_equipment_ledger_from_cache()
        assert ledger is not None
        assert len(ledger._df) == 1

    @patch("func.config_loader.has_equipment_ledger_cache", return_value=False)
    def test_returns_none_when_no_cache(self, mock_has):
        assert load_equipment_ledger_from_cache() is None

    @patch("func.config_loader.load_equipment_ledger_cache", return_value=None)
    @patch("func.config_loader.has_equipment_ledger_cache", return_value=True)
    def test_returns_none_when_cache_empty(self, mock_has, mock_load):
        assert load_equipment_ledger_from_cache() is None

    @patch("func.config_loader.has_equipment_ledger_cache", side_effect=Exception("boom"))
    def test_returns_none_on_exception(self, mock_has):
        assert load_equipment_ledger_from_cache() is None


# ---------------------------------------------------------------------------
# load_oil_ledger_from_cache
# ---------------------------------------------------------------------------
class TestLoadOilLedgerFromCache:
    @patch("func.config_loader.load_oil_ledger_cache")
    @patch("func.config_loader.has_oil_ledger_cache", return_value=True)
    def test_returns_ledger_when_cache_exists(self, mock_has, mock_load):
        mock_load.return_value = [
            {"标准名称": "0号柴油", "原始名称": "0# 柴油"}
        ]
        ledger = load_oil_ledger_from_cache()
        assert ledger is not None
        assert len(ledger._df) == 1

    @patch("func.config_loader.has_oil_ledger_cache", return_value=False)
    def test_returns_none_when_no_cache(self, mock_has):
        assert load_oil_ledger_from_cache() is None


# ---------------------------------------------------------------------------
# load_ledgers
# ---------------------------------------------------------------------------
class TestLoadLedgers:
    @patch("func.orchestration.load_equipment_ledger_from_cache")
    @patch("func.orchestration.load_oil_ledger_from_cache")
    def test_loads_both_when_both_enabled(self, mock_oil, mock_eq):
        mock_eq.return_value = "eq_ledger"
        mock_oil.return_value = "oil_ledger"
        eq, oil = load_ledgers(use_equipment=True, use_oil=True)
        assert eq == "eq_ledger"
        assert oil == "oil_ledger"

    @patch("func.orchestration.load_equipment_ledger_from_cache")
    @patch("func.orchestration.load_oil_ledger_from_cache")
    def test_skips_loading_when_disabled(self, mock_oil, mock_eq):
        eq, oil = load_ledgers(use_equipment=False, use_oil=False)
        assert eq is None
        assert oil is None
        mock_eq.assert_not_called()
        mock_oil.assert_not_called()

    @patch("func.orchestration.load_equipment_ledger_from_cache", return_value="eq")
    @patch("func.orchestration.load_oil_ledger_from_cache")
    def test_partial_loading(self, mock_oil, mock_eq):
        eq, oil = load_ledgers(use_equipment=True, use_oil=False)
        assert eq == "eq"
        assert oil is None
        mock_oil.assert_not_called()


# ---------------------------------------------------------------------------
# postprocess_with_ledgers
# ---------------------------------------------------------------------------
class TestPostprocessWithLedgers:
    @patch("func.ledger_postprocess.apply_ledger_matching")
    def test_delegates_to_apply_ledger_matching(self, mock_apply):
        mock_apply.return_value = True
        result = postprocess_with_ledgers("out.xlsx", "eq", "oil", {"s1": "df"})
        assert result is True
        mock_apply.assert_called_once_with("out.xlsx", "eq", "oil", {"s1": "df"})

    @patch("func.ledger_postprocess.apply_ledger_matching")
    def test_defaults_to_none_sheets(self, mock_apply):
        mock_apply.return_value = False
        result = postprocess_with_ledgers("out.xlsx")
        assert result is False
        mock_apply.assert_called_once_with("out.xlsx", None, None, None)


# ---------------------------------------------------------------------------
# postprocess_from_cache
# ---------------------------------------------------------------------------
class TestPostprocessFromCache:
    @patch("func.orchestration.load_ledgers")
    @patch("func.orchestration.postprocess_with_ledgers")
    def test_skips_when_both_disabled(self, mock_post, mock_load):
        result = postprocess_from_cache("out.xlsx")
        assert result is False
        mock_load.assert_not_called()
        mock_post.assert_not_called()

    @patch("func.orchestration.load_ledgers", return_value=("eq", "oil"))
    @patch("func.orchestration.postprocess_with_ledgers", return_value=True)
    def test_loads_and_processes(self, mock_post, mock_load):
        result = postprocess_from_cache("out.xlsx", use_equipment_ledger=True, use_oil_ledger=True)
        assert result is True
        mock_load.assert_called_once_with(use_equipment=True, use_oil=True)
        mock_post.assert_called_once_with("out.xlsx", "eq", "oil", None)

    @patch("func.orchestration.load_ledgers", return_value=(None, "oil"))
    @patch("func.orchestration.postprocess_with_ledgers", return_value=False)
    def test_passes_preloaded_sheets(self, mock_post, mock_load):
        sheets = {"sheet1": "dataframe"}
        result = postprocess_from_cache("out.xlsx", use_oil_ledger=True, preloaded_sheets=sheets)
        mock_post.assert_called_once_with("out.xlsx", None, "oil", sheets)


# ---------------------------------------------------------------------------
# build_worktime_header_mapping
# ---------------------------------------------------------------------------
class TestBuildWorktimeHeaderMapping:
    @patch("func.config_loader.get_worktime_header_mapping")
    def test_returns_base_mapping_when_no_overrides(self, mock_get):
        mock_get.return_value = {"mode": "position", "fuzzy": False, "entries": []}
        result = build_worktime_header_mapping()
        assert result == {"mode": "position", "fuzzy": False, "entries": []}

    @patch("func.config_loader.get_worktime_header_mapping")
    def test_overrides_mode(self, mock_get):
        mock_get.return_value = {"mode": "position", "fuzzy": False, "entries": []}
        result = build_worktime_header_mapping(mode="name")
        assert result["mode"] == "name"

    @patch("func.config_loader.get_worktime_header_mapping")
    def test_overrides_fuzzy(self, mock_get):
        mock_get.return_value = {"mode": "position", "fuzzy": False, "entries": []}
        result = build_worktime_header_mapping(fuzzy=True)
        assert result["fuzzy"] is True

    @patch("func.config_loader.get_worktime_header_mapping")
    def test_fuzzy_match_alias_used_when_fuzzy_is_none(self, mock_get):
        mock_get.return_value = {"mode": "position", "fuzzy": False, "entries": []}
        result = build_worktime_header_mapping(fuzzy_match=True)
        assert result["fuzzy"] is True

    @patch("func.config_loader.get_worktime_header_mapping")
    def test_fuzzy_takes_priority_over_fuzzy_match(self, mock_get):
        mock_get.return_value = {"mode": "position", "fuzzy": False, "entries": []}
        result = build_worktime_header_mapping(fuzzy=False, fuzzy_match=True)
        assert result["fuzzy"] is False

    @patch("func.config_loader.get_worktime_header_mapping")
    def test_all_params_together(self, mock_get):
        mock_get.return_value = {"mode": "position", "fuzzy": False, "entries": [{"index": 1}]}
        result = build_worktime_header_mapping(mode="name", fuzzy=True)
        assert result == {"mode": "name", "fuzzy": True, "entries": [{"index": 1}]}
