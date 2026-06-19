"""安全凭证存储 — 使用系统 Keychain 保存数据库和 API 密码。

替代在 config.user.json 中明文存储 password 字段的方式。
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import keyring

from . import config_loader
from .config_loader import _get_nested, _set_nested

logger = logging.getLogger(__name__)

# sentinel: 配置文件中出现此值表示实际密码已存入 Keychain
_KEYRING_SENTINEL = "__keyring__"

# 前端曾使用不同的 sentinel 值，兼容旧配置文件
_LEGACY_KEYRING_SENTINEL = "__KEYRING_SENTINEL__"

# minebase 配置中需要加密存储的完整路径（相对于配置根节点）
_SECRET_PATHS: list[tuple[str, ...]] = [
    ("minebase", "api", "password"),
    ("minebase", "database", "password"),
]

_KEYRING_SERVICE = "MiningProcessor"


def _keyring_key(path: tuple[str, ...]) -> str:
    """将配置路径转为 keyring 账号名，如 'minebase.api.password'。"""
    return ".".join(path)


def _is_secret_value(val: Any) -> bool:
    """判断一个值是否为真实的密码（非空、非 sentinel）。"""
    return bool(val) and val not in (_KEYRING_SENTINEL, _LEGACY_KEYRING_SENTINEL)


# ---------------------------------------------------------------------------
# 单路径读写（保持向后兼容）
# ---------------------------------------------------------------------------

def store_secret(path: tuple[str, ...], value: str) -> bool:
    """将单个敏感值存入 Keychain。

    注意：本函数**不**更新 config.user.json 中的 sentinel 标记，
    调用方（如 save_minebase_secrets）应自行处理配置文件更新，
    以避免多次重复读写磁盘。

    Returns:
        True  — Keychain 写入成功。
        False — Keychain 写入失败。
    """
    key = _keyring_key(path)
    try:
        keyring.set_password(_KEYRING_SERVICE, key, value)
    except Exception:
        logger.exception("Keychain 写入失败: %s，密码将以明文保留在配置文件中", key)
        return False
    logger.info("密钥已存入系统 Keychain: %s", key)
    return True


def load_secret(path: tuple[str, ...]) -> str:
    """读取密钥：若配置中为 sentinel 则从 Keychain 取，否则直接返回原值。

    当 Keychain 查找失败时，回退到 config.user.json 的 user_config.minebase
    旧格式中读取明文密码（兼容迁移前的配置）。
    """
    config = config_loader.load_config()
    val = _get_nested(config, path)
    if val in (_KEYRING_SENTINEL, _LEGACY_KEYRING_SENTINEL):
        key = _keyring_key(path)
        secret = keyring.get_password(_KEYRING_SERVICE, key)
        if secret is None:
            # 回退：尝试从 user_config.minebase 旧格式读取明文
            fallback = _read_legacy_plaintext(path)
            if fallback:
                logger.info("Keychain 未找到 %s，使用旧配置中的明文密码", key)
                return fallback
            logger.warning("Keychain 中未找到 %s，请重新设置密码", key)
            return ""
        return secret
    return val or ""


def _read_legacy_plaintext(path: tuple[str, ...]) -> str:
    """从 config.user.json 的 user_config.minebase 旧格式读取明文密码。"""
    user_file = config_loader._load_json(config_loader._USER_CONFIG_FILE)
    legacy_cfg = user_file.get("user_config", {}).get("minebase", {})
    val = _get_nested(legacy_cfg, path[1:])  # path[1:] = ("database", "password")
    return val if val and val not in (_KEYRING_SENTINEL, _LEGACY_KEYRING_SENTINEL) else ""


# ---------------------------------------------------------------------------
# 批量读写（供 config_loader 委托使用，避免 N+1 文件 I/O）
# ---------------------------------------------------------------------------

def save_minebase_secrets(
    cfg: dict[str, Any],
    secret_paths: list[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """将配置中的密码存入 Keychain，返回清理后的配置副本。

    遍历所有 secret_paths，对每个真实密码：
    - 写入 Keychain → 替换为 sentinel
    - 写入失败 → 保留明文

    调用方负责将返回的配置写入 config.user.json。
    """
    paths = secret_paths if secret_paths is not None else _SECRET_PATHS
    cfg_clean = copy.deepcopy(cfg)

    for path in paths:
        val = _get_nested(cfg_clean, path[1:])
        if not _is_secret_value(val):
            continue
        if store_secret(path, val):
            _set_nested(cfg_clean, path[1:], _KEYRING_SENTINEL)
        # else: Keychain 写入失败，保留明文密码

    return cfg_clean


def load_minebase_secret(section: str) -> str:
    """读取指定 minebase 子模块的密码（api 或 database）。

    用于 config_loader 的 get_minebase_*_config 函数。
    """
    return load_secret(("minebase", section, "password"))


# ---------------------------------------------------------------------------
# 迁移
# ---------------------------------------------------------------------------

def migrate_passwords_to_keyring() -> None:
    """一次性迁移：将 config.user.json 中的明文密码转入 Keychain。

    同时扫描顶层 minebase 和旧格式 user_config.minebase 两个位置。
    幂等 — 已标记为 sentinel 的字段不会重复迁移。
    Keychain 写入失败时保留明文，不中断启动。

    迁移成功后，自动清理 user_config.minebase 旧格式中的密码字段，
    避免明文残留在配置文件中。
    """
    user_file = config_loader._load_json(config_loader._USER_CONFIG_FILE)
    minebase_cfg = user_file.get("minebase", {})
    legacy_cfg = user_file.get("user_config", {}).get("minebase", {})
    changed = False
    legacy_changed = False

    for path in _SECRET_PATHS:
        sub_path = path[1:]  # ("api", "password") 或 ("database", "password")
        val = _get_nested(minebase_cfg, sub_path)
        # 顶层无明文时，从 user_config.minebase 旧格式取
        if not val or val == _KEYRING_SENTINEL:
            val = _get_nested(legacy_cfg, sub_path)
        if not _is_secret_value(val):
            continue
        key = _keyring_key(path)
        try:
            keyring.set_password(_KEYRING_SERVICE, key, val)
        except Exception:
            logger.exception("Keychain 迁移失败: %s，保留明文密码", key)
            continue
        # 顶层标记为 sentinel
        _set_nested(minebase_cfg, sub_path, _KEYRING_SENTINEL)
        # 清理旧格式中的明文密码
        if _get_nested(legacy_cfg, sub_path):
            _set_nested(legacy_cfg, sub_path, _KEYRING_SENTINEL)
            legacy_changed = True
        logger.info("已迁移密码到 Keychain: %s", key)
        changed = True

    if changed:
        # 更新顶层 minebase
        user_file["minebase"] = minebase_cfg
        # 更新旧格式（标记为 sentinel 或删除整个空段落）
        if legacy_changed:
            user_cfg = user_file.get("user_config", {})
            if isinstance(user_cfg, dict):
                has_remaining = any(
                    _is_secret_value(_get_nested(legacy_cfg, p[1:]))
                    for p in _SECRET_PATHS
                )
                if not has_remaining:
                    # 所有密码已迁移，移除整个 minebase 段落
                    user_cfg.pop("minebase", None)
                else:
                    user_cfg["minebase"] = legacy_cfg
                user_file["user_config"] = user_cfg
        config_loader._save_json(config_loader._USER_CONFIG_FILE, user_file)
        config_loader._invalidate_config_cache()


def has_keyring_secret(path: tuple[str, ...]) -> bool:
    """判断该路径的密码是否已存入 Keychain。"""
    config = config_loader.load_config()
    return _get_nested(config, path) == _KEYRING_SENTINEL
