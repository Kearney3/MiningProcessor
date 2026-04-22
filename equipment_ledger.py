"""
设备台账模块
用于导入和管理设备台账表，提供设备名称模糊匹配功能
"""
import pandas as pd
from pathlib import Path
from typing import Optional
from rapidfuzz import fuzz, process

# 台账 Excel 表头定义
LEDGER_COLUMNS = [
    "设备编号",
    "标准设备名称",
    "设备类型",
    "额定装载量",
    "所属公司",
    "备注",
    "别名1",
    "别名2",
    "别名3",
    "全称",
    "旧名称",
]

# 模糊匹配阈值（相似度 >= 此值视为匹配）
FUZZY_THRESHOLD = 70


class EquipmentLedger:
    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path
        self._df: Optional[pd.DataFrame] = None
        self._search_cache: dict[str, list[str]] = {}  # 缓存：原始名称 -> 匹配列表

        if ledger_path and Path(ledger_path).exists():
            self.load(ledger_path)

    def load(self, ledger_path: str) -> pd.DataFrame:
        """从 Excel 文件加载设备台账"""
        self.ledger_path = ledger_path
        self._df = pd.read_excel(ledger_path)

        # 验证表头
        missing_cols = set(LEDGER_COLUMNS) - set(self._df.columns)
        if missing_cols:
            raise ValueError(f"台账缺少必需列: {missing_cols}")

        # 构建搜索缓存
        self._build_search_cache()
        return self._df

    def _build_search_cache(self) -> None:
        """构建搜索缓存，包含所有可匹配字段"""
        self._search_cache = {}
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            standard_name = str(row["标准设备名称"]).strip()
            if not standard_name:
                continue

            # 收集所有可能的匹配关键词
            keywords = [standard_name]
            for alias_col in ["别名1", "别名2", "别名3", "全称", "旧名称"]:
                if alias_col in self._df.columns:
                    val = str(row[alias_col]).strip()
                    if val and val != "nan":
                        keywords.append(val)

            # 缓存：每条记录的匹配关键词
            for kw in keywords:
                if kw not in self._search_cache:
                    self._search_cache[kw] = []
                self._search_cache[kw].append(standard_name)

    def export_template(self, output_path: str) -> None:
        """导出设备台账模板 Excel"""
        df = pd.DataFrame(columns=LEDGER_COLUMNS)
        # 添加示例行
        df.loc[0] = [
            "EX-001",  # 设备编号
            "NTE240",  # 标准设备名称
            "矿卡",  # 设备类型
            85,  # 额定装载量
            "XX公司",  # 所属公司
            "",  # 备注
            "NTE",  # 别名1
            "NTE240#1",  # 别名2
            "NTE240 #001",  # 别名3
            "XX公司-NTE240",  # 全称
            "",  # 旧名称
        ]
        df.to_excel(output_path, index=False)
        print(f"台账模板已导出: {output_path}")

    def match(self, raw_name: str) -> Optional[dict]:
        """
        模糊匹配设备名称
        返回: {"标准名称": str, "原始名称": str, "匹配方式": str, "相似度": int} 或 None
        """
        if self._df is None or not raw_name:
            return None

        raw_name = str(raw_name).strip()
        if not raw_name:
            return None

        # 1. 精确匹配缓存中的关键词
        for keyword, matched_standards in self._search_cache.items():
            if raw_name == keyword:
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

    def get_load_capacity(self, standard_name: str) -> int:
        """根据标准设备名称获取额定装载量"""
        if self._df is None:
            return 0

        row = self._df[self._df["标准设备名称"] == standard_name]
        if not row.empty:
            capacity = row.iloc[0]["额定装载量"]
            try:
                return int(capacity)
            except (ValueError, TypeError):
                return 0
        return 0

    def to_dict(self) -> list[dict]:
        """转换为字典列表（用于 GUI 展示）"""
        if self._df is None:
            return []
        return self._df.to_dict("records")


def load_or_create_ledger(ledger_path: Optional[str] = None) -> EquipmentLedger:
    """加载或创建设备台账"""
    if ledger_path and Path(ledger_path).exists():
        return EquipmentLedger(ledger_path)
    return EquipmentLedger()