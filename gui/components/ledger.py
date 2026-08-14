"""设备台账区域组件"""
import flet as ft

import func.equipment_ledger as equipment_ledger
from func.equipment_ledger import LEDGER_COLUMNS

from .ledger_base import LedgerConfig, create_ledger_section_factory
from gui.i18n import t


_LEDGER_STANDARD_COLS = [
    ("设备名称", t("components:ledger.originalEquipmentNameForMatching")),
    ("设备编号", t("components:ledger.originalEquipmentId")),
    ("公司", t("components:ledger.equipmentCompany")),
    ("标准设备名称", t("components:ledger.standardizedEquipmentName")),
    ("标准设备编号", t("components:ledger.standardizedEquipmentId")),
    ("标准公司名称", t("components:ledger.standardizedCompanyName")),
]


def create_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建设备台账区域，返回 (container, refs)"""
    from func import config_loader

    cfg = LedgerConfig(
        section_title=t("components:ledger.equipmentLedgerEquipmentLedger"),
        label_prefix=t("components:ledger.equipmentLedger"),
        empty_icon=ft.Icons.INVENTORY_2_OUTLINED,
        empty_text=t("components:ledger.noEquipmentLedgerData"),
        template_filename=t("components:ledger.equipmentLedgertemplateXlsx"),
        dialog_title=t("components:ledger.importEquipmentLedger"),
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
