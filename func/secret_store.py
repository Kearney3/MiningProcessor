"""安全凭证存储 — 使用 Fernet 对称加密保护配置文件中的密码。

密码加密后以 __enc__ 前缀存储在 config.user.json 中，
运行时自动解密，替代明文存储和系统 Keychain 方案。

Security model
--------------
Encryption keys are derived via PBKDF2-HMAC-SHA256 (480 000 iterations)
from a passphrase and a fixed salt.

Key resolution priority (highest to lowest):
1. ``MP_MASTER_KEY`` environment variable — operator-controlled, portable
   across machines.  Best for production.
2. **Machine UUID** — derived from the host's hardware UUID (macOS) or
   machine-id (Linux) or MAC address hash (fallback).  Config is
   automatically tied to the local machine: encrypted files from other
   machines cannot be decrypted here, and vice-versa.
3. **Legacy hardcoded passphrase** — kept only for backward compatibility
   with configs encrypted before the machine-ID feature was introduced.
   Emits a WARNING-level log message.

The salt (``_SALT``) is intentionally kept as a constant.  Salts do not
need to be secret; they only need to be consistent so that the same
passphrase always derives the same key.

To migrate existing secrets from the legacy key to a new
``MP_MASTER_KEY``, call :func:`migrate_legacy_encryption` after setting
the environment variable.
"""

from __future__ import annotations

import base64
import copy
import logging
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

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

# Legacy hardcoded passphrase — used ONLY when MP_MASTER_KEY is unset.
# Kept for backward compatibility so existing encrypted configs still
# decrypt without manual migration.
_LEGACY_PASSPHRASE = b"MiningProcessor-2024-secret-store"

# Salt for PBKDF2 key derivation.  Salts do not need to be secret;
# they ensure deterministic key derivation for a given passphrase.
_SALT = b"mp-config-salt-v1"

# Module-level Fernet cache (keyed implicitly by current passphrase).
_fernet: Fernet | None = None


def _get_machine_id() -> str:
    """Obtain a stable, machine-unique identifier.

    Resolution order:
    1. macOS — IOPlatformUUID from IORegistry
    2. Linux — /etc/machine-id (systemd/dbus)
    3. Fallback — SHA-256 hash of MAC address (uuid.getnode)

    Returns a hex string; raises RuntimeError only if the fallback also fails.
    """
    import hashlib
    import platform
    import subprocess

    system = platform.system()

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["ioreg", "-d2", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            logger.debug("Failed to read machine ID via IOPlatformUUID", exc_info=True)

    elif system == "Linux":
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(path, encoding="utf-8") as f:
                    mid = f.read().strip()
                    if mid:
                        return mid
            except Exception:
                logger.debug("Failed to read machine ID via %s", path, exc_info=True)

    elif system == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "csproduct", "get", "uuid"],
                capture_output=True, text=True, timeout=5,
            )
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            if len(lines) > 1:
                return lines[1]
        except Exception:
            logger.debug("Failed to read machine ID via wmic", exc_info=True)

    # Cross-platform fallback: hash the MAC address
    import uuid

    node = uuid.getnode()
    if node is not None and node != 0:
        digest = hashlib.sha256(f"mp-machine-{node:x}".encode()).hexdigest()
        return digest[:16]

    raise RuntimeError("Cannot determine a unique machine identifier")


def _get_passphrase() -> bytes:
    """Return the encryption passphrase.

    Priority:
    1. ``MP_MASTER_KEY`` environment variable.
    2. Machine UUID (auto-detected, no configuration needed).
    3. Legacy hardcoded passphrase (emits a warning).
    """
    env_key = os.environ.get("MP_MASTER_KEY")
    if env_key:
        return env_key.encode("utf-8")

    try:
        mid = _get_machine_id()
        return mid.encode("utf-8")
    except Exception:
        pass

    logger.warning(
        "MP_MASTER_KEY environment variable is not set and machine ID "
        "could not be determined; using legacy hardcoded passphrase. "
        "Set MP_MASTER_KEY to a strong secret for production use."
    )
    return _LEGACY_PASSPHRASE


def _build_fernet(passphrase: bytes) -> Fernet:
    """Derive a Fernet instance from *passphrase* + ``_SALT``."""
    kdf = PBKDF2HMAC(
        algorithm=SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase))
    return Fernet(key)


def _derive_key() -> Fernet:
    """Return the active Fernet instance (module-level cached).

    The passphrase is resolved via :func:`_get_passphrase`, which checks
    ``MP_MASTER_KEY`` before falling back to the legacy key.
    """
    global _fernet
    if _fernet is None:
        _fernet = _build_fernet(_get_passphrase())
    return _fernet


def _reset_fernet_cache() -> None:
    """Clear the cached Fernet instances.

    Useful in tests or after changing ``MP_MASTER_KEY`` at runtime.
    """
    global _fernet, _legacy_fernet
    _fernet = None
    _legacy_fernet = None


def _encrypt(value: str) -> str:
    """Encrypt *value*, returning ``__enc__<token>``.  Empty values pass through."""
    if not value:
        return ""
    token = _derive_key().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{token}"


_legacy_fernet: Fernet | None = None


