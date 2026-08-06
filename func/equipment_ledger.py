"""
设备台账模块
用于导入和管理设备台账表，提供设备名称精确匹配功能
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
    """设备名称标准化与匹配。

    提供设备台账的导入、缓存构建与匹配能力，用于将报表中的原始设备名
    称标准化为台账中登记的标准名称。

    匹配策略（优先级由高到低）：
    1. 设备编号精确匹配（match_by_id）—— O(1) 缓存查找
    2. 设备名称精确匹配（继承自 LedgerBase.match）

    典型用法：
        ledger = EquipmentLedger("设备台账.xlsx")
        result = ledger.match_device(name="NTE240 #1101", device_id="#1101")
        # -> {"标准设备名称": "NTE240 HT#1101", "标准设备编号": "HT#1101", "标准公司名称": "A公司"}
    """
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
        """构建搜索缓存，索引设备名称和标准设备名称，以及设备编号（大小写不敏感）"""
        # 先调用基类构建 _search_cache
        super()._build_search_cache()

        self._id_cache = {}
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            std_raw = row.get("标准设备名称")
            standard_name = clean_string(std_raw)

            # 构建设备编号缓存（key 小写化）
            id_raw = row.get("设备编号")
            std_id_raw = row.get("标准设备编号")
            company_raw = row.get("标准公司名称")
            device_id = clean_string(id_raw).lower()
            std_info = {
                "标准设备名称": standard_name,
                "标准设备编号": clean_string(std_id_raw),
                "标准公司名称": clean_string(company_raw),
            }
            if device_id and device_id not in self._id_cache:
                self._id_cache[device_id] = std_info

        # 构建标准设备名称 -> 完整信息的反向索引 (H7)（key 小写化）
        self._name_to_info = {}
        for _, info in self._id_cache.items():
            self._name_to_info[info["标准设备名称"].lower()] = info

    def match_by_id(self, device_id: str) -> Optional[dict]:
        """按设备编号精确匹配（大小写不敏感），返回标准信息 dict 或 None"""
        if not device_id:
            return None
        device_id = clean_string(device_id).lower()
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
        组合匹配：按以下优先级尝试，命中即返回。
        1. 同时有编号和名称 → 两者都匹配且结果一致才命中
        2. 只有编号 → 编号匹配
        3. 只有名称 → 名称匹配（多条不一致视为未命中）
        4. 都没有 → None

        未匹配的记录会输出 warning 日志。
        返回 {"标准设备名称", "标准设备编号", "标准公司名称"} 或 None
        """
        cleaned_name = clean_string(name) if name else None
        cleaned_id = clean_string(device_id) if device_id else None

        # 都没有
        if not cleaned_id and not cleaned_name:
            return None

        result = None

        if cleaned_id and cleaned_name:
            # 编号和名称同时存在：两者都匹配且结果一致才命中
            id_result = self.match_by_id(cleaned_id)
            name_result = self.match(cleaned_name)
            if id_result and name_result:
                id_std = id_result.get("标准设备名称", "")
                name_std = name_result.get("标准名称", "")
                if id_std == name_std:
                    result = id_result
                else:
                    logger.debug(
                        "编号与名称匹配不一致: 编号=%r→%r, 名称=%r→%r",
                        cleaned_id, id_std, cleaned_name, name_std,
                    )
            # 一致匹配失败，回退到名称匹配
            if not result:
                result = self._match_by_name(cleaned_name)
        elif cleaned_id:
            result = self.match_by_id(cleaned_id)
        elif cleaned_name:
            result = self._match_by_name(cleaned_name)

        if not result:
            logger.warning(f"设备台账未匹配: 名称={name!r}, 编号={device_id!r}")

        return result

    def _match_by_name(self, cleaned_name: str) -> Optional[dict]:
        """通过名称匹配，返回完整标准信息。多条不一致视为未命中。"""
        name_result = self.match(cleaned_name)
        if not name_result:
            return None
        std_name = name_result["标准名称"]
        info = self._name_to_info.get(std_name.lower())
        if info:
            return info
        return {
            "标准设备名称": std_name,
            "标准设备编号": "",
            "标准公司名称": "",
        }
