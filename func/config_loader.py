"""
配置加载模块
用于加载和保存 config.json 配置文件
"""
import json
import os
from pathlib import Path
from typing import Any

_USER_CONFIG_SECTION = "user_config"
_USER_CONFIG_DEFAULT_SECTION = "user_config_default"

_CONFIG_FILE = Path(__file__).parent.parent / "config.json"
# 默认设备装载量映射（当 config.json 读取失败时使用）
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

# 默认文件关键字配置（用于批量处理时识别文件类型）
DEFAULT_FILE_KEYWORDS: dict[str, list[str]] = {
    "fuel": ["Fuel report "],
    "electrical": ["Цахилгааны хэлтэс"],
    "production": ["白班", "夜班"],
    "worktime": ["工作效率表"],
}

_runtime_config: dict[str, Any] | None = None



def get_default_load_map(version: str = "new") -> dict[str, int]:
    """获取默认设备装载量映射（当 config.json 读取失败时的 fallback）"""
    return dict(DEFAULT_LOAD_MAP_OLD if version == "old" else DEFAULT_LOAD_MAP_NEW)

def get_config_file_path() -> Path:
    """获取内置配置文件路径"""
    return _CONFIG_FILE


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(f"配置文件不存在: {_CONFIG_FILE}")
    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict[str, Any]) -> None:
    """保存配置文件"""
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def get_device_load_map(version: str = "new") -> dict[str, int]:
    """
    获取设备装载量映射
    version: "new" (默认) 或 "old"
    """
    config = _runtime_config if _runtime_config is not None else load_config()
    key = f"device_load_map_{version}" if version != "new" else "device_load_map"
    return config.get(key, {})


def apply_device_load_map(device_load_map: dict[str, int]) -> dict[str, int]:
    """仅在当前运行时应用设备装载量映射，不持久化到文件"""
    global _runtime_config
    config = load_config()
    config["device_load_map"] = dict(device_load_map)
    _runtime_config = config
    return _runtime_config["device_load_map"]


def update_device_load_map(updates: dict[str, int]) -> dict[str, int]:
    """更新设备装载量映射"""
    config = load_config()
    if "device_load_map" not in config:
        config["device_load_map"] = {}
    config["device_load_map"].update(updates)
    save_config(config)
    return config["device_load_map"]


def get_shift_mapping() -> dict[str, str]:
    """获取班次名称映射"""
    config = load_config()
    return config.get("shift_mapping", {})


def get_default_year() -> int:
    """获取默认年份"""
    config = load_config()
    return config.get("default_year", 2025)


def get_default_month() -> int:
    """获取默认月份"""
    config = load_config()
    return config.get("default_month", 1)


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
    """整体替换并持久化 user_config 段落。"""
    config = load_config()
    config[_USER_CONFIG_SECTION] = dict(user_config)
    save_config(config)


def update_user_config(updates: dict[str, Any]) -> dict[str, Any]:
    """合并更新 user_config（只覆盖传入的 key，其余保留）。"""
    config = load_config()
    current = config.get(_USER_CONFIG_SECTION, {})
    if not isinstance(current, dict):
        current = {}
    current.update(updates)
    config[_USER_CONFIG_SECTION] = current
    save_config(config)
    return current


def reset_user_config(section: str | None = None) -> None:
    """重置用户配置。

    - 当 `section` 为 None 时清空整个 user_config。
    - 当指定了某个小节时，仅清空该小节。
    """
    config = load_config()
    if section is None:
        config[_USER_CONFIG_SECTION] = {}
    else:
        user_config = config.get(_USER_CONFIG_SECTION, {})
        if not isinstance(user_config, dict):
            user_config = {}
        user_config.pop(section, None)
        config[_USER_CONFIG_SECTION] = user_config
    save_config(config)


def get_user_config_default(section: str | None = None, default: Any = None) -> Any:
    """读取 user_config_default 中的默认配置骨架。"""
    config = load_config()
    defaults = config.get(_USER_CONFIG_DEFAULT_SECTION, {})
    if section is None:
        return defaults if defaults else default
    return defaults.get(section, default) if isinstance(defaults, dict) else default


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

DEFAULT_WORKTIME_HEADER_MAPPING: dict = {
    "mode": "position",
    "fuzzy": False,
    "entries": [
        {"index": 1, "original": "", "new": "日期"},
        {"index": 2, "original": "", "new": "班次"},
        {"index": 3, "original": "", "new": "序号"},
        {"index": 4, "original": "", "new": "设备种类"},
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


def is_worktime_header_apply() -> bool:
    """获取工作效率表头修改开关状态（默认 True）。"""
    config = load_config()
    return config.get("worktime_header_apply", True)


def set_worktime_header_apply(enabled: bool) -> None:
    """设置工作效率表头修改开关状态并持久化。"""
    config = load_config()
    config["worktime_header_apply"] = bool(enabled)
    save_config(config)
