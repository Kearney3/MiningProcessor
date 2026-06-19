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
    has_keyring_secret,
    load_secret,
    migrate_passwords_to_keyring,
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
# store_secret
# ---------------------------------------------------------------------------
class TestStoreSecret:
    def test_stores_in_keyring_and_marks_sentinel(self, tmp_path):
        config_file = tmp_path / "config.user.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_USER_CONFIG_FILE", config_file),
            patch("func.secret_store.keyring") as mock_keyring,
        ):
            store_secret(("minebase", "api", "password"), "secret123")
            mock_keyring.set_password.assert_called_once_with(
                _KEYRING_SERVICE, "minebase.api.password", "secret123"
            )
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            assert saved["minebase"]["api"]["password"] == _KEYRING_SENTINEL


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
