"""系统资源配置与生产并行度测试。"""
from __future__ import annotations

import json
from concurrent.futures import Future

import pandas as pd
import pytest

from func import config_loader
from func.excel_production_enhanced import MiningDataProcessor


def test_cpu_cores_are_persisted_and_validated(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    user_file = tmp_path / "config.user.json"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)
    config_loader._invalidate_config_cache()

    available = config_loader.get_available_cpu_cores()
    assert config_loader.get_cpu_cores() == config_loader.get_default_cpu_cores()

    assert config_loader.set_cpu_cores("1") == 1
    assert config_loader.get_cpu_cores() == 1
    saved = json.loads(user_file.read_text(encoding="utf-8"))
    assert saved["user_config"][config_loader.CPU_CORES_CONFIG_KEY] == 1

    with pytest.raises(ValueError):
        config_loader.set_cpu_cores(available + 1)

    config_loader._invalidate_config_cache()


def test_process_folder_uses_configured_cpu_cores_when_workers_omitted(monkeypatch, tmp_path):
    import func.excel_production_enhanced as production_module

    requested_workers = []

    class ExecutorSpy:
        def __init__(self, max_workers):
            requested_workers.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future

    processor = MiningDataProcessor(device_load_map={}, raw_start=-1)
    monkeypatch.setattr(config_loader, "get_cpu_cores", lambda: 2)
    monkeypatch.setattr(production_module, "ThreadPoolExecutor", ExecutorSpy)
    monkeypatch.setattr(
        processor,
        "collect_excel_files",
        lambda _folder: [str(tmp_path / "report.xlsx")],
    )
    monkeypatch.setattr(
        processor,
        "process_single_file_safe",
        lambda *_args: (True, "report.xlsx", pd.DataFrame(), pd.DataFrame(), None),
    )

    processor.process_folder(str(tmp_path), return_sheets=True)

    assert requested_workers == [2]
