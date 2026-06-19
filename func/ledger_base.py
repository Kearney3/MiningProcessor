"""
台账基类模块
为 EquipmentLedger 和 OilLedger 提供共享的通用台账逻辑：
加载、模糊匹配、搜索缓存、模板导出、字典转换。
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from rapidfuzz import fuzz, process

from func.logger import get_logger
from func.string_utils import clean_string

logger = get_logger(__name__)

# 共用模糊匹配阈值（相似度 >= 此值视为匹配）
FUZZY_THRESHOLD = 70


class LedgerBase:
    """
    台账基类，通过构造参数定制列名与模板数据。
    子类可覆盖 _build_search_cache 来扩展缓存逻辑。
    """

    def __init__(
        self,
        ledger_columns: list[str],
        template_sample: list[str],
        name_column: str = "名称",
        std_name_column: str = "标准名称",
        ledger_path: Optional[str] = None,
    ):
        self._ledger_columns = ledger_columns
        self._template_sample = template_sample
        self._name_column = name_column
        self._std_name_column = std_name_column
        self.ledger_path = ledger_path
        self._df: Optional[pd.DataFrame] = None
        self._search_cache: dict[str, list[str]] = {}

        if ledger_path and Path(ledger_path).exists():
            self.load(ledger_path)

    def load(
        self,
        ledger_path: str,
        column_mapping: dict[str, str] | None = None,
        skip_header: bool = True,
    ) -> pd.DataFrame:
        """
        从 Excel 文件加载台账。

        Args:
            ledger_path: Excel 文件路径
            column_mapping: 列映射 {标准列名: Excel列名}，None 时使用原始列名
            skip_header: 是否将第一行视为标题行（True 时第一行作为列名，False 时使用默认列名 Col0/Col1/...）
        """
        self.ledger_path = ledger_path

        if skip_header:
            self._df = pd.read_excel(ledger_path)
        else:
            self._df = pd.read_excel(ledger_path, header=None)
            self._df.columns = [f"Col{i}" for i in range(len(self._df.columns))]

        # 应用列映射
        if column_mapping:
            rename_map = {}
            for standard_col, excel_col in column_mapping.items():
                if excel_col and excel_col in self._df.columns:
                    rename_map[excel_col] = standard_col
            if rename_map:
                self._df = self._df.rename(columns=rename_map)

        # 构建搜索缓存（不强制要求所有列都存在）
        self._build_search_cache()
        return self._df

    def _build_search_cache(self) -> None:
        """构建搜索缓存，索引原始名称和标准名称"""
        self._search_cache = {}
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            std_raw = row.get(self._std_name_column)
            raw_raw = row.get(self._name_column)
            standard_name = clean_string(std_raw)
            raw_name = clean_string(raw_raw)

            # 跳过标准名称和原始名称都为空的行
            if not standard_name and not raw_name:
                continue

            # 使用标准名称作为主匹配键，若为空则用原始名称
            primary = standard_name if standard_name else raw_name

            # 收集匹配关键词
            keywords = []
            if raw_name:
                keywords.append(raw_name)
            if standard_name and standard_name != raw_name:
                keywords.append(standard_name)

            if not keywords:
                continue

            for kw in keywords:
                if kw not in self._search_cache:
                    self._search_cache[kw] = []
                self._search_cache[kw].append(primary)

    def export_template(self, output_path: str) -> None:
        """导出台账模板 Excel"""
        df = pd.DataFrame(columns=self._ledger_columns)
        # 添加示例行
        df.loc[0] = self._template_sample
        df.to_excel(output_path, index=False)
        logger.info(f"台账模板已导出: {output_path}")

    def match(self, raw_name: str) -> Optional[dict]:
        """
        模糊匹配名称
        返回: {"标准名称": str, "原始名称": str, "匹配方式": str, "相似度": int} 或 None
        """
        if self._df is None or not raw_name:
            return None

        raw_name = clean_string(raw_name)
        if not raw_name:
            return None

        # 精确匹配：O(1) 字典查找替代遍历 (H6)
        matched_standards = self._search_cache.get(raw_name)
        if matched_standards:
            return {
                "标准名称": matched_standards[0],
                "原始名称": raw_name,
                "匹配方式": "精确",
                "相似度": 100,
            }

        # 2. 前缀匹配
        for keyword, matched_standards in self._search_cache.items():
            if raw_name.startswith(keyword) or keyword.startswith(raw_name):
                return {
                    "标准名称": matched_standards[0],
                    "原始名称": raw_name,
                    "匹配方式": "前缀",
                    "相似度": 80,
                }

        # 3. 相似度匹配（使用 rapidfuzz）
        all_keywords = list(self._search_cache.keys())
        if all_keywords:
            best_match = process.extractOne(
                raw_name, all_keywords, scorer=fuzz.ratio
            )
            if best_match and best_match[1] >= FUZZY_THRESHOLD:
                matched_standards = self._search_cache[best_match[0]]
                return {
                    "标准名称": matched_standards[0],
                    "原始名称": raw_name,
                    "匹配方式": "相似度",
                    "相似度": int(best_match[1]),
                }

        # 4. 无匹配
        return None

    def to_dict(self) -> list[dict]:
        """转换为字典列表（用于 GUI 展示）"""
        if self._df is None:
            return []
        return self._df.to_dict("records")
