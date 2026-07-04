"""
路径校验工具模块

供 Flet GUI 和 Tauri bridge 共用的路径校验函数。
"""

from pathlib import Path


def sanitize_path(
    raw: str,
    must_exist: bool = False,
    allow_file: bool = True,
    allow_dir: bool = True,
) -> Path:
    """校验并规范化文件路径，防止目录遍历攻击。

    Args:
        raw: 原始路径字符串
        must_exist: 是否要求路径必须存在
        allow_file: 是否允许文件路径
        allow_dir: 是否允许目录路径

    Returns:
        规范化后的 Path 对象

    Raises:
        ValueError: 路径包含 .. 或类型不匹配
        FileNotFoundError: must_exist=True 但路径不存在
    """
    p = Path(raw).resolve()
    if ".." in Path(raw).parts:
        raise ValueError("Path must not contain ..")
    if must_exist and not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p.name}")
    if p.is_file() and not allow_file:
        raise ValueError("Expected directory, got file")
    if p.is_dir() and not allow_dir:
        raise ValueError("Expected file, got directory")
    return p
