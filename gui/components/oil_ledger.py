"""油品台账区域组件"""
import flet as ft

import func.oil_ledger as oil_ledger
from func.oil_ledger import OIL_LEDGER_COLUMNS

from .ledger_base import LedgerConfig, create_ledger_section_factory
from gui.i18n import t


_OIL_LEDGER_STANDARD_COLS = [
    ("油品名称", t("components:oil_ledger.matchingnameMatchingmatching")),
    ("标准油品名称", t("components:oil_ledger.fuelname")),
]


def create_oil_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建油品台账区域，返回 (container, refs)"""
    from func import config_loader

    cfg = LedgerConfig(
        section_title=t("components:oil_ledger.oilLedger"),
        label_prefix=t("components:oil_ledger.oilLedger"),
        empty_icon=ft.Icons.OIL_BARREL_OUTLINED,
        empty_text=t("components:oil_ledger.ledgeroilLedgerdata"),
        template_filename=t("components:oil_ledger.oilLedgertemplateXlsx"),
        dialog_title=t("components:oil_ledger.importOilLedger"),
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
