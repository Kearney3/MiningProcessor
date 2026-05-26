"""config_loader 模块测试"""
import json
import pathlib
import sys

import pytest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader


@pytest.fixture(autouse=True)
def _reset_runtime_config():
    """每个测试前后重置运行时配置，防止测试间污染"""
    config_loader._runtime_config = None
    yield
    config_loader._runtime_config = None


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """创建临时 config.json 并替换模块级路径"""
    config_data = {
        "device_load_map": {"TR100": 35, "EH4000": 85},
        "device_load_map_old": {"TR100": 32, "EH4000": 80},
        "default_year": 2025,
        "default_month": 6,
        "shift_mapping": {"白班": "Day", "夜班": "Night"},
        "output_naming": {"include_date": True},
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    return config_data, config_file


class TestLoadConfig:
    def test_load_returns_dict(self, temp_config):
        result = config_loader.load_config()
        assert isinstance(result, dict)

    def test_load_contains_device_load_map(self, temp_config):
        result = config_loader.load_config()
        assert "device_load_map" in result
        assert result["device_load_map"]["TR100"] == 35

    def test_load_missing_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", tmp_path / "nonexistent.json")
        with pytest.raises(FileNotFoundError):
            config_loader.load_config()


class TestSaveConfig:
    def test_save_writes_json(self, temp_config):
        _, config_file = temp_config
        new_config = {"device_load_map": {"NEW_DEVICE": 99}}
        config_loader.save_config(new_config)

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["device_load_map"]["NEW_DEVICE"] == 99

    def test_save_preserves_unicode(self, temp_config):
        _, config_file = temp_config
        config_loader.save_config({"shift_mapping": {"白班": "Day"}})

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["shift_mapping"]["白班"] == "Day"


class TestGetDeviceLoadMap:
    def test_get_new_version(self, temp_config):
        result = config_loader.get_device_load_map("new")
        assert result["TR100"] == 35

    def test_get_old_version(self, temp_config):
        result = config_loader.get_device_load_map("old")
        assert result["TR100"] == 32

    def test_default_version_is_new(self, temp_config):
        result = config_loader.get_device_load_map()
        assert result["TR100"] == 35

    def test_returns_empty_for_missing_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        result = config_loader.get_device_load_map()
        assert result == {}

    def test_runtime_config_takes_priority(self, temp_config):
        config_loader._runtime_config = {"device_load_map": {"RUNTIME_ONLY": 42}}
        result = config_loader.get_device_load_map()
        assert result == {"RUNTIME_ONLY": 42}


class TestApplyDeviceLoadMap:
    def test_apply_updates_runtime_not_file(self, temp_config):
        _, config_file = temp_config
        result = config_loader.apply_device_load_map({"TR100": 99})
        assert result["TR100"] == 99

        # 运行时配置已更新
        runtime = config_loader.get_device_load_map()
        assert runtime["TR100"] == 99

        # 文件未变
        file_config = json.loads(config_file.read_text(encoding="utf-8"))
        assert file_config["device_load_map"]["TR100"] == 35

    def test_apply_replaces_device_load_map(self, temp_config):
        """apply 替换（而非合并）device_load_map"""
        result = config_loader.apply_device_load_map({"ONLY": 50})
        assert result == {"ONLY": 50}
        # 原有 key 不再存在
        assert "TR100" not in result

    def test_apply_sets_runtime_config(self, temp_config):
        config_loader.apply_device_load_map({"X": 1})
        assert config_loader._runtime_config is not None
        assert config_loader._runtime_config["device_load_map"]["X"] == 1


class TestUpdateDeviceLoadMap:
    def test_update_writes_to_file(self, temp_config):
        _, config_file = temp_config
        config_loader.update_device_load_map({"TR100": 77})

        file_config = json.loads(config_file.read_text(encoding="utf-8"))
        assert file_config["device_load_map"]["TR100"] == 77

    def test_update_preserves_other_keys(self, temp_config):
        _, config_file = temp_config
        config_loader.update_device_load_map({"TR100": 77})

        file_config = json.loads(config_file.read_text(encoding="utf-8"))
        assert file_config["device_load_map"]["EH4000"] == 85

    def test_update_creates_key_if_missing(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"other": "data"}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)

        result = config_loader.update_device_load_map({"X": 1})
        assert result["X"] == 1

        file_config = json.loads(config_file.read_text(encoding="utf-8"))
        assert file_config["device_load_map"]["X"] == 1

    def test_update_merges_with_existing(self, temp_config):
        """update 合并而非替换"""
        config_loader.update_device_load_map({"NEW": 50})
        file_config = config_loader.load_config()
        assert file_config["device_load_map"]["TR100"] == 35  # 保留
        assert file_config["device_load_map"]["NEW"] == 50   # 新增


class TestGetShiftMapping:
    def test_returns_shift_mapping(self, temp_config):
        result = config_loader.get_shift_mapping()
        assert result["白班"] == "Day"
        assert result["夜班"] == "Night"

    def test_returns_empty_when_missing(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        assert config_loader.get_shift_mapping() == {}


class TestGetDefaultYearMonth:
    def test_get_default_year(self, temp_config):
        assert config_loader.get_default_year() == 2025

    def test_get_default_month(self, temp_config):
        assert config_loader.get_default_month() == 6

    def test_fallback_year(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        assert config_loader.get_default_year() == 2025

    def test_fallback_month(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        assert config_loader.get_default_month() == 1


class TestGetConfigFilePath:
    def test_returns_path_object(self, temp_config):
        result = config_loader.get_config_file_path()
        assert isinstance(result, Path)
