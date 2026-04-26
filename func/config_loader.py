"""
配置加载模块
用于加载和保存 config.json 配置文件
"""
import json
import os
from pathlib import Path
from typing import Any

_CONFIG_FILE = Path(__file__).parent.parent / "config.json"
_runtime_config: dict[str, Any] | None = None


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
