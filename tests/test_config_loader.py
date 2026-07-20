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
    """创建临时 config.json + config.user.json 并替换模块级路径"""
    config_data = {
        "device_load_map": {"TR100": 35, "EH4000": 85},
        "device_load_map_old": {"TR100": 32, "EH4000": 80},
        "default_year": 2025,
        "default_month": 6,
        "shift_mapping": {"白班": "Day", "夜班": "Night"},
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    # 确保测试不会读取真实的 config.user.json
    user_file = tmp_path / "config.user.json"
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)
    return config_data, config_file


class TestLoadConfig:
    def test_load_returns_dict(self, temp_config):
        result = config_loader.load_config()
        assert isinstance(result, dict)

    def test_load_contains_device_load_map(self, temp_config):
        result = config_loader.load_config()
        assert "device_load_map" in result
        assert result["device_load_map"]["TR100"] == 35

    def test_load_missing_files_returns_empty(self, tmp_path, monkeypatch):
        """两个配置文件都不存在时返回空 dict（不再抛异常）"""
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", tmp_path / "nonexistent.json")
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "nonexistent_user.json")
        result = config_loader.load_config()
        assert result == {}

    def test_load_merges_user_over_default(self, tmp_path, monkeypatch):
        """config.user.json 中的值覆盖 config.json"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"default_year": 2024, "shift_mapping": {"白班": "Day"}}), encoding="utf-8")
        user_file = tmp_path / "config.user.json"
        user_file.write_text(json.dumps({"default_year": 2026}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        result = config_loader.load_config()
        assert result["default_year"] == 2026          # user 覆盖
        assert result["shift_mapping"]["白班"] == "Day"  # 保留 default

    def test_load_user_config_missing_uses_default(self, tmp_path, monkeypatch):
        """config.user.json 不存在时只返回 config.json 内容"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"default_year": 2025}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "nope.json")

        result = config_loader.load_config()
        assert result == {"default_year": 2025}


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
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "nope.json")
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


class TestGetDefaultYearMonth:
    def test_get_default_year(self, temp_config):
        assert config_loader.get_default_year() == 2025

    def test_get_default_month(self, temp_config):
        assert config_loader.get_default_month() == 6

    def test_fallback_year(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "nope.json")
        assert config_loader.get_default_year() == 2025

    def test_fallback_month(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "nope.json")
        assert config_loader.get_default_month() == 1


class TestGetConfigFilePath:
    def test_returns_path_object(self, temp_config):
        result = config_loader.get_config_file_path()
        assert isinstance(result, Path)


