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
        """创建带 minebase 配置的临时环境并 mock keyring。"""
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

        # Mock keyring with in-memory store
        _store: dict[str, str] = {}

        def _set_password(service: str, key: str, value: str):
            _store[f"{service}:{key}"] = value

        def _get_password(service: str, key: str) -> str | None:
            return _store.get(f"{service}:{key}")

        monkeypatch.setattr("keyring.set_password", _set_password)
        monkeypatch.setattr("keyring.get_password", _get_password)

        return _store, user_file

    def test_save_real_password_stores_in_keyring(self, minebase_env):
        """首次保存真实密码应写入 Keychain 并在配置中标记 sentinel。"""
        _store, user_file = minebase_env

        cfg = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "hunter2"},
        }
        config_loader.save_minebase_config(cfg)

        # 密码应存入 keyring
        keyring_key = "MiningProcessor:minebase.database.password"
        assert _store.get(keyring_key) == "hunter2"

        # 配置文件中密码应为 sentinel
        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["minebase"]["database"]["password"] == "__keyring__"
        # 用户名应正常保存
        assert saved["minebase"]["database"]["user"] == "admin"

    def test_save_sentinel_does_not_overwrite_real_password(self, minebase_env):
        """第二次保存（密码字段为 sentinel 掩码）不应覆盖 Keychain 中的真实密码。

        这是关键回归测试：模拟用户首次输入密码 → 保存 → 重新加载（字段显示掩码）
        → 修改用户名 → 再次保存。第二次保存不应把 sentinel 写入 Keychain。
        """
        _store, user_file = minebase_env
        keyring_key = "MiningProcessor:minebase.database.password"

        # 第一次保存：真实密码
        cfg1 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "hunter2"},
        }
        config_loader.save_minebase_config(cfg1)
        assert _store[keyring_key] == "hunter2"

        # 第二次保存：密码为 sentinel（模拟 UI 掩码），只改了用户名
        cfg2 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "new_admin", "password": "__keyring__"},
        }
        config_loader.save_minebase_config(cfg2)

        # 关键断言：keyring 中仍为真实密码，不应被 sentinel 覆盖
        assert _store[keyring_key] == "hunter2"

        # 用户名应更新为新值
        saved = json.loads(user_file.read_text(encoding="utf-8"))
        assert saved["minebase"]["database"]["user"] == "new_admin"

    def test_save_empty_password_does_not_store(self, minebase_env):
        """空密码不应写入 Keychain。"""
        _store, user_file = minebase_env

        cfg = {
            "mode": "api",
            "api": {"url": "http://localhost:3000", "username": "user", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
        }
        config_loader.save_minebase_config(cfg)

        # 空密码不应写入 keyring
        assert len(_store) == 0

    def test_load_secret_returns_real_password_after_sentinel_save(self, minebase_env):
        """完整 save → load 往返：sentinel 保存后 load_secret 应返回真实密码。"""
        from func import secret_store

        _store, user_file = minebase_env

        # 第一次保存真实密码
        cfg1 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "s3cret"},
        }
        config_loader.save_minebase_config(cfg1)

        # 第二次保存 sentinel（掩码）
        cfg2 = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "__keyring__"},
        }
        config_loader.save_minebase_config(cfg2)

        # load_secret 应返回真实密码
        config_loader._invalidate_config_cache()
        result = secret_store.load_secret(("minebase", "database", "password"))
        assert result == "s3cret"

    def test_save_keeps_plaintext_when_keyring_fails(self, minebase_env):
        """Keychain 写入失败时密码应以明文保留在配置中，不丢失。"""
        _store, user_file = minebase_env

        # 让 keyring 写入抛异常
        def _fail_set(service: str, key: str, value: str):
            raise OSError("keychain unavailable")
        import keyring as _kr
        _kr.set_password = _fail_set  # type: ignore[assignment]

        cfg = {
            "mode": "database",
            "api": {"url": "", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "admin", "password": "hunter2"},
        }
        config_loader.save_minebase_config(cfg)

        saved = json.loads(user_file.read_text(encoding="utf-8"))
        # 密码应保留明文，不被替换为 sentinel
        assert saved["minebase"]["database"]["password"] == "hunter2"
        assert saved["minebase"]["database"]["user"] == "admin"
