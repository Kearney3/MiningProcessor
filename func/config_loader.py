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
import os
import sys
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

_BUNDLED_ROOT = Path(__file__).parent.parent

# PyInstaller 打包模式下，__file__ 指向临时解压目录（_MEIPASS），重启即丢失。
# 持久化目录优先级：环境变量 > sys.frozen 自动检测 > 开发模式（项目根目录）
if os.environ.get("MINING_PROCESSOR_DATA_DIR"):
    _persistent_root = Path(os.environ["MINING_PROCESSOR_DATA_DIR"])
elif getattr(sys, 'frozen', False):
    # Flet 或其他冻结构建，未显式设置环境变量时自动检测
    if sys.platform == "darwin":
        _persistent_root = Path.home() / "Library" / "Application Support" / "com.kearney.mining-processor"
    elif sys.platform == "win32":
        _persistent_root = Path(os.environ.get("APPDATA", str(Path.home()))) / "com.kearney.mining-processor"
    else:
        _persistent_root = Path.home() / ".local" / "share" / "com.kearney.mining-processor"
    _persistent_root.mkdir(parents=True, exist_ok=True)
else:
    _persistent_root = _BUNDLED_ROOT

# config.json: 打包默认值（只读 fallback）
_BUNDLED_CONFIG_FILE = _BUNDLED_ROOT / "config.json"
# 用户可修改的配置文件：持久化目录优先
_CONFIG_FILE = _persistent_root / "config.json"
_USER_CONFIG_FILE = _persistent_root / "config.user.json"

_USER_CONFIG_SECTION = "user_config"


