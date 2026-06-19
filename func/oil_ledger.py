"""
油品台账模块
用于导入和管理油品台账表，提供油品名称模糊匹配功能
"""

from typing import Optional

from func.ledger_base import LedgerBase

# 台账标准表头定义（2 列）
OIL_LEDGER_COLUMNS = [
    "油品名称",
    "标准油品名称",
]


class OilLedger(LedgerBase):
    def __init__(self, ledger_path: Optional[str] = None):
        super().__init__(
            ledger_columns=OIL_LEDGER_COLUMNS,
            template_sample=[
                "0# 柴油",  # 油品名称
                "0号柴油",  # 标准油品名称
            ],
            name_column="油品名称",
            std_name_column="标准油品名称",
            ledger_path=ledger_path,
        )
