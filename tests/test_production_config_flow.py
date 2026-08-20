import pathlib
import sys
from typing import ClassVar

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader  # noqa: E402
from func.excel_production_enhanced import MiningDataProcessor  # noqa: E402
from gui import logic  # noqa: E402


class ProcessorSpy:
    instances: ClassVar[list] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.single_calls = []
        self.folder_calls = []
        self.__class__.instances.append(self)

    def process_single_file(self, path, output_file):
        self.single_calls.append((path, output_file))

    def process_folder(self, path, cancel_event=None):
        self.folder_calls.append(path)


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


def test_execute_task_passes_current_device_load_map_to_production_processor(monkeypatch, tmp_path):
    ProcessorSpy.instances.clear()
    monkeypatch.setattr(config_loader, "get_load_map_version", lambda: "new")
    monkeypatch.setattr(config_loader, "get_device_load_map", lambda version="new": {"TR100": 77, "XDE120": 44})
    import func.excel_production_enhanced as prod_mod
    monkeypatch.setattr(prod_mod, "MiningDataProcessor", ProcessorSpy)

    input_file = tmp_path / "sample.xlsx"
    input_file.write_text("placeholder", encoding="utf-8")

    error, _extra = logic._execute_task("production", str(input_file), raw_start=9)

    assert error is None
    assert len(ProcessorSpy.instances) == 1
    processor = ProcessorSpy.instances[0]
    assert processor.kwargs == {
        "raw_start": 9,
        "device_load_map": {"TR100": 77, "XDE120": 44},
        "skip_hidden_rows": False,
        "skip_hidden_cols": False,
        "anomaly_config": None,
        "filter_zero_hours_meter": False,
        "filter_zero_km_meter": False,
        "filter_zero_run_hours": False,
        "filter_zero_run_km": False,
    }