def _init_persistent_defaults() -> None:
    """首次运行时，将打包的默认配置复制到持久化目录。"""
    if _persistent_root == _BUNDLED_ROOT:
        return  # 开发模式，无需复制
    if _BUNDLED_CONFIG_FILE.exists() and not _CONFIG_FILE.exists():
        import shutil
        shutil.copy2(_BUNDLED_CONFIG_FILE, _CONFIG_FILE)
        logger.info("已将默认配置复制到持久化目录: %s", _CONFIG_FILE)


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
    "maintenance": ["设备出勤统计表"],
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
_config_lock = threading.Lock()  # protects _config_cache and _config_cache_mtime
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

    冻结模式下合并顺序：打包默认 → 持久化 config.json → config.user.json。
    开发模式下合并顺序：config.json → config.user.json。
    使用基于文件 mtime 的缓存，避免重复读盘 (M1)。
    """
    global _config_cache, _config_cache_mtime

    mt1 = _CONFIG_FILE.stat().st_mtime if _CONFIG_FILE.exists() else 0.0
    mt2 = _USER_CONFIG_FILE.stat().st_mtime if _USER_CONFIG_FILE.exists() else 0.0
    # 冻结模式下还需检查打包默认配置是否更新
    mt_bundled = _BUNDLED_CONFIG_FILE.stat().st_mtime if _BUNDLED_CONFIG_FILE.exists() else 0.0

    with _config_lock:
        if _config_cache is not None and (mt1, mt2, mt_bundled) == _config_cache_mtime:
            return _config_cache

        # 冻结模式：打包默认作为底层，持久化配置覆盖
        if _persistent_root != _BUNDLED_ROOT and _BUNDLED_CONFIG_FILE.exists():
            base = _load_json(_BUNDLED_CONFIG_FILE)
            persistent = _load_json(_CONFIG_FILE)
            base = _deep_merge(base, persistent) if persistent else base
        else:
            base = _load_json(_CONFIG_FILE)

        user = _load_json(_USER_CONFIG_FILE)
        result = _deep_merge(base, user) if user else base

        _config_cache = result
        _config_cache_mtime = (mt1, mt2, mt_bundled)
        return result


def _invalidate_config_cache() -> None:
    """清除配置缓存，在写入配置文件后调用 (M1)。"""
    global _config_cache, _config_cache_mtime
    with _config_lock:
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


def get_maintenance_file_keywords() -> list[str]:
    """获取维修记录文件名关键字列表。

    合并 config.json 的 maintenance_file_keywords 和
    user_config 的 file_keywords.maintenance。

    Returns:
        关键字列表，默认 ["设备出勤统计表"]。
    """
    config = load_config()
    base = config.get("maintenance_file_keywords", ["设备出勤统计表"])
    user_kw = get_user_config("file_keywords", {}).get("maintenance", [])
    merged = list(base)
    for kw in user_kw:
        if kw not in merged:
            merged.append(kw)
    return merged


# ---------------------------------------------------------------------------
# 维修分类配置
# ---------------------------------------------------------------------------


def get_maintenance_classifications() -> dict:
    """获取维修分类配置。

    优先读取 config.json 的 maintenance_classifications 等字段，
    为空时返回硬编码默认值。

    Returns:
        分类配置 dict，结构同
        maintenance_classification.get_default_classifications()。
    """
    from func.maintenance_classification import get_default_classifications

    config = load_config()
    class_data = config.get("maintenance_classifications")
    if class_data and isinstance(class_data, list):
        noise_exact = set(config.get("maintenance_noise_exact", []))
        noise_patterns = config.get("maintenance_noise_patterns", [])
        reason_rules = config.get("maintenance_reason_rules", {})
        if not noise_exact:
            defaults = get_default_classifications()
            noise_exact = defaults["noise_exact"]
        if not noise_patterns:
            defaults = get_default_classifications()
            noise_patterns = defaults["noise_patterns"]
        if not reason_rules:
            defaults = get_default_classifications()
            reason_rules = defaults["reason_rules"]
        return {
            "classifications": class_data,
            "noise_exact": noise_exact,
            "noise_patterns": noise_patterns,
            "reason_rules": reason_rules,
        }
    return get_default_classifications()


def apply_maintenance_classifications(rules: dict) -> dict:
    """仅在当前运行时应用维修分类配置，不持久化到文件。

    Args:
        rules: 分类配置 dict。

    Returns:
        应用后的分类配置。
    """
    global _runtime_config
    with _runtime_lock:
        config = load_config()
        config["maintenance_classifications"] = rules.get("classifications", [])
        config["maintenance_noise_exact"] = list(rules.get("noise_exact", []))
        config["maintenance_noise_patterns"] = rules.get("noise_patterns", [])
        config["maintenance_reason_rules"] = rules.get("reason_rules", {})
        _runtime_config = config
        return rules


def update_maintenance_classifications(rules: dict) -> dict:
    """更新维修分类配置（写入 config.json）。

    Args:
        rules: 分类配置 dict。

    Returns:
        写入后的分类配置。
    """
    global _runtime_config
    config = _load_json(_CONFIG_FILE)
    config["maintenance_classifications"] = rules.get("classifications", [])
    config["maintenance_noise_exact"] = list(rules.get("noise_exact", []))
    config["maintenance_noise_patterns"] = rules.get("noise_patterns", [])
    config["maintenance_reason_rules"] = rules.get("reason_rules", {})
    _save_json(_CONFIG_FILE, config)
    _invalidate_config_cache()
    with _runtime_lock:
        _runtime_config = None
    return rules


def export_maintenance_classification_template(path: str, *, with_defaults: bool = False) -> str:
    """导出维修分类配置 Excel 模板。

    Args:
        path: 输出文件路径。
        with_defaults: True 时填充默认数据。

    Returns:
        输出文件路径。
    """
    from func.maintenance_classification import export_classification_template
    return export_classification_template(path, with_defaults=with_defaults)


def import_maintenance_classifications(path: str) -> dict:
    """从 Excel 导入维修分类配置并写入 config.json。

    Args:
        path: Excel 配置文件路径。

    Returns:
        导入的分类配置 dict。
    """
    from func.maintenance_classification import import_classifications_from_excel
    rules = import_classifications_from_excel(path)
    update_maintenance_classifications(rules)
    logger.info("维修分类配置已从 %s 导入并保存", path)
    return rules


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

_DATA_DIR = _persistent_root / "data"
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
_MINEBASE_MAPPING_FILE = _persistent_root / "minebase_column_mapping.json"

# 模块加载时初始化持久化目录（仅冻结模式）
_init_persistent_defaults()


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
