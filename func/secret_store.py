"""安全凭证存储 — 使用 Fernet 对称加密保护配置文件中的密码。

密码加密后以 __enc__ 前缀存储在 config.user.json 中，
运行时自动解密，替代明文存储和系统 Keychain 方案。
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from . import config_loader
from .config_loader import _get_nested, _set_nested

logger = logging.getLogger(__name__)

# 加密值前缀，用于识别配置中的加密字段
_ENCRYPTED_PREFIX = "__enc__"

# minebase 配置中需要加密存储的完整路径（相对于配置根节点）
_SECRET_PATHS: list[tuple[str, ...]] = [
    ("minebase", "api", "password"),
    ("minebase", "database", "password"),
]

# 固定口令和盐（混淆用途，防止配置文件被直接读取）
_PASSPHRASE = b"MiningProcessor-2024-secret-store"
_SALT = b"mp-config-salt-v1"

# 模块级缓存
_fernet: Fernet | None = None


def _derive_key() -> Fernet:
    """从固定口令+盐派生 Fernet key（模块级缓存）。"""
    global _fernet
    if _fernet is None:
        kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=32,
            salt=_SALT,
            iterations=480_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(_PASSPHRASE))
        _fernet = Fernet(key)
    return _fernet


def _encrypt(value: str) -> str:
    """加密字符串，返回 __enc__<token>。空值不加密。"""
    if not value:
        return ""
    token = _derive_key().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{token}"


def _decrypt(value: str) -> str:
    """解密 __enc__ 前缀的值。非加密值原样返回。"""
    if not value or not value.startswith(_ENCRYPTED_PREFIX):
        return value or ""
    token = value[len(_ENCRYPTED_PREFIX):]
    return _derive_key().decrypt(token.encode("ascii")).decode("utf-8")


# ---------------------------------------------------------------------------
# 公有接口（供 config_loader 和 GUI 使用）
# ---------------------------------------------------------------------------

def save_minebase_secrets(
    cfg: dict[str, Any],
    secret_paths: list[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """将配置中的密码加密，返回新配置副本。

    遍历所有 secret_paths，对每个明文密码调用 _encrypt。
    已加密（__enc__ 前缀）和空值跳过。

    调用方负责将返回的配置写入 config.user.json。
    """
    paths = secret_paths if secret_paths is not None else _SECRET_PATHS
    cfg_clean = copy.deepcopy(cfg)

    for path in paths:
        val = _get_nested(cfg_clean, path[1:])
        if val and not val.startswith(_ENCRYPTED_PREFIX):
            _set_nested(cfg_clean, path[1:], _encrypt(val))

    return cfg_clean


def load_secret(path: tuple[str, ...]) -> str:
    """读取密钥：若配置中为 __enc__ 格式则解密，否则直接返回原值。"""
    config = config_loader.load_config()
    val = _get_nested(config, path)
    return _decrypt(val)


def load_minebase_secret(section: str) -> str:
    """读取指定 minebase 子模块的密码（api 或 database）。"""
    return load_secret(("minebase", section, "password"))


def has_encrypted_secret(path: tuple[str, ...]) -> bool:
    """判断该路径的密码是否已加密存储。"""
    config = config_loader.load_config()
    val = _get_nested(config, path)
    return bool(val) and val.startswith(_ENCRYPTED_PREFIX)
