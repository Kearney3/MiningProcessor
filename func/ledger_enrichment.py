"""统一设备台账与型号台账匹配路径。"""

from typing import Any, Optional

from func.logger import get_logger
from func.string_utils import clean_string

logger = get_logger(__name__)

MODEL_FIELDS = ["标准公司名称", "所有权", "设备型号", "设备类型", "内部分类"]


def resolve_equipment_attributes(
    name: Any = None,
    device_id: Any = None,
    equipment_ledger=None,
    model_ledger=None,
) -> dict[str, str]:
    """按统一优先级解析设备标准信息和型号属性。

    设备台账负责原始名称/编号到标准设备信息的解析；型号台账只接受
    设备台账得到的标准设备编号，从而避免两套匹配逻辑互相漂移。
    """
    result = {
        "标准设备名称": "",
        "标准设备编号": "",
        "标准公司名称": "",
        "所有权": "",
        "设备型号": "",
        "设备类型": "",
        "内部分类": "",
    }
    equipment_match = None
    if equipment_ledger:
        equipment_match = equipment_ledger.match_device(
            name=clean_string(name) or None,
            device_id=clean_string(device_id) or None,
        )
        if equipment_match:
            for key in ("标准设备名称", "标准设备编号", "标准公司名称"):
                result[key] = clean_string(equipment_match.get(key))

    if model_ledger and result["标准设备编号"]:
        model_match = model_ledger.match_by_standard_id(result["标准设备编号"])
        if model_match:
            # 型号台账是本次扩展属性的来源，标准公司名称也以型号台账
            # 为准；同步入口不会把这些扩展字段发送到 MineBase。
            model_company = clean_string(model_match.get("标准公司名称"))
            if model_company:
                result["标准公司名称"] = model_company
            for key in ("所有权", "设备型号", "设备类型", "内部分类"):
                result[key] = clean_string(model_match.get(key))
        else:
            logger.warning(
                "型号台账未匹配: 标准设备编号=%r", result["标准设备编号"]
            )

    return result


def enrich_dataframe_device(
    df,
    name_col: str,
    id_col: Optional[str] = None,
    equipment_ledger=None,
    model_ledger=None,
    suffix: str = "",
):
    """返回补充设备标准字段/型号字段后的副本。"""
    result = df.copy()
    attributes = []
    for _, row in result.iterrows():
        attributes.append(resolve_equipment_attributes(
            name=row.get(name_col),
            device_id=row.get(id_col) if id_col else None,
            equipment_ledger=equipment_ledger,
            model_ledger=model_ledger,
        ))
    for key in ("标准设备名称", "标准设备编号", "标准公司名称", *MODEL_FIELDS):
        result[f"{key}{suffix}"] = [item[key] for item in attributes]
    return result