class TestUserConfigReadWrite:
    """验证 user_config 读写走 config.user.json"""

    def test_save_user_config_writes_to_user_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        user_file = tmp_path / "config.user.json"
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        config_loader.save_user_config({"database": {"db_host": "10.0.0.1"}})

        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["user_config"]["database"]["db_host"] == "10.0.0.1"
        # config.json 不应包含 user_config
        default = json.loads(config_file.read_text(encoding="utf-8"))
        assert "user_config" not in default

    def test_update_user_config_merges_into_user_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        user_file = tmp_path / "config.user.json"
        user_file.write_text(json.dumps({"user_config": {"database": {"db_host": "old"}}}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        config_loader.update_user_config({"database": {"db_host": "new"}})

        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["user_config"]["database"]["db_host"] == "new"

    def test_reset_user_config_clears_user_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        user_file = tmp_path / "config.user.json"
        user_file.write_text(json.dumps({"user_config": {"database": {"db_host": "x"}}}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        config_loader.reset_user_config()

        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["user_config"] == {}

    def test_get_user_config_reads_merged(self, tmp_path, monkeypatch):
        """get_user_config 从合并后的配置读取"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"user_config": {"database": {"db_host": "default_host"}}}), encoding="utf-8")
        user_file = tmp_path / "config.user.json"
        user_file.write_text(json.dumps({"user_config": {"database": {"db_host": "user_host", "db_port": 5432}}}), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        result = config_loader.get_user_config("database")
        assert result["db_host"] == "user_host"  # user 覆盖
        assert result["db_port"] == 5432          # user 新增


class TestDefaultLoadMaps:
    def test_new_map_not_empty(self):
        assert len(config_loader.DEFAULT_LOAD_MAP_NEW) > 0

    def test_old_map_not_empty(self):
        assert len(config_loader.DEFAULT_LOAD_MAP_OLD) > 0

    def test_new_map_has_expected_devices(self):
        assert "NTE240" in config_loader.DEFAULT_LOAD_MAP_NEW
        assert "TR100" in config_loader.DEFAULT_LOAD_MAP_NEW

    def test_get_default_load_map_new(self):
        result = config_loader.get_default_load_map("new")
        assert result == config_loader.DEFAULT_LOAD_MAP_NEW
        assert result is not config_loader.DEFAULT_LOAD_MAP_NEW  # 返回副本

    def test_get_default_load_map_old(self):
        result = config_loader.get_default_load_map("old")
        assert result == config_loader.DEFAULT_LOAD_MAP_OLD

    def test_get_default_load_map_returns_copy(self):
        result = config_loader.get_default_load_map()
        result["TEST"] = 99
        assert "TEST" not in config_loader.DEFAULT_LOAD_MAP_NEW


class TestSaveMinebaseConfig:
    """save_minebase_config 与 secret_store 的集成测试。"""

    @pytest.fixture
    def minebase_env(self, tmp_path, monkeypatch):
        """创建带 minebase 配置的临时环境。"""
        config_data = {
            "minebase": {
                "mode": "database",
                "api": {"url": "http://localhost:3000", "username": "", "password": ""},
                "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
            },
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)

        user_file = tmp_path / "config.user.json"
        monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

        return user_file

    def test_save_real_password_encrypts(self, minebase_env):
        """首次保存真实密码应加密存储。"""
        user_file = minebase_env

        cfg = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "hunter2"},
        }
        config_loader.save_minebase_config(cfg)

        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["minebase"]["database"]["password"].startswith("__enc__")
        assert saved["minebase"]["database"]["user"] == "admin"

    def test_save_encrypted_does_not_re_encrypt(self, minebase_env):
        """第二次保存（密码已是加密格式）不应重复加密。"""
        from func.secret_store import _decrypt

        user_file = minebase_env

        cfg1 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "hunter2"},
        }
        config_loader.save_minebase_config(cfg1)

        saved1 = json.loads(user_file.read_text(encoding="utf-8"))
        encrypted_pw = saved1["minebase"]["database"]["password"]

        cfg2 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "new_admin", "password": encrypted_pw},
        }
        config_loader.save_minebase_config(cfg2)

        saved2 = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved2["minebase"]["database"]["password"] == encrypted_pw
        assert _decrypt(saved2["minebase"]["database"]["password"]) == "hunter2"
        assert saved2["minebase"]["database"]["user"] == "new_admin"

    def test_save_empty_password_does_not_encrypt(self, minebase_env):
        """空密码不应加密。"""
        user_file = minebase_env

        cfg = {
            "mode": "api",
            "api": {"url": "http://localhost:3000", "username": "user", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
        }
        config_loader.save_minebase_config(cfg)

        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["minebase"]["database"]["password"] == ""
        assert saved["minebase"]["api"]["password"] == ""

    def test_load_secret_returns_real_password_after_encrypted_save(self, minebase_env):
        """完整 save → load 往返：加密保存后 load_secret 应返回真实密码。"""
        from func import secret_store

        user_file = minebase_env

        cfg1 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "s3cret"},
        }
        config_loader.save_minebase_config(cfg1)

        config_loader._invalidate_config_cache()
        result = secret_store.load_secret(("minebase", "database", "password"))
        assert result == "s3cret"


# ---------------------------------------------------------------------------
# 异常值检测配置
# ---------------------------------------------------------------------------

class TestAnomalyDetectionConfig:
    """异常值检测配置的 get / update / save 测试。"""

    def test_get_anomaly_detection_config_defaults(self):
        """无用户覆盖时应返回 DEFAULT_ANOMALY_DETECTION。"""
        cfg = config_loader.get_anomaly_detection_config()
        assert cfg["enabled"] is False
        assert cfg["sigma_n"] == 3.0
        assert cfg["percentile_low"] == 1.0
        assert cfg["percentile_high"] == 99.0
        assert "fuel" in cfg["thresholds"]
        assert "production" in cfg["thresholds"]
        assert "electrical" in cfg["thresholds"]
        assert "worktime" in cfg["thresholds"]

    def test_get_anomaly_thresholds_all(self):
        """不指定 data_type 时返回全部阈值。"""
        thresholds = config_loader.get_anomaly_thresholds()
        assert "fuel" in thresholds
        assert "油品消耗" in thresholds["fuel"]

    def test_get_anomaly_thresholds_specific(self):
        """指定 data_type 时返回对应阈值。"""
        thresholds = config_loader.get_anomaly_thresholds("fuel")
        assert "油品消耗" in thresholds
        assert thresholds["油品消耗"]["max"] == 50000

    def test_get_anomaly_thresholds_unknown_type(self):
        """未知类型返回空 dict。"""
        thresholds = config_loader.get_anomaly_thresholds("unknown")
        assert thresholds == {}

    def test_get_anomaly_handling_rules_default(self):
        """默认处理规则应包含预配置的默认值策略。"""
        rules = config_loader.get_anomaly_handling_rules()
        assert "production" in rules
        assert "electrical" in rules
        assert "worktime" in rules
        assert rules["production"]["产量"]["strategy"] == "default_value"
        assert rules["production"]["产量"]["default"] == 0

    def test_update_anomaly_detection_config(self, temp_config):
        """更新应写入 config.user.json 并正确合并。"""
        _, config_file = temp_config
        updates = {"enabled": True, "sigma_n": 2.5}
        config_loader._invalidate_config_cache()
        result = config_loader.update_anomaly_detection_config(updates)
        assert result["enabled"] is True
        assert result["sigma_n"] == 2.5

        # 读取应合并默认值
        cfg = config_loader.get_anomaly_detection_config()
        assert cfg["enabled"] is True
        assert cfg["sigma_n"] == 2.5
        assert cfg["percentile_high"] == 99.0  # 默认值保留

    def test_save_anomaly_detection_config(self, temp_config):
        """整体保存应替换 user_config 中的 anomaly_detection 段。"""
        _, config_file = temp_config
        new_cfg = {"enabled": True, "generate_report": True}
        config_loader._invalidate_config_cache()
        config_loader.save_anomaly_detection_config(new_cfg)

        cfg = config_loader.get_anomaly_detection_config()
        assert cfg["enabled"] is True
        assert cfg["generate_report"] is True

