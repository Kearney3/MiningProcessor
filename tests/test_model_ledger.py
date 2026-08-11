import pandas as pd

from func.model_ledger import ModelLedger


def _ledger(records):
    ledger = ModelLedger()
    ledger._df = pd.DataFrame(records)
    ledger._build_search_cache()
    return ledger


def test_model_ledger_matches_standard_id_and_returns_attributes():
    ledger = _ledger([{
        "标准设备编号": "HT#001",
        "标准公司名称": "公司A",
        "所有权": "自有",
        "设备型号": "NTE240",
        "设备类型": "矿卡",
        "内部分类": "采矿设备",
    }])
    result = ledger.match_by_standard_id("HT#001")
    assert result["所有权"] == "自有"
    assert ledger.match_by_standard_id("not-found") is None


def test_conflicting_duplicate_standard_id_is_not_silently_selected():
    ledger = _ledger([
        {"标准设备编号": "HT#1", "标准公司名称": "A", "所有权": "自有", "设备型号": "X", "设备类型": "矿卡", "内部分类": "采矿"},
        {"标准设备编号": "HT#1", "标准公司名称": "B", "所有权": "租赁", "设备型号": "Y", "设备类型": "矿卡", "内部分类": "运输"},
    ])
    assert ledger.match_by_standard_id("HT#1") is None

