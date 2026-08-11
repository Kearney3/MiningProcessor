"""型号台账：按标准设备编号补充设备属性。"""

from typing import Optional

from func.ledger_base import LedgerBase
from func.logger import get_logger
from func.string_utils import clean_string

logger = get_logger(__name__)


MODEL_LEDGER_COLUMNS = [
    "标准设备编号",
    "标准公司名称",
    "所有权",
    "设备型号",
    "设备类型",
    "内部分类",
]


def _id_key(value) -> str:
    """生成稳定的设备编号键，兼容 Excel 将 001 读成 1 的情况。"""
    value = clean_string(value).lower()
    if not value:
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return value


class ModelLedger(LedgerBase):
    """以标准设备编号为唯一匹配键的型号台账。"""

    def __init__(self, ledger_path: Optional[str] = None):
        self._id_cache: dict[str, dict] = {}
        self._ambiguous_ids: set[str] = set()
        super().__init__(
            ledger_columns=MODEL_LEDGER_COLUMNS,
            template_sample=["HT#1101", "A公司", "自有", "NTE240", "矿卡", "采矿设备"],
            name_column="标准设备编号",
            std_name_column="标准设备编号",
            ledger_path=ledger_path,
        )

    def _build_search_cache(self) -> None:
        self._search_cache = {}
        self._id_cache = {}
        self._ambiguous_ids = set()
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            key = _id_key(row.get("标准设备编号"))
            if not key:
                continue
            info = {
                "标准设备编号": clean_string(row.get("标准设备编号")),
                "标准公司名称": clean_string(row.get("标准公司名称")),
                "所有权": clean_string(row.get("所有权")),
                "设备型号": clean_string(row.get("设备型号")),
                "设备类型": clean_string(row.get("设备类型")),
                "内部分类": clean_string(row.get("内部分类")),
            }
            previous = self._id_cache.get(key)
            if previous is None:
                self._id_cache[key] = info
            elif previous != info:
                self._ambiguous_ids.add(key)

    def match_by_standard_id(self, standard_device_id) -> Optional[dict]:
        """按标准设备编号精确匹配；冲突编号视为未命中。"""
        key = _id_key(standard_device_id)
        if not key or key in self._ambiguous_ids:
            if key in self._ambiguous_ids:
                logger.warning("型号台账存在重复且冲突的标准设备编号: %r", standard_device_id)
            return None
        return self._id_cache.get(key)

    def match(self, raw_name: str) -> Optional[dict]:
        """兼容台账通用接口，将传入值解释为标准设备编号。"""
        result = self.match_by_standard_id(raw_name)
        if not result:
            return None
        return {
            "标准名称": result["标准设备编号"],
            "原始名称": clean_string(raw_name),
            "匹配方式": "标准设备编号精确",
            "相似度": 100,
            **result,
        }

