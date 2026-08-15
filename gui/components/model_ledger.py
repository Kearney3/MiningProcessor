"""型号台账区域组件。"""
import flet as ft

import func.model_ledger as model_ledger
from func.model_ledger import MODEL_LEDGER_COLUMNS

from .ledger_base import LedgerConfig, create_ledger_section_factory
from gui.i18n import t


_MODEL_STANDARD_COLS = [
    ("标准设备编号", t("components:model_ledger.ledgerequipmentLedgerledgerequipmentledger")),
    ("标准公司名称", t("components:model_ledger.modelLedgerledgercompanyname")),
    ("所有权", t("components:model_ledger.itemItemItem")),
    ("设备型号", t("components:model_ledger.equipmentModel")),
    ("设备类型", t("components:model_ledger.equipmentHaulTruckExcavator")),
    ("内部分类", t("components:model_ledger.classificationclassification")),
]


def create_model_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建型号台账区域，返回 (container, refs)。"""
    from func import config_loader

    cfg = LedgerConfig(
        section_title="型号台账",
        display_title=t("components:model_ledger.modelLedger"),
        label_prefix=t("components:model_ledger.modelLedger"),
        empty_icon=getattr(ft.Icons, "ENGINEERING_OUTLINED", ft.Icons.INVENTORY_2_OUTLINED),
        empty_text=t("components:model_ledger.ledgermodelLedgerdata"),
        template_filename="型号台账模板.xlsx",
        dialog_title=t("components:model_ledger.importModelLedger"),
        dialog_height=400,
        backend_module=model_ledger,
        backend_class_name="ModelLedger",
        columns=MODEL_LEDGER_COLUMNS,
        standard_cols=_MODEL_STANDARD_COLS,
        save_cache=config_loader.save_model_ledger_cache,
        load_cache=config_loader.load_model_ledger_cache,
        clear_cache=config_loader.clear_model_ledger_cache,
        has_cache=config_loader.has_model_ledger_cache,
        var_prefix="model_ledger",
    )
    return create_ledger_section_factory(page, log, cfg)
