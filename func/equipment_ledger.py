"""
设备台账模块
用于导入和管理设备台账表，提供设备名称模糊匹配功能
"""

from typing import Optional

from func.logger import get_logger
from func.ledger_base import LedgerBase
from func.string_utils import clean_string

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


class EquipmentLedger(LedgerBase):
    def __init__(self, ledger_path: Optional[str] = None):
        self._id_cache: dict[str, dict] = {}  # 缓存：设备编号 -> 标准信息
        self._name_to_info: dict[str, dict] = {}  # 反向索引：标准设备名称 -> 完整信息 (H7)
        super().__init__(
            ledger_columns=LEDGER_COLUMNS,
            template_sample=[
                "NTE240 #1101",  # 设备名称
                "#1101",  # 设备编号
                "XX公司",  # 公司
                "NTE240 HT#1101",  # 标准设备名称
                "HT#1101",  # 标准设备编号
                "A公司",  # 标准公司
            ],
            name_column="设备名称",
            std_name_column="标准设备名称",
            ledger_path=ledger_path,
        )

    def _build_search_cache(self) -> None:
        """构建搜索缓存，索引设备名称和标准设备名称，以及设备编号"""
        # 先调用基类构建 _search_cache
        super()._build_search_cache()

        self._id_cache = {}
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            std_raw = row.get("标准设备名称")
            standard_name = clean_string(std_raw)

            # 构建设备编号缓存
            id_raw = row.get("设备编号")
            std_id_raw = row.get("标准设备编号")
            company_raw = row.get("标准公司名称")
            device_id = clean_string(id_raw)
            std_info = {
                "标准设备名称": standard_name,
                "标准设备编号": clean_string(std_id_raw),
                "标准公司名称": clean_string(company_raw),
            }
            if device_id and device_id not in self._id_cache:
                self._id_cache[device_id] = std_info

        # 构建标准设备名称 -> 完整信息的反向索引 (H7)
        self._name_to_info = {}
        for _, info in self._id_cache.items():
            self._name_to_info[info["标准设备名称"]] = info

    def match_by_id(self, device_id: str) -> Optional[dict]:
        """按设备编号精确匹配，返回标准信息 dict 或 None"""
        if not device_id:
            return None
        device_id = clean_string(device_id)
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
            name_result = self.match(clean_string(name))
            if name_result:
                # 补充编号和公司信息：O(1) 反向索引查找 (H7)
                std_name = name_result["标准名称"]
                info = self._name_to_info.get(std_name)
                if info:
                    return info
                # 没有完整信息，返回部分
                return {
                    "标准设备名称": std_name,
                    "标准设备编号": "",
                    "标准公司名称": "",
                }

        return None
