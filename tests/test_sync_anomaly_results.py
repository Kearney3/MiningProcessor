"""同步异常值明细的回归测试。"""
import json
from unittest.mock import MagicMock, patch

import pandas as pd

from func.anomaly import detect_and_filter
from func.anomaly.rules import AnomalyConfig
from func.sync_to_minebase import sync


def _write_mapping(path):
    path.write_text(
        json.dumps(
            {
                "fuel_consumption": {
                    "日期": "date",
                    "设备名称": "sourceEquipmentName",
                    "油品消耗": "consumption",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_sync_anomalies_follow_date_filter_and_include_source_locators(tmp_path):
    """异常明细应与日期过滤后的同步数据一致，并能定位源表和源行。"""
    mapping_path = tmp_path / "mapping.json"
    _write_mapping(mapping_path)

    def _process_fuel(*args, **kwargs):
        anomaly_config = kwargs["anomaly_config"]
        source_df = pd.DataFrame(
            {
                "日期": ["2026-08-23", "2026-08-24"],
                "设备名称": ["TR-01", "TR-02"],
                "油品消耗": [60000, 60000],
            },
        )
        detect_and_filter(source_df, "fuel", config=anomaly_config)
        return [
            {"date": "2026-08-23", "sourceEquipmentName": "TR-01", "consumption": 60000},
            {"date": "2026-08-24", "sourceEquipmentName": "TR-02", "consumption": 60000},
        ]

    with patch("func.sync_to_minebase.discover_files") as discover, \
         patch("func.sync_to_minebase._process_fuel_file", side_effect=_process_fuel), \
         patch("func.sync_to_minebase.sync_via_api", return_value={"success": 1, "skipped": 0, "failed": 0, "warnings": []}), \
         patch("func.sync_to_minebase.MineBaseAPIClient") as api_cls, \
         patch("func.sync_to_minebase.get_minebase_api_config", return_value={"url": "http://test", "username": "u", "password": "p"}):
        discover.return_value = {"fuel": [tmp_path / "Fuel.xlsx"]}
        api_cls.return_value = MagicMock()
        results = sync(
            tmp_path,
            mode="api",
            data_types=["fuel"],
            mapping_file=mapping_path,
            date_start="2026-08-24",
            date_end="2026-08-24",
            anomaly_config=AnomalyConfig(enabled=True),
        )

    anomalies = results["fuel"]["anomalies"]
    assert [record["日期"] for record in anomalies] == ["2026-08-24"]
    assert anomalies[0]["源表"] == "油耗信息"
    assert anomalies[0]["源行号"] == 3
    assert anomalies[0]["相关字段"] == "油品消耗"
    assert anomalies[0]["检测方法"] == "threshold"
