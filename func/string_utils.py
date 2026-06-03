"""
字符串清理工具模块

提供统一的字符串标准化功能，确保所有从 Excel 读取的文本数据：
- 去除两端空格
- 去除内部换行（\\n、\\r）
- 去除内部制表符（\\t）
- 合并连续空格为单个空格
"""

import re
import pandas as pd


def clean_string(val) -> str:
    """
    将任意值标准化为干净的字符串。

    处理规则：
    1. None / NaN / NaT → ""
    2. pd.Series → 取第一个元素后递归处理
    3. 去除两端空白
    4. 内部 \\n、\\r、\\t 替换为空格
    5. 合并连续空格为单个空格
    6. 最终再去两端空白

    Args:
        val: 任意类型的输入值

    Returns:
        清理后的字符串（保证无内部换行/Tab，两端无空格）
    """
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
    # 内部换行和制表符替换为空格
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # 合并连续空格
    s = re.sub(r" {2,}", " ", s)
    # 最终再去两端
    s = s.strip()
    return s

