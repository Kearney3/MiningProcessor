"""func/secret_store.py 安全凭证存储测试"""
import json
import pathlib
import sys
from unittest.mock import patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader
from func.secret_store import (
    _KEYRING_SENTINEL,
    _KEYRING_SERVICE,
    _keyring_key,
    _is_secret_value,
    has_keyring_secret,
    load_minebase_secret,
    load_secret,
    migrate_passwords_to_keyring,
    save_minebase_secrets,
    store_secret,
)


@pytest.fixture(autouse=True)
def _reset_config_cache():
    """每个测试前后清空配置缓存，避免跨测试污染。"""
    config_loader._invalidate_config_cache()
    yield
    config_loader._invalidate_config_cache()


# ---------------------------------------------------------------------------
# _keyring_key
# ---------------------------------------------------------------------------
class TestKeyringKey:
    def test_converts_path_to_dotted_string(self):
        assert _keyring_key(("minebase", "api", "password")) == "minebase.api.password"

    def test_single_element(self):
        assert _keyring_key(("password",)) == "password"


# ---------------------------------------------------------------------------
# _is_secret_value
# ---------------------------------------------------------------------------
class TestIsSecretValue:
    def test_returns_true_for_real_password(self):
        assert _is_secret_value("my_secret") is True

    def test_returns_false_for_empty_string(self):
        assert _is_secret_value("") is False

    def test_returns_false_for_none(self):
        assert _is_secret_value(None) is False

    def test_returns_false_for_sentinel(self):
        assert _is_secret_value(_KEYRING_SENTINEL) is False

    def test_returns_false_for_legacy_sentinel(self):
        assert _is_secret_value("__KEYRING_SENTINEL__") is False


# ---------------------------------------------------------------------------
# store_secret
# ---------------------------------------------------------------------------
class TestStoreSecret:
    def test_stores_in_keyring_and_returns_true(self):
        """store_secret 只写 Keychain 并返回 True，不修改配置文件。"""
        with patch("func.secret_store.keyring") as mock_keyring:
            result = store_secret(("minebase", "api", "password"), "secret123")
            mock_keyring.set_password.assert_called_once_with(
                _KEYRING_SERVICE, "minebase.api.password", "secret123",
            )
        assert result is True

    def test_returns_false_on_keyring_failure(self):
        """Keychain 写入失败时应返回 False。"""
        with patch("func.secret_store.keyring") as mock_keyring:
            mock_keyring.set_password.side_effect = OSError("keychain unavailable")
            result = store_secret(("minebase", "database", "password"), "new_pass")
        assert result is False


# ---------------------------------------------------------------------------
# save_minebase_secrets
# ---------------------------------------------------------------------------
class TestSaveMinebaseSecrets:
    def test_writes_to_keyring_and_replaces_with_sentinel(self, tmp_path):
        """真实密码应写入 Keychain 并在返回的配置中替换为 sentinel。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            cfg = {
                "api": {"url": "http://example.com", "username": "admin", "password": "secret123"},
                "database": {"host": "localhost", "port": 5432, "user": "postgres", "password": "db_pass"},
            }
            result = save_minebase_secrets(cfg)

        assert mock_keyring.set_password.call_count == 2
        assert result["api"]["password"] == _KEYRING_SENTINEL
        assert result["database"]["password"] == _KEYRING_SENTINEL
        # 非密码字段保持不变
        assert result["api"]["url"] == "http://example.com"
        assert result["database"]["user"] == "postgres"

    def test_skips_empty_and_sentinel_values(self):
        """空密码和 sentinel 值不应写入 Keychain。"""
        with patch("func.secret_store.keyring") as mock_keyring:
            cfg = {
                "api": {"password": ""},
                "database": {"password": _KEYRING_SENTINEL},
            }
            result = save_minebase_secrets(cfg)

        mock_keyring.set_password.assert_not_called()
        assert result["api"]["password"] == ""
        assert result["database"]["password"] == _KEYRING_SENTINEL

    def test_keeps_plaintext_on_keyring_failure(self, tmp_path):
        """Keychain 写入失败时密码应保留在返回的配置中。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            mock_keyring.set_password.side_effect = OSError("keychain unavailable")
            cfg = {"database": {"password": "hunter2"}}
            result = save_minebase_secrets(cfg)

        assert result["database"]["password"] == "hunter2"

    def test_does_not_mutate_input_config(self):
        """不应修改传入的原始配置字典。"""
        with patch("func.secret_store.keyring"):
            cfg = {"api": {"password": "original"}}
            save_minebase_secrets(cfg)

        assert cfg["api"]["password"] == "original"


