"""油品台账区域组件"""
import flet as ft

import func.oil_ledger as oil_ledger
from func.oil_ledger import OIL_LEDGER_COLUMNS

from .ledger_base import LedgerConfig, create_ledger_section_factory


_OIL_LEDGER_STANDARD_COLS = [
    ("油品名称", "油品的原始名称（用于匹配）"),
    ("标准油品名称", "标准化后的油品名称"),
]


def create_oil_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建油品台账区域，返回 (container, refs)"""
    from func import config_loader

    cfg = LedgerConfig(
        section_title="油品台账",
        label_prefix="油品台账",
        empty_icon=ft.Icons.OIL_BARREL_OUTLINED,
        empty_text="暂无油品台账数据",
        template_filename="油品台账模板.xlsx",
        dialog_title="导入油品台账",
        dialog_height=300,
        backend_module=oil_ledger,
        backend_class_name="OilLedger",
        columns=OIL_LEDGER_COLUMNS,
        standard_cols=_OIL_LEDGER_STANDARD_COLS,
        save_cache=config_loader.save_oil_ledger_cache,
        load_cache=config_loader.load_oil_ledger_cache,
        clear_cache=config_loader.clear_oil_ledger_cache,
        has_cache=config_loader.has_oil_ledger_cache,
        var_prefix="oil",
    )
    return create_ledger_section_factory(page, log, cfg)