def _decrypt(value: str) -> str:
    """Decrypt a ``__enc__``-prefixed value.  Non-encrypted values pass through.

    If decryption with the current key fails (e.g. config was encrypted with
    the legacy hardcoded key before machine-ID support was added), the legacy
    key is tried as a fallback.  A ``DEBUG`` log is emitted when fallback
    succeeds so that operators know a migration is advisable.
    """
    global _legacy_fernet

    if not value or not value.startswith(_ENCRYPTED_PREFIX):
        return value or ""
    token = value[len(_ENCRYPTED_PREFIX):]
    try:
        return _derive_key().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        pass
    # Fallback: try the legacy hardcoded key (pre-machine-ID configs)
    if _legacy_fernet is None:
        _legacy_fernet = _build_fernet(_LEGACY_PASSPHRASE)
    try:
        plaintext = _legacy_fernet.decrypt(token.encode("ascii")).decode("utf-8")
        logger.warning(
            "Password decrypted with legacy hardcoded key; consider setting "
            "MP_MASTER_KEY and re-saving MineBase config to upgrade encryption."
        )
        return plaintext
    except InvalidToken:
        pass
    raise InvalidToken("无法解密密码：当前密钥和遗留密钥均失败，请重新保存密码")


# ---------------------------------------------------------------------------
# Migration helper
# ---------------------------------------------------------------------------

def migrate_legacy_encryption(
    cfg: dict[str, Any],
    secret_paths: list[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Re-encrypt values from the legacy key to the current ``MP_MASTER_KEY``.

    This function is intended to be called **after** ``MP_MASTER_KEY`` has
    been set in the environment.  It:

    1. Decrypts each encrypted value using the legacy hardcoded key.
    2. Re-encrypts it with the new key derived from ``MP_MASTER_KEY``.
    3. Returns a **new** config dict (the original is not mutated).

    Values that are not encrypted (no ``__enc__`` prefix) or that fail
    legacy decryption are left unchanged.

    Parameters
    ----------
    cfg:
        Configuration dictionary whose secrets should be migrated.
    secret_paths:
        Paths to migrate.  Defaults to :data:`_SECRET_PATHS`.

    Returns
    -------
    dict
        A deep copy of *cfg* with migrated encrypted values.
    """
    if not os.environ.get("MP_MASTER_KEY"):
        logger.warning(
            "migrate_legacy_encryption called without MP_MASTER_KEY set; "
            "nothing to migrate to."
        )
        return copy.deepcopy(cfg)

    paths = secret_paths if secret_paths is not None else _SECRET_PATHS
    cfg_new = copy.deepcopy(cfg)

    # Build a Fernet instance for the legacy key (bypasses cache).
    legacy_fernet = _build_fernet(_LEGACY_PASSPHRASE)
    # Ensure the cached Fernet uses the *new* key.
    _reset_fernet_cache()
    new_fernet = _derive_key()

    migrated_count = 0
    for path in paths:
        val = _get_nested(cfg_new, path[1:])
        if not val or not val.startswith(_ENCRYPTED_PREFIX):
            continue

        token = val[len(_ENCRYPTED_PREFIX):]
        try:
            plaintext = legacy_fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            # Already encrypted with the new key, or corrupt — skip.
            logger.debug(
                "Skipping %s: not decryptable with legacy key (may already be migrated).",
                ".".join(path),
            )
            continue

        new_token = new_fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        _set_nested(cfg_new, path[1:], f"{_ENCRYPTED_PREFIX}{new_token}")
        migrated_count += 1
        logger.info("Migrated secret at %s to new key.", ".".join(path))

    logger.info(
        "Legacy encryption migration complete: %d value(s) re-encrypted.",
        migrated_count,
    )
    return cfg_new


# ---------------------------------------------------------------------------
# Public API (used by config_loader and GUI)
# ---------------------------------------------------------------------------

def save_minebase_secrets(
    cfg: dict[str, Any],
    secret_paths: list[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Encrypt passwords in *cfg* and return a new config copy.

    Iterates over *secret_paths*, encrypting each plaintext password via
    :func:`_encrypt`.  Values that are already encrypted (``__enc__``
    prefix) or empty are left unchanged.

    The caller is responsible for writing the returned config to
    ``config.user.json``.
    """
    paths = secret_paths if secret_paths is not None else _SECRET_PATHS
    cfg_clean = copy.deepcopy(cfg)

    for path in paths:
        val = _get_nested(cfg_clean, path[1:])
        if val and not val.startswith(_ENCRYPTED_PREFIX):
            _set_nested(cfg_clean, path[1:], _encrypt(val))

    return cfg_clean


def load_secret(path: tuple[str, ...]) -> str:
    """Read a secret: decrypt if ``__enc__``-prefixed, else return as-is."""
    config = config_loader.load_config()
    val = _get_nested(config, path)
    return _decrypt(val)


def load_minebase_secret(section: str) -> str:
    """Load the password for a minebase sub-module (api or database)."""
    return load_secret(("minebase", section, "password"))


def has_encrypted_secret(path: tuple[str, ...]) -> bool:
    """Check whether the value at *path* is stored in encrypted form."""
    config = config_loader.load_config()
    val = _get_nested(config, path)
    return bool(val) and val.startswith(_ENCRYPTED_PREFIX)
