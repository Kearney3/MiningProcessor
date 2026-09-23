import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader  # noqa: E402
from func.excel_production_enhanced import MiningDataProcessor  # noqa: E402


def test_mining_data_processor_prefers_explicit_device_load_map(monkeypatch):
    def fail_if_called(version="new"):
        raise AssertionError("config_loader should not be called when device_load_map is provided")

    monkeypatch.setattr(config_loader, "get_device_load_map", fail_if_called)

    processor = MiningDataProcessor(device_load_map={"TR100": 99}, raw_start=8)

    assert processor.raw_start == 8
    assert processor.load_map == {"TR100": 99}


def test_mining_data_processor_loads_runtime_config_when_not_explicit(monkeypatch):
    monkeypatch.setattr(config_loader, "get_device_load_map", lambda version="new": {"EH4000": 88})

    processor = MiningDataProcessor()

    assert processor.load_map == {"EH4000": 88}
