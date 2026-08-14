"""设备台账区域组件"""
import flet as ft

import func.equipment_ledger as equipment_ledger
from func.equipment_ledger import LEDGER_COLUMNS

from .ledger_base import LedgerConfig, create_ledger_section_factory
from gui.i18n import t


_LEDGER_STANDARD_COLS = [
    ("设备名称", t("components:ledger.设备的原始名称（用于匹配）_9a53")),
    ("设备编号", t("components:ledger.设备的原始编号_502f")),
    ("公司", t("components:ledger.设备所属公司_a154")),
    ("标准设备名称", t("components:ledger.标准化后的设备名称_deab")),
    ("标准设备编号", t("components:ledger.标准化后的设备编号_f5ca")),
    ("标准公司名称", t("components:ledger.标准化后的公司名称_8559")),
]


def create_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建设备台账区域，返回 (container, refs)"""
    from func import config_loader

    cfg = LedgerConfig(
        section_title=t("components:ledger.设备台账_e6a7"),
        label_prefix=t("components:ledger.台账_4d78"),
        empty_icon=ft.Icons.INVENTORY_2_OUTLINED,
        empty_text=t("components:ledger.暂无设备台账数据_b7fb"),
        template_filename=t("components:ledger.设备台账模板.xlsx_f258"),
        dialog_title=t("components:ledger.导入设备台账_ecdf"),
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
