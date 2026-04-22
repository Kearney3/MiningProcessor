"""
配置加载模块
用于加载和保存 config.json 配置文件
"""
import json
import os
from pathlib import Path
from typing import Any

_CONFIG_FILE = Path(__file__).parent / "config.json"


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
    config = load_config()
    key = f"device_load_map_{version}" if version != "new" else "device_load_map"
    return config.get(key, {})


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
