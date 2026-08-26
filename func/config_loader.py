"""
配置加载模块

配置分为两个文件：
- config.json        : 系统默认配置（提交到 Git）
- config.user.json   : 用户覆盖配置（gitignore，含敏感信息如数据库凭据）

load_config() 合并两者返回（user 覆盖 default），save 时按目标分别写入。
"""
import copy
import contextlib
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


DEFAULT_DAILY_REPORT_CONFIG: dict[str, Any] = {
    "material_statistics": {
        "焦煤": ["Нү"],
        "动力煤": ["oxid"],
        "工程作业": ["И.А"],
        "土石": ["Хө", "Ш.Х", "Шг.х", "Б.н"],
    },
    "formulas": {
        "延迟时间": "transfer+auxiliary_work+waiting_load",
        "待机时间": "blasting+refueling+standby+weather_snow+weather_dust+fill_water+power_issue_planned+power_issue_unplanned",
        "设备可动率": "(planned_minutes-planned_maintenance-unplanned_fault)/planned_minutes",
        "设备可动利用率": "(planned_minutes-planned_maintenance-unplanned_fault)>0?(transfer+auxiliary_work+waiting_load+total_production_minutes)/(planned_minutes-planned_maintenance-unplanned_fault):0",
        "设备利用率": "(planned_minutes-planned_maintenance-unplanned_fault)>0?(transfer+auxiliary_work+waiting_load+total_production_minutes)/(planned_minutes):0",
    },
}


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
    "KOMATSU 465": 20,
    "MT 4400": 80, "CAT 773D": 20,
}

DEFAULT_FILE_KEYWORDS: dict[str, list[str]] = {
    "fuel": ["Fuel report "],
    "electrical": ["Цахилгааны хэлтэс"],
    "production": ["白班", "夜班"],
    "worktime": ["工作效率表"],
    "maintenance": ["设备出勤统计表"],
}

# DEFAULT_WORKTIME_HEADER_MAPPING 已移至 config.json

DEFAULT_ANOMALY_DETECTION: dict[str, Any] = {
    "enabled": False,
    "generate_report": False,
    "flag_anomalies": True,
    "filter_anomalies": False,
    "handle_anomalies": False,
    "use_threshold": True,
    "use_sigma": False,
    "use_percentile": False,
    "sigma_n": 3.0,
    "percentile_low": 1.0,
    "percentile_high": 99.0,
    "thresholds": {
        "fuel": {
            "油品消耗": {"min": 0, "max": 50000, "enabled": True},
        },
        "fuel_engine": {
            "发动机小时数开始": {"min": 0, "enabled": True},
            "发动机小时数结束": {"min": 0, "enabled": True},
            "运行小时数": {"min": 0, "max": 14, "enabled": True},
        },
        "production_running": {
            "运行里程": {"min": 0, "max": 500, "enabled": True},
            "运行小时数": {"min": 0, "max": 14, "enabled": True},
            "趟次": {"min": 0, "max": 50, "enabled": True},
        },
        "production": {
            "趟次": {"min": 0, "max": 50, "enabled": True},
            "产量": {"min": 0, "max": 50000, "enabled": True},
        },
        "electrical": {
            "电力消耗": {"min": 0, "max": 50000, "enabled": True},
        },
        "worktime": {
            "__all_numeric__": {"min": 0, "max": 720, "enabled": True},
        },
        "tire": {
            "寿命（时间）": {"min": 0, "enabled": True},
            "寿命（里程）": {"min": 0, "enabled": True},
        },
    },
    "statistical_columns": {
        "fuel": {"油品消耗": {"enabled": True}},
        "fuel_engine": {"运行小时数": {"enabled": True}},
        "production_running": {"运行里程": {"enabled": True}, "运行小时数": {"enabled": True}, "趟次": {"enabled": True}},
        "production": {"趟次": {"enabled": True}, "产量": {"enabled": True}},
        "electrical": {"电力消耗": {"enabled": True}},
        "worktime": {},
        "tire": {
            "寿命（时间）": {"enabled": True},
            "寿命（里程）": {"enabled": True},
        },
    },
    "handling_rules": {
        "production_running": {
            "趟次": {"strategy": "default_value", "default": 0},
        },
        "production": {
            "趟次": {"strategy": "default_value", "default": 0},
            "产量": {"strategy": "default_value", "default": 0},
        },
        "electrical": {
            "电力消耗": {"strategy": "default_value", "default": 0},
        },
        "worktime": {
            "__all_numeric__": {"strategy": "default_value", "default": 0},
        },
        "tire": {
            "寿命（时间）": {"strategy": "nan"},
            "寿命（里程）": {"strategy": "nan"},
        },
    },
}

