"""
设备台账模块
用于导入和管理设备台账表，提供设备名称精确匹配功能
"""


from func.ledger_base import LedgerBase
from func.logger import get_logger
from func.string_utils import clean_equipment_name, clean_string

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
    1. 同时有设备名称和设备编号时，按二者联合匹配
    2. 联合匹配失败或没有设备编号时，按设备名称匹配
    3. 名称匹配结果的标准设备编号不一致时视为歧义

    典型用法：
        ledger = EquipmentLedger("设备台账.xlsx")
        result = ledger.match_device(name="NTE240 #1101", device_id="#1101")
        # -> {"标准设备名称": "NTE240 HT#1101", "标准设备编号": "HT#1101", "标准公司名称": "A公司"}
    """
    def __init__(self, ledger_path: str | None = None):
        self._id_cache: dict[str, dict] = {}  # 缓存：设备编号 -> 标准信息
        self._name_to_info: dict[str, dict] = {}  # 反向索引：标准设备名称 -> 完整信息 (H7)
        self._name_records: dict[str, list[dict]] = {}
        self._pair_cache: dict[tuple[str, str], list[dict]] = {}
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
        self._name_records = {}
        self._pair_cache = {}
        if self._df is None:
            return

        for _, row in self._df.iterrows():
            raw_name = clean_equipment_name(row.get("设备名称"))
            std_raw = row.get("标准设备名称")
            std_raw_clean = clean_equipment_name(std_raw)
            standard_name = std_raw_clean if std_raw_clean else raw_name

            std_id_raw = row.get("标准设备编号")
            company_raw = row.get("标准公司名称")
            info = {
                "标准设备名称": standard_name,
                "标准设备编号": clean_equipment_name(std_id_raw),
                "标准公司名称": clean_string(company_raw),
            }

            # 名称索引同时支持原始名称和标准名称。完整记录保存在索引
            # 中，后续才能在名称歧义时检查所有记录的标准设备编号。
            name_keys = {
                value.lower()
                for value in (raw_name, standard_name)
                if value
            }
            for name_key in name_keys:
                self._name_records.setdefault(name_key, []).append(info)

            # 联合索引按名称+编号建立。设备编号通常来自“设备编号”，
            # 同时接受“标准设备编号”，便于输入数据已经使用标准编号时
            # 仍能完成联合匹配。
            id_keys = {
                id_key
                for value in (clean_equipment_name(row.get("设备编号")), info["标准设备编号"])
                for id_key in self._id_keys(value)
            }
            for name_key in name_keys:
                for id_key in id_keys:
                    pair_key = (name_key, id_key)
                    self._pair_cache.setdefault(pair_key, []).append(info)

            # 构建设备编号缓存（key 小写化）
            id_raw = row.get("设备编号")
            device_id = clean_equipment_name(id_raw).lower()
            std_info = dict(info)
            if device_id and device_id not in self._id_cache:
                self._id_cache[device_id] = std_info

            # 构建标准设备名称 -> 完整信息的反向索引 (H7)（key 小写化）
            if std_raw_clean:
                key = std_raw_clean.lower()
                if key not in self._name_to_info:
                    self._name_to_info[key] = dict(info)

    @staticmethod
    def _id_keys(value: str) -> set[str]:
        """返回设备编号的文本键及 Excel 数字化后的等价键。"""
        cleaned = clean_equipment_name(value)
        if not cleaned:
            return set()

        keys = {cleaned.lower()}
        try:
            keys.add(str(int(float(cleaned))).lower())
        except (ValueError, TypeError):
            pass
        return keys

    @staticmethod
    def _resolve_candidates(candidates: list[dict]) -> dict | None:
        """仅在候选记录的标准设备编号一致时返回标准信息。"""
        if not candidates:
            return None

        standard_ids = {
            clean_equipment_name(item.get("标准设备编号")) for item in candidates
        }
        if len(standard_ids) != 1:
            logger.debug(
                "设备名称匹配歧义: 候选记录的标准设备编号不一致 %s",
                sorted(standard_ids),
            )
            return None
        return dict(candidates[0])

    def _name_candidates(self, cleaned_name: str) -> list[dict]:
        """返回名称对应的全部候选记录。"""
        return self._name_records.get(cleaned_name.lower(), [])

    def match_by_id(self, device_id: str) -> dict | None:
        """按设备编号精确匹配（大小写不敏感），返回标准信息 dict 或 None"""
        if not device_id:
            return None
        device_id = clean_equipment_name(device_id).lower()
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

    def match_device(self, name: str | None = None, device_id: str | None = None) -> dict | None:
        """
        组合匹配：按以下优先级尝试，命中即返回。
        1. 同时有编号和名称 → 先按二者联合匹配
        2. 联合匹配失败或缺少编号 → 仅按名称匹配
        3. 名称候选的标准设备编号不一致 → 视为歧义，匹配失败
        4. 没有名称 → 匹配失败

        未匹配的记录会输出 warning 日志。
        返回 {"标准设备名称", "标准设备编号", "标准公司名称"} 或 None
        """
        cleaned_name = clean_equipment_name(name) if name else None
        cleaned_id = clean_equipment_name(device_id) if device_id else None

        # 都没有
        if not cleaned_id and not cleaned_name:
            return None

        result = None

        if cleaned_id and cleaned_name:
            # 名称+编号先走联合索引。这样名称本身即使对应多个设备，
            # 也可以由编号把候选集缩小到正确记录。
            name_key = cleaned_name.lower()
            exact_id_key = cleaned_id.lower()
            pair_candidates = self._pair_cache.get((name_key, exact_id_key), [])
            if not pair_candidates:
                # 仅在没有文本精确键时，才使用 Excel 数字化后的等价键，
                # 避免同时存在 "001" 和 "1" 时把两条设备混成歧义。
                for id_key in self._id_keys(cleaned_id) - {exact_id_key}:
                    pair_candidates = self._pair_cache.get((name_key, id_key), [])
                    if pair_candidates:
                        break
            result = self._resolve_candidates(pair_candidates)

            # 联合匹配失败后，按规则回退为名称匹配。
            if not result:
                result = self._match_by_name(cleaned_name)
        elif cleaned_name:
            # 缺少设备编号时只按名称匹配；名称缺失时不允许仅凭编号命中。
            result = self._match_by_name(cleaned_name)

        if not result:
            logger.warning(f"设备台账未匹配: 名称={name!r}, 编号={device_id!r}")

        return result

    def _match_by_name(self, cleaned_name: str) -> dict | None:
        """通过名称匹配，返回完整标准信息。多条不一致视为未命中。"""
        return self._resolve_candidates(self._name_candidates(cleaned_name))

    def match(self, raw_name: str) -> dict | None:
        """按名称匹配，并按标准设备编号判断候选是否有歧义。"""
        if self._df is None or not raw_name:
            return None

        cleaned_name = clean_equipment_name(raw_name)
        if not cleaned_name:
            return None

        info = self._resolve_candidates(self._name_candidates(cleaned_name))
        if not info:
            return None
        return {
            "标准名称": info["标准设备名称"],
            "原始名称": cleaned_name,
            "匹配方式": "精确",
            "相似度": 100,
        }
