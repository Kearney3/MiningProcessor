"""设备台账区域组件"""
import flet as ft

import func.equipment_ledger as equipment_ledger
from func.equipment_ledger import LEDGER_COLUMNS

from .ledger_base import LedgerConfig, create_ledger_section_factory


_LEDGER_STANDARD_COLS = [
    ("设备名称", "设备的原始名称（用于匹配）"),
    ("设备编号", "设备的原始编号"),
    ("公司", "设备所属公司"),
    ("标准设备名称", "标准化后的设备名称"),
    ("标准设备编号", "标准化后的设备编号"),
    ("标准公司名称", "标准化后的公司名称"),
]


def create_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建设备台账区域，返回 (container, refs)"""
    from func import config_loader

    cfg = LedgerConfig(
        section_title="设备台账",
        label_prefix="台账",
        empty_icon=ft.Icons.INVENTORY_2_OUTLINED,
        empty_text="暂无设备台账数据",
        template_filename="设备台账模板.xlsx",
        dialog_title="导入设备台账",
        dialog_height=400,
        backend_module=equipment_ledger,
        backend_class_name="EquipmentLedger",
        columns=LEDGER_COLUMNS,
        standard_cols=_LEDGER_STANDARD_COLS,
        save_cache=config_loader.save_equipment_ledger_cache,
        load_cache=config_loader.load_equipment_ledger_cache,
        clear_cache=config_loader.clear_equipment_ledger_cache,
        has_cache=config_loader.has_equipment_ledger_cache,
        var_prefix="ledger",
    )
    return create_ledger_section_factory(page, log, cfg)
