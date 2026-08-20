"""文件关键字配置区域组件。"""
import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from func.config_loader import DEFAULT_FILE_KEYWORDS
from gui.components.common import _log_message
from gui.i18n import t

from ._helpers import _create_keyword_input


def _create_keywords_section(page: ft.Page, log):
    """创建文件关键字配置卡片，返回 (card, refs_dict)。"""

    fuel_input, fuel_get, fuel_set = _create_keyword_input(page, t("components:user_config._keywords.fuelData"), t("components:user_config._keywords.enterAKeywordAndPressEnterOrClickAdd"))
    elec_input, elec_get, elec_set = _create_keyword_input(page, t("components:user_config._keywords.electricalData"), t("components:user_config._keywords.enterAKeywordAndPressEnterOrClickAdd"))
    prod_input, prod_get, prod_set = _create_keyword_input(page, t("components:user_config._keywords.productionData"), t("components:user_config._keywords.enterAKeywordAndPressEnterOrClickAdd"))
    work_input, work_get, work_set = _create_keyword_input(page, t("components:user_config._keywords.worktimeData"), t("components:user_config._keywords.enterAKeywordAndPressEnterOrClickAdd"))
    maint_input, maint_get, maint_set = _create_keyword_input(page, t("components:user_config._keywords.maintenanceData"), t("components:user_config._keywords.enterAKeywordAndPressEnterOrClickAdd"))

    _kw_getters = {
        "fuel": fuel_get, "electrical": elec_get,
        "production": prod_get, "worktime": work_get, "maintenance": maint_get,
    }
    _kw_setters = {
        "fuel": fuel_set, "electrical": elec_set,
        "production": prod_set, "worktime": work_set, "maintenance": maint_set,
    }

    kw_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _apply_kw_to_ui(kw: dict[str, list[str]]):
        for key, setter in _kw_setters.items():
            setter(kw.get(key, []))

    def _collect_kw_from_ui() -> dict[str, list[str]]:
        return {key: getter() for key, getter in _kw_getters.items()}

    def _reload_keywords():
        saved = config_loader.get_user_config("file_keywords", None)
        if saved and isinstance(saved, dict):
            merged = dict(DEFAULT_FILE_KEYWORDS)
            for k, v in saved.items():
                if isinstance(v, list):
                    merged[k] = v
            _apply_kw_to_ui(merged)
        else:
            _apply_kw_to_ui(DEFAULT_FILE_KEYWORDS)
        kw_status_text.value = ""

    def save_keywords(_e):
        kw = _collect_kw_from_ui()
        config_loader.update_user_config({"file_keywords": kw})
        kw_status_text.value = t("components:user_config._keywords.filenameKeywordConfigurationSaved")
        _log_message(log, t("components:user_config._keywords.savedfilenameKeywordConfiguration"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def reset_keywords(_e):
        config_loader.update_user_config({"file_keywords": dict(DEFAULT_FILE_KEYWORDS)})
        _apply_kw_to_ui(DEFAULT_FILE_KEYWORDS)
        kw_status_text.value = t("components:user_config._keywords.restoreddefaultkeyword")
        _log_message(log, t("components:user_config._keywords.restoreddefaultfilenameKeywordConfiguration"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    kw_action_buttons = [
        theme.primary_btn(t("components:user_config._keywords.saveKeywords"), icon=ft.Icons.SAVE, on_click=save_keywords),
        theme.secondary_btn(t("components:user_config._keywords.reload"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload_keywords()),
        theme.secondary_btn(t("components:user_config._keywords.restoreDefault"), icon=ft.Icons.RESTART_ALT, on_click=reset_keywords),
    ]

    keywords_card = theme.make_collapsible(
        title=t("components:user_config._keywords.filenameKeywordConfiguration"),
        subtitle=t("components:user_config._keywords.usedToAutomaticallyIdentifyDataFilesInAFolderDuringBatchProcessing"),
        icon=ft.Icons.KEY,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                t("components:user_config._keywords.matchingtypematchingfilenameKeywordmatchingSheetLevelmatchingprocessingmatchingM"),
                size=12,
                color=theme.TEXT_SECONDARY,
            ),
            fuel_input,
            elec_input,
            prod_input,
            work_input,
            maint_input,
            ft.Row(kw_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            kw_status_text,
        ],
    )

    return keywords_card, {"reload": _reload_keywords, "save": save_keywords, "reset": reset_keywords}
