"""
配置加载模块

配置分为两个文件：
- config.json        : 系统默认配置（提交到 Git）
- config.user.json   : 用户覆盖配置（gitignore，含敏感信息如数据库凭据）

load_config() 合并两者返回（user 覆盖 default），save 时按目标分别写入。
"""
import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class _LedgerEncoder(json.JSONEncoder):
    """处理 pandas Timestamp 等不可直接序列化的类型。"""
    def default(self, obj):
        import datetime
        import numpy as np
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat() if not pd.isna(obj) else None
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj) if not np.isnan(obj) else None
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if pd.isna(obj):
            return None
        return super().default(obj)


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

_CONFIG_FILE = Path(__file__).parent.parent / "config.json"
_USER_CONFIG_FILE = Path(__file__).parent.parent / "config.user.json"

_USER_CONFIG_SECTION = "user_config"


# ---------------------------------------------------------------------------
# 默认值（当 config.json 读取失败时的 fallback）
# ---------------------------------------------------------------------------

DEFAULT_LOAD_MAP_NEW = {
    "NTE240": 85, "EH4000": 85, "LIEBHERR T264": 80,
    "HITACHI 4000": 85, "MT4400": 85, "MT4400AC": 85,
    "TR100": 35, "TEREX 60": 22, "Terex 60": 22, "TR60": 22,
    "XDM100": 35, "XDE120": 43, "XDEM120": 43,
    "XDE130": 43, "XDM130": 43, "T-264": 80,
    "SANY SET150S": 52, "CAT773": 20,
}

DEFAULT_LOAD_MAP_OLD = {
    "NTE240": 80, "LIEBHERR T264": 80, "EH4000": 80,
    "HITACHI 4000": 80, "MT4400": 80, "TR100": 32,
    "TEREX 60": 20, "Terex 60": 20, "TR60": 20, "MT-10": 20,
    "XDM100": 32, "XDE120": 40, "XDEM120": 40,
    "XDE130": 45, "XDM130": 45, "T-264": 80,
    "SANY SET150S": 52, "CAT773": 20, "KOMATSU 785": 37,
    "MT 4400": 80, "CAT 773D": 20,
}

DEFAULT_FILE_KEYWORDS: dict[str, list[str]] = {
    "fuel": ["Fuel report "],
    "electrical": ["Цахилгааны хэлтэс"],
    "production": ["白班", "夜班"],
    "worktime": ["工作效率表"],
}

DEFAULT_WORKTIME_HEADER_MAPPING: dict = {
    "mode": "position",
    "fuzzy": False,
    "entries": [
        {"index": 1, "original": "", "new": "日期"},
        {"index": 2, "original": "", "new": "班次"},
        {"index": 3, "original": "", "new": "序号"},
        {"index": 4, "original": "", "new": "设备名称"},
        {"index": 5, "original": "", "new": "公司"},
        {"index": 6, "original": "", "new": "应运行分钟"},
        {"index": 7, "original": "", "new": "应运行小时数"},
        {"index": 8, "original": "", "new": "停车/换班"},
        {"index": 9, "original": "", "new": "转移"},
        {"index": 10, "original": "", "new": "挖机场地推土/清理墙壁"},
        {"index": 11, "original": "", "new": "等待装货"},
        {"index": 12, "original": "", "new": "爆破"},
        {"index": 13, "original": "", "new": "就餐/休息时间"},
        {"index": 14, "original": "", "new": "柴油"},
        {"index": 15, "original": "", "new": "计划维修/润滑"},
        {"index": 16, "original": "", "new": "未计划/故障"},
        {"index": 17, "original": "", "new": "待命"},
        {"index": 18, "original": "", "new": "因天气：大风暴，雨，雪"},
        {"index": 19, "original": "", "new": "扬尘：洒水车不足"},
        {"index": 20, "original": "", "new": "排队/装水"},
        {"index": 21, "original": "", "new": "总产量生产运行分钟"},
        {"index": 22, "original": "", "new": "因电力原因停车/计划"},
        {"index": 23, "original": "", "new": "因电力原因停车/未计划"},
        {"index": 24, "original": "", "new": "总产量生产运行小时"},
        {"index": 25, "original": "", "new": "注释"},
    ],
}

