"""
字符串清理工具模块

提供统一的字符串标准化功能，确保所有从 Excel 读取的文本数据：
- 去除两端空格
- 去除内部换行（\\n、\\r）
- 去除内部制表符（\\t）
- 去除零宽字符（ZWSP/ZWNJ/ZWJ/Word Joiner/BOM）
- 不换行空格替换为普通空格
- 合并连续空格为单个空格
- 西里尔同形字母替换为拉丁字母（避免 С→C 等视觉相同字符导致匹配失败）
"""

import re

import pandas as pd

_MULTI_SPACE = re.compile(r' {2,}')
# 零宽字符（删除）：ZWSP, ZWNJ, ZWJ, Word Joiner, Mongolian Vowel Separator, BOM
_ZERO_WIDTH = re.compile(r'[​‌‍⁠᠎﻿]')

# 西里尔字母 → 拉丁字母同形映射（仅覆盖与拉丁字母视觉完全相同的字符）
# Excel 中的蒙古文设备名称经常混用西里尔/拉丁字母，肉眼无法区分但 Unicode 不同
_CYRILLIC_TO_LATIN_MAP = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H",
    "І": "I", "К": "K", "М": "M", "О": "O", "Р": "P",
    "Т": "T", "Х": "X",
})


def normalize_cyrillic_homoglyphs(text: str) -> str:
    """将西里尔同形字母替换为对应的拉丁字母。

    用于设备名称、型号等需要精确匹配的场景，避免 С(Cyrillic) vs C(Latin)
    等肉眼无法区分的字符导致匹配失败。

    Args:
        text: 已清理的字符串

    Returns:
        替换后的字符串
    """
    return text.translate(_CYRILLIC_TO_LATIN_MAP)


def clean_string(val) -> str:
    """
    将任意值标准化为干净的字符串。

    处理规则：
    1. None / NaN / NaT → ""
    2. pd.Series → 取第一个元素后递归处理
    3. 去除两端空白
    4. 内部 \\n、\\r、\\t 替换为空格
    5. 不换行空格（\\u00a0）替换为普通空格
    6. 删除零宽字符（ZWSP/ZWNJ/ZWJ/Word Joiner/BOM）
    7. 合并连续空格为单个空格
    8. 最终再去两端空白

    Args:
        val: 任意类型的输入值

    Returns:
        清理后的字符串（保证无内部换行/Tab/零宽字符，两端无空格）
    """
    # Fast path for numeric values - skip all string processing
    if isinstance(val, (int, float)) and not pd.isna(val):
        return str(val)

    # 处理 pd.Series
    if isinstance(val, pd.Series):
        if val.empty:
            return ""
        val = val.iloc[0]

    # 处理 None / NaN / NaT
    try:
        if val is None or pd.isna(val):
            return ""
    except (ValueError, TypeError):
        # pd.isna 对某些类型会抛异常，安全降级
        pass

    # 转字符串并清理
    s = str(val)
    # 去两端空白
    s = s.strip()
    if not s:
        return ""
    # 内部换行和制表符替换为空格
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # 不换行空格替换为普通空格
    s = s.replace(" ", " ")
    # 删除零宽字符
    s = _ZERO_WIDTH.sub("", s)
    # 合并连续空格
    s = _MULTI_SPACE.sub(" ", s)
    # 最终再去两端
    s = s.strip()
    return s


def clean_equipment_name(val) -> str:
    """将任意值标准化为干净的设备名称/编号字符串。

    等价于 clean_string() + normalize_cyrillic_homoglyphs()，
    用于设备名称和设备编号的提取，确保输出使用标准化拉丁字母。

    不用于一般文本（班次名称、矿石类型、蒙古文标签等），
    因为那些场景中 Cyrillic 字母是合法的非同形字符。

    Args:
        val: 任意类型的输入值

    Returns:
        清理后的字符串，Cyrillic 同形字母已替换为 Latin 对应字符
    """
    return normalize_cyrillic_homoglyphs(clean_string(val))
