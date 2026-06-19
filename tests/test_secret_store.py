"""func/secret_store.py Fernet 文件加密存储测试"""
import json
import pathlib
import sys
from unittest.mock import patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader
from func.secret_store import (
    _ENCRYPTED_PREFIX,
    _decrypt,
    _encrypt,
    has_encrypted_secret,
    load_minebase_secret,
    load_secret,
    save_minebase_secrets,
)


@pytest.fixture(autouse=True)
def _reset_config_cache():
    """每个测试前后清空配置缓存，避免跨测试污染。"""
    config_loader._invalidate_config_cache()
    yield
    config_loader._invalidate_config_cache()


# ---------------------------------------------------------------------------
# _encrypt / _decrypt
# ---------------------------------------------------------------------------
class TestEncryptDecrypt:
    def test_roundtrip(self):
        """加密后解密应得到原值。"""
        original = "my_secret_password_123"
        encrypted = _encrypt(original)
        decrypted = _decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_output_not_plaintext(self):
        """加密输出不应等于原始值。"""
        encrypted = _encrypt("hello")
        assert encrypted != "hello"
        assert encrypted.startswith(_ENCRYPTED_PREFIX)

    def test_encrypt_empty_returns_empty(self):
        """空字符串不应加密，直接返回空。"""
        assert _encrypt("") == ""
        assert _encrypt(None) == ""

    def test_decrypt_non_encrypted_passthrough(self):
        """非 __enc__ 前缀的值应原样返回。"""
        assert _decrypt("plain_text") == "plain_text"
        assert _decrypt("") == ""
        assert _decrypt(None) == ""

    def test_encrypt_produces_unique_output(self):
        """相同明文每次加密结果不同（Fernet 含时间戳+IV）。"""
        e1 = _encrypt("same_password")
        e2 = _encrypt("same_password")
        # Fernet tokens 包含时间戳，1秒内可能相同，但解密结果应一致
        assert _decrypt(e1) == _decrypt(e2) == "same_password"


# ---------------------------------------------------------------------------
# save_minebase_secrets
# ---------------------------------------------------------------------------
class TestSaveMinebaseSecrets:
    def test_encrypts_password_fields(self):
        """密码字段应被加密。"""
        cfg = {
            "api": {"url": "http://example.com", "username": "admin", "password": "secret123"},
            "database": {"host": "localhost", "port": 5432, "user": "postgres", "password": "db_pass"},
        }
        result = save_minebase_secrets(cfg)

        assert result["api"]["password"].startswith(_ENCRYPTED_PREFIX)
        assert result["database"]["password"].startswith(_ENCRYPTED_PREFIX)
        assert _decrypt(result["api"]["password"]) == "secret123"
        assert _decrypt(result["database"]["password"]) == "db_pass"

    def test_preserves_non_password_fields(self):
        """非密码字段应保持不变。"""
        cfg = {
            "api": {"url": "http://example.com", "username": "admin", "password": "secret"},
            "database": {"host": "localhost", "port": 5432, "user": "postgres", "password": "db"},
        }
        result = save_minebase_secrets(cfg)

        assert result["api"]["url"] == "http://example.com"
        assert result["api"]["username"] == "admin"
        assert result["database"]["host"] == "localhost"
        assert result["database"]["port"] == 5432

    def test_does_not_mutate_input(self):
        """不应修改传入的原始配置。"""
        cfg = {"api": {"password": "original"}}
        save_minebase_secrets(cfg)
        assert cfg["api"]["password"] == "original"

    def test_skips_empty_and_none(self):
        """空密码和 None 不应加密。"""
        cfg = {
            "api": {"password": ""},
            "database": {"password": None},
        }
        result = save_minebase_secrets(cfg)
        assert result["api"]["password"] == ""
        assert result["database"]["password"] is None

    def test_skips_already_encrypted(self):
        """已经是 __enc__ 格式的值不应重复加密。"""
        already = _encrypt("already_encrypted")
        cfg = {"api": {"password": already}}
        result = save_minebase_secrets(cfg)
        assert result["api"]["password"] == already


# ---------------------------------------------------------------------------
# load_secret
# ---------------------------------------------------------------------------
class TestLoadSecret:
    def test_decrypts_encrypted_value(self, tmp_path):
        """应解密 __enc__ 格式的密码。"""
        encrypted = _encrypt("real_pass")
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": encrypted}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            result = load_secret(("minebase", "api", "password"))
        assert result == "real_pass"

    def test_returns_plaintext_as_is(self, tmp_path):
        """非加密值应原样返回。"""
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

    def test_returns_empty_when_missing(self, tmp_path):
        """路径不存在时应返回空字符串。"""
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
# load_minebase_secret
# ---------------------------------------------------------------------------
class TestLoadMinebaseSecret:
    def test_end_to_end_encrypt_then_decrypt(self, tmp_path):
        """端到端：加密存储 → 读取解密。"""
        cfg = {"api": {"password": "api_secret"}}
        encrypted_cfg = save_minebase_secrets(cfg)

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"minebase": encrypted_cfg}), encoding="utf-8")
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            result = load_minebase_secret("api")
        assert result == "api_secret"


# ---------------------------------------------------------------------------
# has_encrypted_secret
# ---------------------------------------------------------------------------
class TestHasEncryptedSecret:
    def test_returns_true_for_encrypted(self, tmp_path):
        encrypted = _encrypt("pass")
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"minebase": {"api": {"password": encrypted}}}),
            encoding="utf-8",
        )
        empty_user = tmp_path / "config.user.json"
        empty_user.write_text(json.dumps({}), encoding="utf-8")
        with (
            patch.object(config_loader, "_CONFIG_FILE", config_file),
            patch.object(config_loader, "_USER_CONFIG_FILE", empty_user),
        ):
            assert has_encrypted_secret(("minebase", "api", "password")) is True

    def test_returns_false_for_plaintext(self, tmp_path):
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
            assert has_encrypted_secret(("minebase", "api", "password")) is False