# M3: 线程安全锁，保护 _runtime_config 的读写
_runtime_lock = threading.Lock()
_runtime_config: dict[str, Any] | None = None

# M1: 基于文件 mtime 的配置缓存，避免 GUI 启动期间重复读盘
_config_cache: dict[str, Any] | None = None
_config_cache_mtime: tuple[float, float] = (0.0, 0.0)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """深合并：override 中的键覆盖 base，dict 值递归合并。"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def _get_nested(d: dict[str, Any], path: tuple[str, ...]) -> Any:
    """按路径取值，缺 key 时返回 None。"""
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _set_nested(d: dict[str, Any], path: tuple[str, str, str], value: Any) -> None:
    """按路径设置值，自动创建中间 dict。"""
    cur = d
    for k in path[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[path[-1]] = value


def _load_json(path: Path) -> dict[str, Any]:
    """读取 JSON 文件，不存在或损坏时返回空 dict。"""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("读取配置文件失败 (%s): %s", path.name, e)
        return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """原子写入 JSON 文件（先写临时文件再 rename，防止崩溃导致文件损坏）。"""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# 路径访问（供 GUI 测试 monkeypatch 用）
# ---------------------------------------------------------------------------

def get_config_file_path() -> Path:
    """获取系统默认配置文件路径"""
    return _CONFIG_FILE


def get_user_config_file_path() -> Path:
    """获取用户配置文件路径"""
    return _USER_CONFIG_FILE


# ---------------------------------------------------------------------------
# 加载与保存
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    """加载合并后的配置（系统默认 + 用户覆盖）。

    先读 config.json，再用 config.user.json 深合并覆盖。
    任何一侧文件不存在都不报错，返回另一侧的内容。
    使用基于文件 mtime 的缓存，避免重复读盘 (M1)。
    """
    global _config_cache, _config_cache_mtime

    mt1 = _CONFIG_FILE.stat().st_mtime if _CONFIG_FILE.exists() else 0.0
    mt2 = _USER_CONFIG_FILE.stat().st_mtime if _USER_CONFIG_FILE.exists() else 0.0

    if _config_cache is not None and (mt1, mt2) == _config_cache_mtime:
        return _config_cache

    base = _load_json(_CONFIG_FILE)
    user = _load_json(_USER_CONFIG_FILE)
    result = _deep_merge(base, user) if user else base

    _config_cache = result
    _config_cache_mtime = (mt1, mt2)
    return result


def _invalidate_config_cache() -> None:
    """清除配置缓存，在写入配置文件后调用 (M1)。"""
    global _config_cache, _config_cache_mtime
    _config_cache = None
    _config_cache_mtime = (0.0, 0.0)


def save_config(config: dict[str, Any]) -> None:
    """保存系统默认配置到 config.json（不含用户敏感数据）。"""
    _save_json(_CONFIG_FILE, config)
    _invalidate_config_cache()


# ---------------------------------------------------------------------------
# 设备装载量
# ---------------------------------------------------------------------------

def get_default_load_map(version: str = "new") -> dict[str, int]:
    """获取默认设备装载量映射（当 config.json 读取失败时的 fallback）"""
    return dict(DEFAULT_LOAD_MAP_OLD if version == "old" else DEFAULT_LOAD_MAP_NEW)


def get_device_load_map(version: str = "new") -> dict[str, int]:
    """
    获取设备装载量映射
    version: "new" (默认) 或 "old"
    """
    with _runtime_lock:  # M3
        config = _runtime_config if _runtime_config is not None else load_config()
    key = f"device_load_map_{version}" if version != "new" else "device_load_map"
    return config.get(key, {})


def apply_device_load_map(device_load_map: dict[str, int]) -> dict[str, int]:
    """仅在当前运行时应用设备装载量映射，不持久化到文件"""
    global _runtime_config
    with _runtime_lock:  # M3
        config = load_config()
        config["device_load_map"] = dict(device_load_map)
        _runtime_config = config
        return _runtime_config["device_load_map"]


def update_device_load_map(updates: dict[str, int]) -> dict[str, int]:
    """更新设备装载量映射（写入 config.json）"""
    global _runtime_config
    config = _load_json(_CONFIG_FILE)
    if "device_load_map" not in config:
        config["device_load_map"] = {}
    config["device_load_map"].update(updates)
    _save_json(_CONFIG_FILE, config)
    _invalidate_config_cache()
    with _runtime_lock:  # M2: 清除运行时缓存，确保下次读取使用最新值
        _runtime_config = None
    return config["device_load_map"]


# ---------------------------------------------------------------------------
# 班次 / 年月
# ---------------------------------------------------------------------------


def get_default_shift() -> str:
    """Get default shift value when shift column is missing (e.g. "Night")"""
    config = load_config()
    return config.get("default_shift", "Night")


def set_default_shift(shift: str) -> None:
    """Set default shift value when shift column is missing"""
    config = _load_json(_CONFIG_FILE)
    config["default_shift"] = shift
    _save_json(_CONFIG_FILE, config)
    _invalidate_config_cache()


def get_default_year() -> int:
    """获取默认年份"""
    config = load_config()
    return config.get("default_year", 2025)


def get_default_month() -> int:
    """获取默认月份"""
    config = load_config()
    return config.get("default_month", 1)


# ---------------------------------------------------------------------------
# 用户配置读写（写入 config.user.json）
# ---------------------------------------------------------------------------

def get_user_config(section: str | None = None, default: Any = None) -> Any:
    """读取用户自定义配置。

    当 `section` 为 None 时返回完整的 user_config 字典；
    否则返回对应小节；找不到时返回 `default`。
    """
    config = load_config()
    user_config = config.get(_USER_CONFIG_SECTION, {})
    if section is None:
        return user_config
    return user_config.get(section, default)


def save_user_config(user_config: dict[str, Any]) -> None:
    """整体替换并持久化 user_config 段落（写入 config.user.json）。"""
    user_file = _load_json(_USER_CONFIG_FILE)
    user_file[_USER_CONFIG_SECTION] = dict(user_config)
    _save_json(_USER_CONFIG_FILE, user_file)
    _invalidate_config_cache()


def update_user_config(updates: dict[str, Any]) -> dict[str, Any]:
    """合并更新 user_config（只覆盖传入的 key，其余保留，写入 config.user.json）。"""
    user_file = _load_json(_USER_CONFIG_FILE)
    current = user_file.get(_USER_CONFIG_SECTION, {})
    if not isinstance(current, dict):
        current = {}
    current.update(updates)
    user_file[_USER_CONFIG_SECTION] = current
    _save_json(_USER_CONFIG_FILE, user_file)
    _invalidate_config_cache()
    return current


def reset_user_config(section: str | None = None) -> None:
    """重置用户配置。

    - 当 `section` 为 None 时清空 config.user.json 中的 user_config。
    - 当指定了某个小节时，仅清空该小节。
    """
    user_file = _load_json(_USER_CONFIG_FILE)
    if section is None:
        user_file[_USER_CONFIG_SECTION] = {}
    else:
        user_config = user_file.get(_USER_CONFIG_SECTION, {})
        if not isinstance(user_config, dict):
            user_config = {}
        user_config.pop(section, None)
        user_file[_USER_CONFIG_SECTION] = user_config
    _save_json(_USER_CONFIG_FILE, user_file)
    _invalidate_config_cache()



# ---------------------------------------------------------------------------
# 文件关键字
# ---------------------------------------------------------------------------

def get_file_keywords() -> dict[str, list[str]]:
    """获取批量处理的文件关键字配置，未配置时返回默认值。"""
    user_cfg = get_user_config("file_keywords", None)
    if user_cfg and isinstance(user_cfg, dict):
        merged = dict(DEFAULT_FILE_KEYWORDS)
        for k, v in user_cfg.items():
            if isinstance(v, list):
                merged[k] = v
        return merged
    return dict(DEFAULT_FILE_KEYWORDS)


# ---------------------------------------------------------------------------
# 工作效率表头映射
# ---------------------------------------------------------------------------

def get_worktime_header_mapping() -> dict:
    """获取工作效率表头映射配置。

    返回格式::

        {
            "mode": "position" | "name",
            "fuzzy": False,
            "entries": [
                {"index": 0, "original": "原始列名", "new": "新列名"},
                ...
            ]
        }
    """
    saved = get_user_config("worktime_header_mapping", None)
    if saved and isinstance(saved, dict):
        merged = dict(DEFAULT_WORKTIME_HEADER_MAPPING)
        merged.update({k: v for k, v in saved.items() if k in DEFAULT_WORKTIME_HEADER_MAPPING})
        if not isinstance(merged.get("entries"), list):
            merged["entries"] = []
        return merged
    return dict(DEFAULT_WORKTIME_HEADER_MAPPING)


def save_worktime_header_mapping(mapping: dict) -> None:
    """持久化工作效率表头映射配置。"""
    update_user_config({"worktime_header_mapping": mapping})



# ---------------------------------------------------------------------------
# 台账缓存（JSON 格式持久化）
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data"
_EQUIPMENT_LEDGER_CACHE = _DATA_DIR / "equipment_ledger_cache.json"
_OIL_LEDGER_CACHE = _DATA_DIR / "oil_ledger_cache.json"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_equipment_ledger_cache(records: list[dict]) -> None:
    """将设备台账记录缓存为 JSON 文件。"""
    _ensure_data_dir()
    with open(_EQUIPMENT_LEDGER_CACHE, "w", encoding="utf-8") as f:
        json.dump({"data": records}, f, ensure_ascii=False, indent=2, cls=_LedgerEncoder)


def load_equipment_ledger_cache() -> list[dict] | None:
    """加载设备台账缓存，不存在时返回 None。"""
    if not _EQUIPMENT_LEDGER_CACHE.exists():
        return None
    try:
        with open(_EQUIPMENT_LEDGER_CACHE, "r", encoding="utf-8") as f:
            return json.load(f).get("data")
    except Exception as e:
        logger.warning("加载设备台账缓存失败: %s", e)
        return None


def clear_equipment_ledger_cache() -> None:
    """删除设备台账缓存文件。"""
    if _EQUIPMENT_LEDGER_CACHE.exists():
        _EQUIPMENT_LEDGER_CACHE.unlink()


def has_equipment_ledger_cache() -> bool:
    return _EQUIPMENT_LEDGER_CACHE.exists()


def save_oil_ledger_cache(records: list[dict]) -> None:
    """将油品台账记录缓存为 JSON 文件。"""
    _ensure_data_dir()
    with open(_OIL_LEDGER_CACHE, "w", encoding="utf-8") as f:
        json.dump({"data": records}, f, ensure_ascii=False, indent=2, cls=_LedgerEncoder)


def load_oil_ledger_cache() -> list[dict] | None:
    """加载油品台账缓存，不存在时返回 None。"""
    if not _OIL_LEDGER_CACHE.exists():
        return None
    try:
        with open(_OIL_LEDGER_CACHE, "r", encoding="utf-8") as f:
            return json.load(f).get("data")
    except Exception as e:
        logger.warning("加载油品台账缓存失败: %s", e)
        return None


def clear_oil_ledger_cache() -> None:
    """删除油品台账缓存文件。"""
    if _OIL_LEDGER_CACHE.exists():
        _OIL_LEDGER_CACHE.unlink()


def has_oil_ledger_cache() -> bool:
    return _OIL_LEDGER_CACHE.exists()


# ---------------------------------------------------------------------------
# MineBase 同步配置
# ---------------------------------------------------------------------------

_MINEBASE_CONFIG_FALLBACK: dict[str, Any] = {
    "mode": "api",
    "api": {"url": "http://localhost:3000", "username": "", "password": ""},
    "database": {"host": "127.0.0.1", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
}


def get_minebase_config() -> dict[str, Any]:
    """获取 MineBase 同步配置（config.json 默认值 + config.user.json 覆盖）。"""
    config = load_config()
    return _deep_merge(_MINEBASE_CONFIG_FALLBACK, config.get("minebase", {}))


def get_minebase_config_default() -> dict[str, Any]:
    """获取 MineBase 同步的默认配置（仅 config.json，不含用户覆盖）。"""
    config = _load_json(_CONFIG_FILE)
    return dict(config.get("minebase", {}))


def get_minebase_mode() -> str:
    """获取 MineBase 同步模式：'api' 或 'database'。"""
    return get_minebase_config().get("mode", "api")


def get_minebase_api_config() -> dict[str, Any]:
    """获取 MineBase API 模式配置（密码从 Keychain 解密）。"""
    from .secret_store import load_minebase_secret

    cfg = get_minebase_config().get("api", {})
    if "password" in cfg:
        cfg = {**cfg, "password": load_minebase_secret("api")}
    return cfg


def get_minebase_db_config() -> dict[str, Any]:
    """获取 MineBase 数据库直连模式配置（密码从 Keychain 解密）。"""
    from .secret_store import load_minebase_secret

    cfg = get_minebase_config().get("database", {})
    if "password" in cfg:
        cfg = {**cfg, "password": load_minebase_secret("database")}
    return cfg


def save_minebase_config(minebase_cfg: dict[str, Any]) -> None:
    """保存 MineBase 配置到 config.user.json（密码自动存入 Keychain）。"""
    from .secret_store import save_minebase_secrets

    cfg_to_save = save_minebase_secrets(minebase_cfg)
    # 写入 config.user.json 顶层 minebase（与 load_config 合并逻辑一致）
    user_file = _load_json(_USER_CONFIG_FILE)
    user_file["minebase"] = cfg_to_save
    _save_json(_USER_CONFIG_FILE, user_file)
    _invalidate_config_cache()


# ---------------------------------------------------------------------------
# MineBase 列映射
# ---------------------------------------------------------------------------

# 用户自定义映射的独立文件路径（不在 config.user.json 中，方便单独管理）
_MINEBASE_MAPPING_FILE = Path(__file__).parent.parent / "minebase_column_mapping.json"


def get_minebase_column_mapping() -> dict[str, dict[str, str]]:
    """获取 MineBase 列映射配置。

    优先读取 minebase_column_mapping.json（用户自定义），
    不存在时回退到 config.json 中的默认值。
    """
    if _MINEBASE_MAPPING_FILE.exists():
        try:
            with open(_MINEBASE_MAPPING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("读取 MineBase 列映射文件失败，回退到默认值: %s", e)
    # 回退到 config.json 中的默认值
    config = _load_json(_CONFIG_FILE)
    return dict(config.get("minebase_column_mapping", {}))


def save_minebase_column_mapping(mapping: dict[str, dict[str, str]]) -> None:
    """保存用户自定义列映射到独立 JSON 文件。"""
    _save_json(_MINEBASE_MAPPING_FILE, mapping)


def reset_minebase_column_mapping() -> None:
    """删除用户自定义映射文件，恢复为 config.json 中的默认值。"""
    if _MINEBASE_MAPPING_FILE.exists():
        _MINEBASE_MAPPING_FILE.unlink()