# M3: 线程安全锁，保护 _runtime_config 的读写
_runtime_lock = threading.Lock()
_runtime_config: dict[str, Any] | None = None

# M1: 基于文件 mtime 的配置缓存，避免 GUI 启动期间重复读盘
_config_lock = threading.Lock()  # protects _config_cache and _config_cache_mtime
_config_write_lock = threading.RLock()  # serializes read-modify-write updates
_config_cache: dict[str, Any] | None = None
_config_cache_mtime: tuple[float, float] = (0.0, 0.0)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """深合并：override 中的键覆盖 base，dict 值递归合并。"""
    # Copy the complete base tree first.  A shallow copy would leave nested
    # dicts/lists shared with the caller and let later mutations leak back into
    # the source configuration.
    result = copy.deepcopy(base)
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
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list):
            try:
                index = int(k)
            except (TypeError, ValueError):
                return None
            if index < 0 or index >= len(cur):
                return None
            cur = cur[index]
        else:
            return None
    return cur


def _set_nested(d: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
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
        with open(path, encoding="utf-8") as f:
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
    if path.name == "config.user.json":
        # This file may contain API/database credentials.  chmod is best
        # effort for platforms whose filesystems do not expose POSIX modes.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)


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
            # Never expose the mutable cache object to callers.
            return copy.deepcopy(_config_cache)

        # 冻结模式：打包默认作为底层，持久化配置覆盖
        if _persistent_root != _BUNDLED_ROOT and _BUNDLED_CONFIG_FILE.exists():
            base = _load_json(_BUNDLED_CONFIG_FILE)
            persistent = _load_json(_CONFIG_FILE)
            base = _deep_merge(base, persistent) if persistent else base
        else:
            base = _load_json(_CONFIG_FILE)

        user = _load_json(_USER_CONFIG_FILE)
        result = _deep_merge(base, user) if user else _deep_merge(base, {})

        _config_cache = result
        _config_cache_mtime = (mt1, mt2, mt_bundled)
        return copy.deepcopy(result)


def _invalidate_config_cache() -> None:
    """清除配置缓存，在写入配置文件后调用 (M1)。"""
    global _config_cache, _config_cache_mtime
    with _config_lock:
        _config_cache = None
        _config_cache_mtime = (0.0, 0.0)


def save_config(config: dict[str, Any]) -> None:
    """保存系统默认配置到 config.json（不含用户敏感数据）。"""
    with _config_write_lock:
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
    value = config.get(key, {})
    return copy.deepcopy(value) if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# 装载量版本偏好
# ---------------------------------------------------------------------------

def get_load_map_version() -> str:
    """获取当前装载量版本偏好（"new" 或 "old"）。

    读取 user_config.load_map_version，默认返回 "new"。
    """
    return get_user_config("load_map_version", "new")


def set_load_map_version(version: str) -> None:
    """持久化装载量版本偏好（写入 config.user.json）。

    Parameters
    ----------
    version : str
        "new" 或 "old"。
    """
    if version not in ("new", "old"):
        raise ValueError(f"version must be 'new' or 'old', got {version!r}")
    update_user_config({"load_map_version": version})


def apply_device_load_map(device_load_map: dict[str, int], version: str = "new") -> dict[str, int]:
    """仅在当前运行时应用设备装载量映射，不持久化到文件。

    Parameters
    ----------
    device_load_map : dict[str, int]
        要应用的装载量映射。
    version : str
        "new" 或 "old"，决定更新运行时中的哪个 key。
    """
    global _runtime_config
    config_key = "device_load_map" if version == "new" else "device_load_map_old"
    with _runtime_lock:  # M3
        config = load_config()
        config[config_key] = copy.deepcopy(device_load_map)
        _runtime_config = config
        return copy.deepcopy(_runtime_config[config_key])


def update_device_load_map(updates: dict[str, int], version: str = "new") -> dict[str, int]:
    """更新设备装载量映射（写入 config.json）。

    Parameters
    ----------
    updates : dict[str, int]
        要更新的 key-value 对。
    version : str
        "new" 或 "old"，决定写入 config.json 中的哪个 key。
    """
    global _runtime_config
    config_key = "device_load_map" if version == "new" else "device_load_map_old"
    with _config_write_lock:
        config = _load_json(_CONFIG_FILE)
        if config_key not in config:
            config[config_key] = {}
        config[config_key].update(updates)
        _save_json(_CONFIG_FILE, config)
        _invalidate_config_cache()
        with _runtime_lock:  # M2: 清除运行时缓存，确保下次读取使用最新值
            _runtime_config = None
        return dict(config[config_key])


# ---------------------------------------------------------------------------
# 班次 / 年月
# ---------------------------------------------------------------------------


def get_default_shift() -> str:
    """Get default shift value when shift column is missing (e.g. "Night")"""
    config = load_config()
    return config.get("default_shift", "Night")


def set_default_shift(shift: str) -> None:
    """Set default shift value when shift column is missing"""
    with _config_write_lock:
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
    with _config_write_lock:
        user_file = _load_json(_USER_CONFIG_FILE)
        user_file[_USER_CONFIG_SECTION] = dict(user_config)
        _save_json(_USER_CONFIG_FILE, user_file)
        _invalidate_config_cache()


def update_user_config(updates: dict[str, Any]) -> dict[str, Any]:
    """合并更新 user_config（只覆盖传入的 key，其余保留，写入 config.user.json）。"""
    with _config_write_lock:
        user_file = _load_json(_USER_CONFIG_FILE)
        current = user_file.get(_USER_CONFIG_SECTION, {})
        if not isinstance(current, dict):
            current = {}
        current.update(updates)
        user_file[_USER_CONFIG_SECTION] = current
        _save_json(_USER_CONFIG_FILE, user_file)
        _invalidate_config_cache()
        return dict(current)


def reset_user_config(section: str | None = None) -> None:
    """重置用户配置。

    - 当 `section` 为 None 时清空 config.user.json 中的 user_config。
    - 当指定了某个小节时，仅清空该小节。
    """
    with _config_write_lock:
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


def reset_all_user_overrides() -> None:
    """重置所有用户覆盖配置（清空 config.user.json，恢复为纯系统默认值）。

    与 reset_user_config() 不同，此函数清除 config.user.json 中的所有内容，
    包括 minebase、anomaly_detection 等顶层段落。
    """
    with _config_write_lock:
        _save_json(_USER_CONFIG_FILE, {})
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
    from func.maintenance_classification import (
        MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION,
        get_default_classifications,
    )

    config = load_config()
    class_data = config.get("maintenance_classifications")
    schema_version = int(config.get("maintenance_classification_schema_version", 1) or 1)
    if (
        class_data
        and isinstance(class_data, list)
        and schema_version >= MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION
    ):
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
            "schema_version": schema_version,
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
    from func.maintenance_classification import MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION

    global _runtime_config
    with _runtime_lock:
        config = load_config()
        config["maintenance_classification_schema_version"] = (
            MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION
        )
        config["maintenance_classifications"] = copy.deepcopy(rules.get("classifications", []))
        config["maintenance_noise_exact"] = copy.deepcopy(rules.get("noise_exact", []))
        config["maintenance_noise_patterns"] = copy.deepcopy(rules.get("noise_patterns", []))
        config["maintenance_reason_rules"] = copy.deepcopy(rules.get("reason_rules", {}))
        _runtime_config = config
        return copy.deepcopy(rules)


def update_maintenance_classifications(rules: dict) -> dict:
    """更新维修分类配置（写入 config.json）。

    Args:
        rules: 分类配置 dict。

    Returns:
        写入后的分类配置。
    """
    from func.maintenance_classification import MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION

    global _runtime_config
    with _config_write_lock:
        config = _load_json(_CONFIG_FILE)
        config["maintenance_classification_schema_version"] = (
            MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION
        )
        config["maintenance_classifications"] = rules.get("classifications", [])
        config["maintenance_noise_exact"] = list(rules.get("noise_exact", []))
        config["maintenance_noise_patterns"] = rules.get("noise_patterns", [])
        config["maintenance_reason_rules"] = rules.get("reason_rules", {})
        _save_json(_CONFIG_FILE, config)
        _invalidate_config_cache()
        with _runtime_lock:
            _runtime_config = None
        return copy.deepcopy(rules)


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

    优先返回 config.user.json 中的用户覆盖，否则返回 config.json 中的默认值。

    返回格式::

        {
            "mode": "position" | "name",
            "entries": [
                {"index": 1, "keywords": ["设备种类", "төрөл"], "new": "设备种类"},
                ...
            ]
        }
    """
    saved = get_user_config("worktime_header_mapping", None)
    if saved and isinstance(saved, dict) and isinstance(saved.get("entries"), list):
        return dict(saved)
    # 从 config.json 读取默认配置
    cfg = load_config()
    default = cfg.get("worktime_header_mapping", {})
    if isinstance(default, dict) and isinstance(default.get("entries"), list):
        return dict(default)
    return {"mode": "position", "entries": []}


def save_worktime_header_mapping(mapping: dict) -> None:
    """持久化工作效率表头映射配置。"""
    update_user_config({"worktime_header_mapping": mapping})


# ---------------------------------------------------------------------------
# 日报统计配置
# ---------------------------------------------------------------------------

def get_daily_report_config() -> dict[str, Any]:
    """获取日报统计配置（默认配置 + 用户覆盖）。"""
    saved = get_user_config("daily_report", None)
    if isinstance(saved, dict):
        result = _deep_merge(DEFAULT_DAILY_REPORT_CONFIG, saved)
    else:
        cfg = load_config().get("daily_report", {})
        result = _deep_merge(DEFAULT_DAILY_REPORT_CONFIG, cfg) if isinstance(cfg, dict) else copy.deepcopy(DEFAULT_DAILY_REPORT_CONFIG)

    # 原始设备字段开关已迁移到日报导出页，不再从用户配置读取。
    for legacy_key in (
        "include_raw_equipment_name",
        "include_raw_equipment_code",
        "include_raw_company_name",
    ):
        result.pop(legacy_key, None)

    # 兼容第一版日报配置：物料展开已改为自动收集全部物料类型，
    # 公式默认值也随业务口径更新；只替换旧的系统默认值，不覆盖用户真正改过的公式。
    result.pop("production_materials", None)
    legacy_material_statistics = {
        "焦煤": ["焦煤"],
        "动力煤": ["动力煤"],
        "工程作业": ["工程作业"],
        "土石": ["土石"],
    }
    if result.get("material_statistics") == legacy_material_statistics:
        result["material_statistics"] = copy.deepcopy(DEFAULT_DAILY_REPORT_CONFIG["material_statistics"])
    legacy_formulas = {
        "延迟时间": "transfer+auxiliary_work+waiting_load",
        "待机时间": "standby",
        "设备可动率": "(planned_minutes-planned_maintenance-unplanned_fault)>0?(planned_minutes-planned_maintenance-unplanned_fault)/planned_minutes:0",
        "设备可动利用率": "(planned_minutes-planned_maintenance-unplanned_fault)>0?total_production_minutes/(planned_minutes-planned_maintenance-unplanned_fault):0",
        "设备利用率": "planned_minutes>0?total_production_minutes/planned_minutes:0",
    }
    formulas = result.get("formulas", {})
    if isinstance(formulas, dict):
        for key, old_value in legacy_formulas.items():
            if formulas.get(key) == old_value:
                formulas[key] = DEFAULT_DAILY_REPORT_CONFIG["formulas"][key]
    return result


def save_daily_report_config(config: dict[str, Any]) -> dict[str, Any]:
    """持久化日报统计配置到 config.user.json。"""
    clean_config = dict(config or {})
    for legacy_key in (
        "include_raw_equipment_name",
        "include_raw_equipment_code",
        "include_raw_company_name",
    ):
        clean_config.pop(legacy_key, None)
    merged = _deep_merge(DEFAULT_DAILY_REPORT_CONFIG, clean_config)
    # 延迟导入避免 config_loader 与日报模块的初始化循环。
    from func.daily_report import validate_daily_report_formulas
    formula_errors = validate_daily_report_formulas(merged.get("formulas"))
    if formula_errors:
        details = "；".join(f"{field}：{message}" for field, message in formula_errors.items())
        raise ValueError(f"日报公式配置无效：{details}")
    update_user_config({"daily_report": merged})
    return merged


# ---------------------------------------------------------------------------
# 异常值检测配置
# ---------------------------------------------------------------------------

def get_anomaly_detection_config() -> dict[str, Any]:
    """获取异常值检测配置。

    合并 DEFAULT_ANOMALY_DETECTION 和用户配置。
    用户可在 config.user.json 的 anomaly_detection 段覆盖任何默认值。

    Returns:
        异常检测配置 dict，结构同 DEFAULT_ANOMALY_DETECTION。
    """
    config = load_config()
    ad = config.get("anomaly_detection", {})
    return _deep_merge(DEFAULT_ANOMALY_DETECTION, ad) if ad else copy.deepcopy(DEFAULT_ANOMALY_DETECTION)


def get_anomaly_thresholds(data_type: str | None = None) -> dict[str, Any]:
    """获取异常检测阈值配置。

    Parameters
    ----------
    data_type : str, optional
        数据类型（如 "fuel", "production"）。为 None 时返回全部。

    Returns
    -------
    dict
        指定数据类型的阈值 dict，或全部阈值 dict。
    """
    ad = get_anomaly_detection_config()
    thresholds = ad.get("thresholds", {})
    if data_type is not None:
        return dict(thresholds.get(data_type, {}))
    return dict(thresholds)


def get_anomaly_handling_rules() -> dict[str, Any]:
    """获取异常值处理策略配置。"""
    ad = get_anomaly_detection_config()
    return dict(ad.get("handling_rules", {}))


def update_anomaly_detection_config(updates: dict[str, Any]) -> dict[str, Any]:
    """更新异常值检测配置（写入 config.user.json 顶层 anomaly_detection 段）。

    Parameters
    ----------
    updates : dict
        要更新的字段，会与现有 anomaly_detection 配置合并。

    Returns
    -------
    dict
        更新后的完整 anomaly_detection 配置。
    """
    with _config_write_lock:
        user_file = _load_json(_USER_CONFIG_FILE)
        current = user_file.get("anomaly_detection", {})
        if not isinstance(current, dict):
            current = {}
        merged = _deep_merge(current, updates)
        user_file["anomaly_detection"] = merged
        _save_json(_USER_CONFIG_FILE, user_file)
        _invalidate_config_cache()
        return copy.deepcopy(merged)


def save_anomaly_detection_config(config_data: dict[str, Any]) -> None:
    """整体替换异常值检测配置（写入 config.user.json 顶层 anomaly_detection 段）。"""
    with _config_write_lock:
        user_file = _load_json(_USER_CONFIG_FILE)
        user_file["anomaly_detection"] = copy.deepcopy(config_data)
        _save_json(_USER_CONFIG_FILE, user_file)
        _invalidate_config_cache()


# ---------------------------------------------------------------------------
# LLM 标注配置
# ---------------------------------------------------------------------------

_DEFAULT_LLM_CONFIG: dict[str, Any] = {
    "url": "",
    "api_key": "",
    "model": "",
    "format": "openai",
    "concurrency": 10,
    "batch_size": 50,
    "timeout": 120,
    "max_retries": 3,
}


def get_llm_config() -> dict[str, Any]:
    """获取 LLM 标注配置（默认值 + 用户配置合并）。

    API Key 从 Keychain 解密；未存入 Keychain 时直接读取配置值。

    Returns:
        LLM 配置 dict，包含 url, api_key, model, format,
        concurrency, batch_size, timeout, max_retries。
    """
    from .secret_store import load_minebase_secret

    user_cfg = get_user_config("llm_labeling", {})
    cfg = _deep_merge(_DEFAULT_LLM_CONFIG, user_cfg) if user_cfg else dict(_DEFAULT_LLM_CONFIG)
    stored_key = cfg.get("api_key", "")
    if stored_key:
        try:
            decrypted = load_minebase_secret("llm_api_key")
            if decrypted:
                cfg["api_key"] = decrypted
        except Exception:
            pass
    return cfg


def update_llm_config(updates: dict[str, Any]) -> dict[str, Any]:
    """更新 LLM 标注配置（写入 config.user.json，API Key 存入 Keychain）。

    Args:
        updates: 要更新的字段。

    Returns:
        更新后的完整 LLM 配置。
    """
    from .secret_store import save_minebase_secrets

    # Do not pop from the caller-owned dictionary: RPC callers and GUI state
    # may reuse the same object after this function returns.
    pending = copy.deepcopy(updates)
    api_key = pending.pop("api_key", None)
    with _config_write_lock:
        current = get_user_config("llm_labeling", {})
        if not isinstance(current, dict):
            current = {}
        current.update(pending)
        update_user_config({"llm_labeling": current})
        if isinstance(api_key, str) and api_key.strip():
            try:
                wrapper = {"llm_api_key": {"password": api_key}}
                encrypted = save_minebase_secrets(
                    wrapper, secret_paths=[("minebase", "llm_api_key", "password")],
                )
                user_file = _load_json(_USER_CONFIG_FILE)
                minebase = user_file.get("minebase", {})
                if not isinstance(minebase, dict):
                    minebase = {}
                minebase["llm_api_key"] = encrypted["llm_api_key"]
                user_file["minebase"] = minebase
                llm_cfg = user_file.get(_USER_CONFIG_SECTION, {}).get("llm_labeling", {})
                llm_cfg["api_key"] = "keychain"
                user_file.setdefault(_USER_CONFIG_SECTION, {})["llm_labeling"] = llm_cfg
                _save_json(_USER_CONFIG_FILE, user_file)
                _invalidate_config_cache()
            except Exception:
                logger.warning("无法加密 LLM API key（MP_MASTER_KEY 未设置），密钥未保存")
                current["api_key"] = ""
                update_user_config({"llm_labeling": current})
    return get_llm_config()


def test_llm_connection(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """测试 LLM 接口连接，返回可用模型列表。

    Args:
        config: LLM 配置 dict，为 None 时从 get_llm_config() 读取。

    Returns:
        {"success": bool, "models": [...], "error": "..."}
    """
    import json as _json
    import ssl
    import urllib.error
    import urllib.request

    if config is None:
        config = get_llm_config()
    url = config.get("url", "").strip()
    api_key = config.get("api_key", "").strip()
    # 当 api_key 为空（前端掩码）时，从持久化配置中加载真实密钥
    if not api_key:
        stored = get_llm_config()
        api_key = stored.get("api_key", "").strip()
    fmt = config.get("format", "openai")
    if not url:
        return {"success": False, "models": [], "error": "未配置接口 URL"}

    base = url.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base.rsplit("/chat/completions", 1)[0]
    if base.endswith("/v1/messages"):
        base = base.rsplit("/v1/messages", 1)[0]
    if not base.endswith("/v1"):
        base = base + "/v1"
    models_url = base + "/models"

    headers: dict[str, str] = {"Accept": "application/json"}
    if fmt == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
    else:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    try:
        # 创建 SSL 上下文以解决 macOS 证书验证失败问题
        try:
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_ctx = ssl.create_default_context()

        req = urllib.request.Request(models_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        model_list = data.get("data", [])
        if isinstance(model_list, list):
            models = [
                item.get("id", "") for item in model_list if isinstance(item, dict)
            ]
        else:
            models = []
        return {"success": True, "models": sorted(models), "error": ""}
    except urllib.error.HTTPError as exc:
        # 代理可能不支持 /v1/models 端点（404/405），返回空列表让用户手动输入
        if exc.code in (404, 405):
            return {
                "success": True,
                "models": [],
                "error": "该接口不支持自动获取模型列表，请手动输入模型名称",
            }
        return {"success": False, "models": [], "error": f"{exc} (URL: {models_url})"}
    except Exception as exc:
        return {"success": False, "models": [], "error": f"{exc} (URL: {models_url})"}


# ---------------------------------------------------------------------------
# 台账缓存（JSON 格式持久化）
# ---------------------------------------------------------------------------

_DATA_DIR = _persistent_root / "data"
_EQUIPMENT_LEDGER_CACHE = _DATA_DIR / "equipment_ledger_cache.json"
_OIL_LEDGER_CACHE = _DATA_DIR / "oil_ledger_cache.json"
_MODEL_LEDGER_CACHE = _DATA_DIR / "model_ledger_cache.json"
_ledger_cache_lock = threading.RLock()


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_equipment_ledger_cache(records: list[dict]) -> None:
    """将设备台账记录缓存为 JSON 文件。"""
    with _ledger_cache_lock:
        _ensure_data_dir()
        tmp = _EQUIPMENT_LEDGER_CACHE.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"data": records}, f, ensure_ascii=False, indent=2, cls=_LedgerEncoder)
            tmp.replace(_EQUIPMENT_LEDGER_CACHE)
        finally:
            if tmp.exists():
                tmp.unlink()


def load_equipment_ledger_cache() -> list[dict] | None:
    """加载设备台账缓存，不存在时返回 None。"""
    with _ledger_cache_lock:
        if not _EQUIPMENT_LEDGER_CACHE.exists():
            return None
        try:
            with open(_EQUIPMENT_LEDGER_CACHE, encoding="utf-8") as f:
                return json.load(f).get("data")
        except Exception as e:
            logger.warning("加载设备台账缓存失败: %s", e)
            return None


def clear_equipment_ledger_cache() -> None:
    """删除设备台账缓存文件。"""
    with _ledger_cache_lock:
        if _EQUIPMENT_LEDGER_CACHE.exists():
            _EQUIPMENT_LEDGER_CACHE.unlink()


def has_equipment_ledger_cache() -> bool:
    with _ledger_cache_lock:
        return _EQUIPMENT_LEDGER_CACHE.exists()


def save_oil_ledger_cache(records: list[dict]) -> None:
    """将油品台账记录缓存为 JSON 文件。"""
    with _ledger_cache_lock:
        _ensure_data_dir()
        tmp = _OIL_LEDGER_CACHE.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"data": records}, f, ensure_ascii=False, indent=2, cls=_LedgerEncoder)
            tmp.replace(_OIL_LEDGER_CACHE)
        finally:
            if tmp.exists():
                tmp.unlink()


def load_oil_ledger_cache() -> list[dict] | None:
    """加载油品台账缓存，不存在时返回 None。"""
    with _ledger_cache_lock:
        if not _OIL_LEDGER_CACHE.exists():
            return None
        try:
            with open(_OIL_LEDGER_CACHE, encoding="utf-8") as f:
                return json.load(f).get("data")
        except Exception as e:
            logger.warning("加载油品台账缓存失败: %s", e)
            return None


def clear_oil_ledger_cache() -> None:
    """删除油品台账缓存文件。"""
    with _ledger_cache_lock:
        if _OIL_LEDGER_CACHE.exists():
            _OIL_LEDGER_CACHE.unlink()


def has_oil_ledger_cache() -> bool:
    with _ledger_cache_lock:
        return _OIL_LEDGER_CACHE.exists()


def save_model_ledger_cache(records: list[dict]) -> None:
    """将型号台账记录缓存为 JSON 文件。"""
    with _ledger_cache_lock:
        _ensure_data_dir()
        tmp = _MODEL_LEDGER_CACHE.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"data": records}, f, ensure_ascii=False, indent=2, cls=_LedgerEncoder)
            tmp.replace(_MODEL_LEDGER_CACHE)
        finally:
            if tmp.exists():
                tmp.unlink()


def load_model_ledger_cache() -> list[dict] | None:
    """加载型号台账缓存，不存在时返回 None。"""
    with _ledger_cache_lock:
        if not _MODEL_LEDGER_CACHE.exists():
            return None
        try:
            with open(_MODEL_LEDGER_CACHE, encoding="utf-8") as f:
                return json.load(f).get("data")
        except Exception as e:
            logger.warning("加载型号台账缓存失败: %s", e)
            return None


def clear_model_ledger_cache() -> None:
    """删除型号台账缓存文件。"""
    with _ledger_cache_lock:
        if _MODEL_LEDGER_CACHE.exists():
            _MODEL_LEDGER_CACHE.unlink()


def has_model_ledger_cache() -> bool:
    with _ledger_cache_lock:
        return _MODEL_LEDGER_CACHE.exists()


# ---------------------------------------------------------------------------
# MineBase 同步配置
# ---------------------------------------------------------------------------

# MineBase 配置以“连接档案”为单位保存。一个档案绑定一个地址和一组
# 凭据，因此同一地址可以保存多个账号，同一账号也可以保存多个地址。
# 密码字段只在内存中解密；落盘时由 secret_store 逐档案加密。
_MINEBASE_PROFILE_FALLBACK: dict[str, Any] = {
    "id": "local-api",
    "name": "本地 MineBase",
    "mode": "api",
    "api": {"url": "http://localhost:3000", "username": "", "password": ""},
    "database": {
        "host": "localhost",
        "port": 5432,
        "database": "minebase",
        "user": "postgres",
        "password": "",
    },
}

_MINEBASE_CONFIG_FALLBACK: dict[str, Any] = {
    "active_profile_id": "local-api",
    "profiles": [_MINEBASE_PROFILE_FALLBACK],
}


def _normalize_minebase_profile(raw: Any, index: int) -> dict[str, Any]:
    """补齐一个连接档案的默认字段，并确保其 id 可用于选择。"""
    profile = _deep_merge(_MINEBASE_PROFILE_FALLBACK, raw if isinstance(raw, dict) else {})
    profile_id = str(profile.get("id") or f"profile-{index + 1}").strip()
    profile["id"] = profile_id or f"profile-{index + 1}"
    profile["name"] = str(profile.get("name") or f"连接 {index + 1}").strip()
    if profile.get("mode") not in ("api", "database"):
        profile["mode"] = "api"

    api = profile.get("api") if isinstance(profile.get("api"), dict) else {}
    database = profile.get("database") if isinstance(profile.get("database"), dict) else {}
    profile["api"] = {
        "url": str(api.get("url") or ""),
        "username": str(api.get("username") or ""),
        "password": str(api.get("password") or ""),
    }
    try:
        port = int(database.get("port", 5432))
    except (TypeError, ValueError):
        port = 5432
    profile["database"] = {
        "host": str(database.get("host") or "localhost"),
        "port": port,
        "database": str(database.get("database") or "minebase"),
        "user": str(database.get("user") or "postgres"),
        "password": str(database.get("password") or ""),
    }
    return profile


def _normalize_minebase_config(raw: Any) -> dict[str, Any]:
    """返回独立副本的连接档案配置。"""
    raw_dict = raw if isinstance(raw, dict) else {}
    raw_profiles = raw_dict.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raw_profiles = [_MINEBASE_PROFILE_FALLBACK]

    profiles: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, raw_profile in enumerate(raw_profiles):
        profile = _normalize_minebase_profile(raw_profile, index)
        profile_id = profile["id"]
        if profile_id in used_ids:
            suffix = 2
            candidate = f"{profile_id}-{suffix}"
            while candidate in used_ids:
                suffix += 1
                candidate = f"{profile_id}-{suffix}"
            profile["id"] = candidate
        used_ids.add(profile["id"])
        profiles.append(profile)

    active_id = str(raw_dict.get("active_profile_id") or "").strip()
    if active_id not in used_ids:
        active_id = profiles[0]["id"]
    return {"active_profile_id": active_id, "profiles": profiles}


def _get_minebase_profile(profile_id: str | None = None) -> dict[str, Any]:
    """获取当前档案或指定档案的副本。"""
    config = get_minebase_config()
    selected_id = profile_id or config["active_profile_id"]
    for profile in config["profiles"]:
        if profile["id"] == selected_id:
            return copy.deepcopy(profile)
    if profile_id:
        raise ValueError(f"MineBase 连接档案不存在: {profile_id}")
    return copy.deepcopy(config["profiles"][0])


def get_minebase_config() -> dict[str, Any]:
    """获取 MineBase 连接档案配置（默认值 + 用户覆盖）。"""
    config = load_config()
    return _normalize_minebase_config(config.get("minebase"))


def get_minebase_config_default() -> dict[str, Any]:
    """获取 MineBase 连接档案默认配置（仅 config.json）。"""
    config = _load_json(_CONFIG_FILE)
    return _normalize_minebase_config(config.get("minebase"))


def get_minebase_mode(profile_id: str | None = None) -> str:
    """获取当前或指定 MineBase 连接档案的模式。"""
    return _get_minebase_profile(profile_id).get("mode", "api")


def get_minebase_api_config(profile_id: str | None = None) -> dict[str, Any]:
    """获取当前或指定 API 档案配置，密码在返回前解密。"""
    from .secret_store import _decrypt

    profile = _get_minebase_profile(profile_id)
    cfg = copy.deepcopy(profile.get("api", {}))
    cfg["password"] = _decrypt(cfg.get("password", ""))
    return cfg


def get_minebase_db_config(profile_id: str | None = None) -> dict[str, Any]:
    """获取当前或指定数据库档案配置，密码在返回前解密。"""
    from .secret_store import _decrypt

    profile = _get_minebase_profile(profile_id)
    cfg = copy.deepcopy(profile.get("database", {}))
    cfg["password"] = _decrypt(cfg.get("password", ""))
    return cfg


def _preserve_minebase_secret_sentinels(
    incoming: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    """把 UI 的密码哨兵替换为当前档案中已保存的加密值。"""
    from .secret_store import KEYRING_SENTINEL

    current_by_id = {p.get("id"): p for p in current.get("profiles", [])}
    result = copy.deepcopy(incoming)
    for profile in result.get("profiles", []):
        old = current_by_id.get(profile.get("id"), {})
        for section in ("api", "database"):
            password = profile.get(section, {}).get("password")
            if password != KEYRING_SENTINEL:
                continue
            old_password = old.get(section, {}).get("password", "")
            profile[section]["password"] = old_password if old_password else ""
    return result


def save_minebase_config(minebase_cfg: dict[str, Any]) -> None:
    """保存连接档案配置；密码按档案加密后写入 config.user.json。"""
    from .secret_store import save_minebase_secrets

    if not isinstance(minebase_cfg, dict) or not isinstance(minebase_cfg.get("profiles"), list):
        raise ValueError("MineBase 配置必须包含 profiles 列表")
    if not minebase_cfg["profiles"]:
        raise ValueError("至少需要保留一个 MineBase 连接档案")

    with _config_write_lock:
        current = get_minebase_config()
        normalized = _normalize_minebase_config(minebase_cfg)
        normalized = _preserve_minebase_secret_sentinels(normalized, current)
        cfg_to_save = save_minebase_secrets(normalized)
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
            with open(_MINEBASE_MAPPING_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("读取 MineBase 列映射文件失败，回退到默认值: %s", e)
    # 回退到 config.json 中的默认值
    config = _load_json(_CONFIG_FILE)
    return dict(config.get("minebase_column_mapping", {}))


def save_minebase_column_mapping(mapping: dict[str, dict[str, str]]) -> None:
    """保存用户自定义列映射到独立 JSON 文件。"""
    with _config_write_lock:
        _save_json(_MINEBASE_MAPPING_FILE, mapping)


def reset_minebase_column_mapping() -> None:
    """删除用户自定义映射文件，恢复为 config.json 中的默认值。"""
    with _config_write_lock:
        if _MINEBASE_MAPPING_FILE.exists():
            _MINEBASE_MAPPING_FILE.unlink()
