"""
设备台账模块
用于导入和管理设备台账表，提供设备名称模糊匹配功能
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from rapidfuzz import fuzz, process


from func.logger import get_logger

logger = get_logger(__name__)

# 台账标准表头定义（6 列）
LEDGER_COLUMNS = [
    "设备名称",
    "设备编号",
    "公司",
    "标准设备名称",
    "标准设备编号",
    "标准公司名称",
]

# 模糊匹配阈值（相似度 >= 此值视为匹配）
FUZZY_THRESHOLD = 70


class EquipmentLedger:
    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path
        self._df: Optional[pd.DataFrame] = None
        self._search_cache: dict[str, list[str]] = {}  # 缓存：原始名称 -> 匹配列表
        self._id_cache: dict[str, dict] = {}  # 缓存：设备编号 -> 标准信息

        if ledger_path and Path(ledger_path).exists():
            self.load(ledger_path)

    def load(self, ledger_path: str, column_mapping: dict[str, str] | None = None, skip_header: bool = True) -> pd.DataFrame:
        """
        从 Excel 文件加载设备台账

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
        """构建搜索缓存，索引设备名称和标准设备名称，以及设备编号"""
        self._search_cache = {}
        self._id_cache = {}
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            std_raw = row.get("标准设备名称")
            raw_raw = row.get("设备名称")
            standard_name = "" if pd.isna(std_raw) else str(std_raw).strip()
            raw_name = "" if pd.isna(raw_raw) else str(raw_raw).strip()

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

            # 构建设备编号缓存
            id_raw = row.get("设备编号")
            std_id_raw = row.get("标准设备编号")
            company_raw = row.get("标准公司名称")
            device_id = "" if pd.isna(id_raw) else str(id_raw).strip()
            std_info = {
                "标准设备名称": standard_name,
                "标准设备编号": "" if pd.isna(std_id_raw) else str(std_id_raw).strip(),
                "标准公司名称": "" if pd.isna(company_raw) else str(company_raw).strip(),
            }
            if device_id and device_id not in self._id_cache:
                self._id_cache[device_id] = std_info

    def export_template(self, output_path: str) -> None:
        """导出设备台账模板 Excel"""
        df = pd.DataFrame(columns=LEDGER_COLUMNS)
        # 添加示例行
        df.loc[0] = [
            "NTE240 #1101",  # 设备名称
            "#1101",  # 设备编号
            "XX公司",  # 公司
            "NTE240 HT#1101",  # 标准设备名称
            "HT#1101",  # 标准设备编号
            "A公司",  # 标准公司
        ]
        df.to_excel(output_path, index=False)
        logger.info(f"台账模板已导出: {output_path}")

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

    def match_by_id(self, device_id: str) -> Optional[dict]:
        """按设备编号精确匹配，返回标准信息 dict 或 None"""
        if not device_id:
            return None
        device_id = str(device_id).strip()
        if not device_id:
            return None
        # 直接匹配
        result = self._id_cache.get(device_id)
        if result:
            return result
        # 尝试数值等价匹配（处理 pandas 读取 Excel 时 "001" -> 1 的情况）
        try:
            num_id = str(int(float(device_id)))
            return self._id_cache.get(num_id)
        except (ValueError, TypeError):
            pass
        return None

    def match_device(self, name: Optional[str] = None, device_id: Optional[str] = None) -> Optional[dict]:
        """
        组合匹配：优先用设备编号精确匹配，其次用设备名称模糊匹配。
        返回 {"标准设备名称", "标准设备编号", "标准公司名称"} 或 None
        """
        # 优先用编号精确匹配
        if device_id:
            result = self.match_by_id(device_id)
            if result:
                return result

        # 其次用名称模糊匹配
        if name:
            name_result = self.match(str(name))
            if name_result:
                # 补充编号和公司信息（如果编号缓存中有）
                std_name = name_result["标准名称"]
                # 尝试从 _id_cache 找完整信息
                for _, info in self._id_cache.items():
                    if info["标准设备名称"] == std_name:
                        return info
                # 没有完整信息，返回部分
                return {
                    "标准设备名称": std_name,
                    "标准设备编号": "",
                    "标准公司名称": "",
                }

        return None

    def to_dict(self) -> list[dict]:
        """转换为字典列表（用于 GUI 展示）"""
        if self._df is None:
            return []
        return self._df.to_dict("records")
