"""安全凭证存储 — 使用系统 Keychain 保存数据库和 API 密码。

替代在 config.user.json 中明文存储 password 字段的方式。
"""

from __future__ import annotations

import logging
import keyring

from . import config_loader
from .config_loader import _get_nested, _set_nested

logger = logging.getLogger(__name__)

# sentinel: 配置文件中出现此值表示实际密码已存入 Keychain
_KEYRING_SENTINEL = "__keyring__"

# minebase 配置中需要加密存储的完整路径（相对于配置根节点）
_SECRET_PATHS: list[tuple[str, ...]] = [
    ("minebase", "api", "password"),
    ("minebase", "database", "password"),
]

_KEYRING_SERVICE = "MiningProcessor"


def _keyring_key(path: tuple[str, ...]) -> str:
    """将配置路径转为 keyring 账号名，如 'minebase.api.password'。"""
    return ".".join(path)


def store_secret(path: tuple[str, ...], value: str) -> None:
    """将敏感值存入 Keychain，并在 config.user.json 中标记为 sentinel。"""
    key = _keyring_key(path)
    keyring.set_password(_KEYRING_SERVICE, key, value)
    # path 形如 ("minebase", "api", "password")，相对于 minebase 节点的子路径为 path[1:]
    user_file = config_loader._load_json(config_loader._USER_CONFIG_FILE)
    minebase_cfg = user_file.get("minebase", {})
    _set_nested(minebase_cfg, path[1:], _KEYRING_SENTINEL)
    config_loader._save_json(config_loader._USER_CONFIG_FILE, {**user_file, "minebase": minebase_cfg})
    config_loader._invalidate_config_cache()
    logger.info("密钥已存入系统 Keychain: %s", key)


def load_secret(path: tuple[str, ...]) -> str:
    """读取密钥：若配置中为 sentinel 则从 Keychain 取，否则直接返回原值。"""
    config = config_loader.load_config()
    val = _get_nested(config, path)
    if val == _KEYRING_SENTINEL:
        key = _keyring_key(path)
        secret = keyring.get_password(_KEYRING_SERVICE, key)
        if secret is None:
            logger.warning("Keychain 中未找到 %s，请重新设置密码", key)
            return ""
        return secret
    return val or ""


def has_keyring_secret(path: tuple[str, ...]) -> bool:
    """判断该路径的密码是否已存入 Keychain。"""
    config = config_loader.load_config()
    return _get_nested(config, path) == _KEYRING_SENTINEL


def migrate_passwords_to_keyring() -> None:
    """一次性迁移：将 config.user.json 中的明文密码转入 Keychain。

    幂等 — 已标记为 sentinel 的字段不会重复迁移。
    """
    user_file = config_loader._load_json(config_loader._USER_CONFIG_FILE)
    minebase_cfg = user_file.get("minebase", {})
    changed = False

    for path in _SECRET_PATHS:
        val = _get_nested(minebase_cfg, path[1:])
        if val and val != _KEYRING_SENTINEL:
            key = _keyring_key(path)
            keyring.set_password(_KEYRING_SERVICE, key, val)
            _set_nested(minebase_cfg, path[1:], _KEYRING_SENTINEL)
            logger.info("已迁移密码到 Keychain: %s", key)
            changed = True

    if changed:
        config_loader._save_json(config_loader._USER_CONFIG_FILE, {**user_file, "minebase": minebase_cfg})
        config_loader._invalidate_config_cache()