# ---------------------------------------------------------------------------
# load_minebase_secret
# ---------------------------------------------------------------------------
class TestLoadMinebaseSecret:
    def test_delegates_to_load_secret(self, tmp_path):
        """load_minebase_secret 应正确委托给 load_secret。"""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"database": {"password": "real_pass"}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            result = load_minebase_secret("database")
        assert result == "real_pass"

    def test_returns_keychain_value(self, tmp_path):
        """sentinel 密码应从 Keychain 解密。"""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": _KEYRING_SENTINEL}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            mock_keyring.get_password.return_value = "from_keychain"
            result = load_minebase_secret("api")
        assert result == "from_keychain"


# ---------------------------------------------------------------------------
# load_secret
# ---------------------------------------------------------------------------
class TestLoadSecret:
    def test_returns_plaintext_when_not_sentinel(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": "plain123"}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            result = load_secret(("minebase", "api", "password"))
        assert result == "plain123"

    def test_returns_keychain_value_when_sentinel(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": _KEYRING_SENTINEL}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            mock_keyring.get_password.return_value = "from_keychain"
            result = load_secret(("minebase", "api", "password"))
        assert result == "from_keychain"
        mock_keyring.get_password.assert_called_once_with(_KEYRING_SERVICE, "minebase.api.password")

    def test_returns_empty_when_keychain_missing(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": _KEYRING_SENTINEL}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            mock_keyring.get_password.return_value = None
            result = load_secret(("minebase", "api", "password"))
        assert result == ""

    def test_falls_back_to_legacy_user_config_when_keychain_missing(self, tmp_path):
        """Keychain 无条目时应从 user_config.minebase 旧格式回退读取明文密码。"""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"database": {"password": _KEYRING_SENTINEL}}}),
            encoding="utf-8",
        )
        user_file = tmp_path / "config.user.json"
        user_file.write_text(
            json.dumps({
                "user_config": {
                    "minebase": {
                        "database": {"password": "legacy_db_pass"},
                    }
                },
                "minebase": {
                    "database": {"password": _KEYRING_SENTINEL},
                },
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", user_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            mock_keyring.get_password.return_value = None
            result = load_secret(("minebase", "database", "password"))
        assert result == "legacy_db_pass"

    def test_returns_empty_when_path_missing(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            result = load_secret(("minebase", "api", "password"))
        assert result == ""


# ---------------------------------------------------------------------------
# has_keyring_secret
# ---------------------------------------------------------------------------
class TestHasKeyringSecret:
    def test_returns_true_when_sentinel(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": _KEYRING_SENTINEL}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            assert has_keyring_secret(("minebase", "api", "password")) is True

    def test_returns_false_when_plaintext(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": "plain"}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            assert has_keyring_secret(("minebase", "api", "password")) is False

    def test_returns_false_when_missing(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            assert has_keyring_secret(("minebase", "api", "password")) is False


# ---------------------------------------------------------------------------
# migrate_passwords_to_keyring
# ---------------------------------------------------------------------------
class TestMigratePasswords:
    def test_migrates_plaintext_passwords(self, tmp_path):
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "minebase": {
                    "api": {"password": "api_pass"},
                    "database": {"password": "db_pass"},
                }
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            migrate_passwords_to_keyring()
            assert mock_keyring.set_password.call_count == 2
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            assert saved["minebase"]["api"]["password"] == _KEYRING_SENTINEL
            assert saved["minebase"]["database"]["password"] == _KEYRING_SENTINEL

    def test_idempotent_skips_already_migrated(self, tmp_path):
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "minebase": {
                    "api": {"password": _KEYRING_SENTINEL},
                    "database": {"password": _KEYRING_SENTINEL},
                }
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            migrate_passwords_to_keyring()
            mock_keyring.set_password.assert_not_called()

    def test_skips_empty_passwords(self, tmp_path):
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": ""}, "database": {}}}),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            migrate_passwords_to_keyring()
            mock_keyring.set_password.assert_not_called()

    def test_handles_keyring_failure_and_continues(self, tmp_path):
        """Keychain 写入失败时应跳过该路径继续处理其余路径。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "minebase": {
                    "api": {"password": "api_pass"},
                    "database": {"password": "db_pass"},
                }
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            # api 写入失败，database 写入成功
            def _fail_then_succeed(service: str, key: str, value: str):
                if "api" in key:
                    raise OSError("keychain locked")
            mock_keyring.set_password.side_effect = _fail_then_succeed

            migrate_passwords_to_keyring()

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        # api 密码保留明文（迁移失败）
        assert saved["minebase"]["api"]["password"] == "api_pass"
        # database 密码迁移成功，标记为 sentinel
        assert saved["minebase"]["database"]["password"] == _KEYRING_SENTINEL

    def test_migrates_from_legacy_user_config_minebase(self, tmp_path):
        """应从 user_config.minebase 旧格式迁移明文密码到 Keychain。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "user_config": {
                    "minebase": {
                        "database": {"password": "legacy_db_pass"},
                    }
                },
                "minebase": {
                    "database": {"password": _KEYRING_SENTINEL},
                },
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            migrate_passwords_to_keyring()

        # 应从旧格式读取密码并写入 keychain
        mock_keyring.set_password.assert_called_once_with(
            _KEYRING_SERVICE, "minebase.database.password", "legacy_db_pass",
        )

    def test_cleans_legacy_plaintext_after_migration(self, tmp_path):
        """迁移成功后应清理 user_config.minebase 中的明文密码。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "user_config": {
                    "minebase": {
                        "database": {"password": "legacy_db_pass"},
                    }
                },
                "minebase": {
                    "database": {"password": _KEYRING_SENTINEL},
                },
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            migrate_passwords_to_keyring()

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        # 旧格式的 minebase 段落应被移除（所有密码已迁移）
        assert "minebase" not in saved.get("user_config", {})

    def test_cleans_both_top_level_and_legacy_passwords(self, tmp_path):
        """当顶层和旧格式都有明文密码时，两者都应迁移并清理。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "user_config": {
                    "minebase": {
                        "api": {"password": "legacy_api_pass"},
                        "database": {"password": "legacy_db_pass"},
                    }
                },
                "minebase": {
                    "api": {"password": _KEYRING_SENTINEL},
                    "database": {"password": _KEYRING_SENTINEL},
                },
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            migrate_passwords_to_keyring()

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert mock_keyring.set_password.call_count == 2
        # 旧格式的 minebase 段落应被完全移除
        assert "minebase" not in saved.get("user_config", {})
        # 顶层 sentinel 保持不变
        assert saved["minebase"]["api"]["password"] == _KEYRING_SENTINEL
        assert saved["minebase"]["database"]["password"] == _KEYRING_SENTINEL

    def test_preserves_legacy_section_when_partial_migration(self, tmp_path):
        """部分迁移失败时，旧格式中已成功的密码应标记为 sentinel。"""
        config_file = tmp_path / "config.user.json"
        config_file.write_text(
            json.dumps({
                "user_config": {
                    "minebase": {
                        "api": {"password": "legacy_api_pass"},
                        "database": {"password": "legacy_db_pass"},
                    }
                },
                "minebase": {
                    "api": {"password": _KEYRING_SENTINEL},
                    "database": {"password": _KEYRING_SENTINEL},
                },
            }),
            encoding="utf-8",
        )
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            # api 迁移失败，database 迁移成功
            def _fail_api(service: str, key: str, value: str):
                if "api" in key:
                    raise OSError("keychain locked")
            mock_keyring.set_password.side_effect = _fail_api

            migrate_passwords_to_keyring()

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        legacy_mb = saved.get("user_config", {}).get("minebase", {})
        # api 密码保留明文（迁移失败）
        assert legacy_mb["api"]["password"] == "legacy_api_pass"
        # database 密码迁移成功，标记为 sentinel
        assert legacy_mb["database"]["password"] == _KEYRING_SENTINEL
