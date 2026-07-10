"""维修记录处理工具函数

提供批注解析、表头检测、年月解析、设备型号提取等共用工具。
"""
import re
from datetime import date

from func.string_utils import clean_string


# ── 批注解析 ──────────────────────────────────────────────────

def parse_comment(comment_text: str) -> list[tuple[str, str]]:
    """从单元格批注中提取班次和维修内容列表。

    一条批注可能包含多个班次（白班/夜班），每个班次有独立的维修描述。
    自动清理 Site Translator: / Lei.gen: 等元数据前缀。

    Args:
        comment_text: 单元格批注原文。

    Returns:
        [(班次, 维修内容), ...]  班次为 "白班" / "夜班" / "未标注"。
    """
    if not comment_text:
        return []

    text = comment_text.strip()
    # 清理元数据前缀
    text = re.sub(r'^Site Translator:\s*\n?', '', text)
    text = re.sub(r'^Lei\.gen:\s*\n?', '', text)
    text = text.strip()
    if not text:
        return []

    entries = []
    # 按班次标记拆分
    parts = re.split(r'\n*(?=白班：|夜班：)', text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        shift_match = re.match(r'^(白班|夜班)：\s*(.*)', part, re.DOTALL)
        if shift_match:
            shift = shift_match.group(1)
            content = shift_match.group(2).strip()
        else:
            shift = "未标注"
            content = part

        content = re.sub(r'\s+', ' ', content).strip()
        if content:
            entries.append((shift, content))

    # 兜底：如果有原文但未解析出任何条目
    if not entries and text:
        text_clean = re.sub(r'\s+', ' ', text).strip()
        entries.append(("未标注", text_clean))

    return entries


# ── 表头检测 ──────────────────────────────────────────────────

def detect_header_layout(ws) -> tuple[int, dict[int, int]]:
    """从工作表表头行检测列布局。

    扫描第 1 行，找到 "原因" 列和整数值 1-31 对应的日期列。

    Args:
        ws: openpyxl Worksheet 对象。

    Returns:
        (reason_col, day_col_map)
        reason_col: "原因"列的列号 (1-based)。
        day_col_map: {day_num: col_num} 日期到列号的映射。
    """
    reason_col = 2  # 默认第 2 列
    day_col_map: dict[int, int] = {}

    for col_idx, cell in enumerate(ws[1], start=1):
        val = cell.value
        if val is None:
            continue

        if isinstance(val, str) and val.strip() == "原因":
            reason_col = col_idx
        elif isinstance(val, (int, float)):
            day_num = int(val)
            if 1 <= day_num <= 31:
                day_col_map[day_num] = col_idx

    # 兜底：未检测到日期列时，假设 C 列开始
    if not day_col_map:
        for day in range(1, 32):
            day_col_map[day] = day + 2

    return reason_col, day_col_map


# ── 年月解析 ──────────────────────────────────────────────────

def parse_year_month_from_filename(filename: str) -> tuple[int | None, int | None]:
    """从文件名解析年份和月份。

    支持格式：
      - "2024年3月设备出勤统计表.xlsx" → (2024, 3)
      - "2023年设备出勤统计表.xlsx"   → (2023, None)

    Args:
        filename: 文件名（不含路径）。

    Returns:
        (year, month)，无法解析时对应位置返回 None。
    """
    m = re.search(r'(\d{4})年(\d{1,2})月', filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'(\d{4})年', filename)
    if m:
        return int(m.group(1)), None
    return None, None


def parse_month_from_sheetname(sheetname: str) -> int | None:
    """从 sheet 名称解析月份。

    支持格式: "1月份" → 1, "3月" → 3, "12月份" → 12

    Args:
        sheetname: 工作表名称。

    Returns:
        月份整数，无法解析时返回 None。
    """
    m = re.search(r'(\d{1,2})月', sheetname)
    return int(m.group(1)) if m else None


# ── 日期解析 ──────────────────────────────────────────────────

def parse_date(date_str: str) -> date | None:
    """解析中文日期字符串。

    支持格式: "2024年3月15日" → date(2024, 3, 15)
    无效日期（如 2月30日）返回 None。

    Args:
        date_str: 中文日期字符串。

    Returns:
        date 对象，解析失败返回 None。
    """
    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', str(date_str))
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ── 设备名称处理 ──────────────────────────────────────────────

def preprocess_device_name(name: str) -> str:
    """预处理设备名称：去除换行符、合并多余空格。

    Args:
        name: 原始设备名称。

    Returns:
        清理后的名称。
    """
    return clean_string(name)


def extract_device_model(std_name: str) -> str:
    """从标准设备名称中提取设备型号。

    标准名称格式: "{型号} {两字母}#{四位数字}"
    例如: "HITACHI EX5600 EX#0123" → "HITACHI EX5600"
          "CAT D8T DZ#0168" → "CAT D8T"

    Args:
        std_name: 标准设备名称。

    Returns:
        设备型号字符串。无法提取时返回原始名称。
    """
    m = re.match(r'^(.+?)\s+[A-Z]{2}#\d{4}$', str(std_name).strip())
    return m.group(1) if m else str(std_name)
