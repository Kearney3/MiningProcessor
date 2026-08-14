"""文件关键字配置区域组件。"""
import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from func.config_loader import DEFAULT_FILE_KEYWORDS
from gui.components.common import _log_message

from ._helpers import _create_keyword_input
from gui.i18n import t


def _create_keywords_section(page: ft.Page, log):
    """创建文件关键字配置卡片，返回 (card, refs_dict)。"""

    fuel_input, fuel_get, fuel_set = _create_keyword_input(page, t("components:user_config._keywords.燃油数据_f769"), t("components:user_config._keywords.输入关键字后按回车或点击添加_45a8"))
    elec_input, elec_get, elec_set = _create_keyword_input(page, t("components:user_config._keywords.电力数据_2456"), t("components:user_config._keywords.输入关键字后按回车或点击添加_45a8"))
    prod_input, prod_get, prod_set = _create_keyword_input(page, t("components:user_config._keywords.生产数据_9fb6"), t("components:user_config._keywords.输入关键字后按回车或点击添加_45a8"))
    work_input, work_get, work_set = _create_keyword_input(page, t("components:user_config._keywords.工时数据_8c32"), t("components:user_config._keywords.输入关键字后按回车或点击添加_45a8"))
    maint_input, maint_get, maint_set = _create_keyword_input(page, t("components:user_config._keywords.维修数据_ba9e"), t("components:user_config._keywords.输入关键字后按回车或点击添加_45a8"))

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
        kw_status_text.value = t("components:user_config._keywords.文件关键字配置已保存_73b3")
        _log_message(log, t("components:user_config._keywords.已保存文件关键字配置_e565"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def reset_keywords(_e):
        config_loader.update_user_config({"file_keywords": dict(DEFAULT_FILE_KEYWORDS)})
        _apply_kw_to_ui(DEFAULT_FILE_KEYWORDS)
        kw_status_text.value = t("components:user_config._keywords.已恢复默认关键字_bb96")
        _log_message(log, t("components:user_config._keywords.已恢复默认文件关键字配置_fe90"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    kw_action_buttons = [
        theme.primary_btn(t("components:user_config._keywords.保存关键字_f436"), icon=ft.Icons.SAVE, on_click=save_keywords),
        theme.secondary_btn(t("components:user_config._keywords.重新加载_64ca"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload_keywords()),
        theme.secondary_btn(t("components:user_config._keywords.恢复默认_7468"), icon=ft.Icons.RESTART_ALT, on_click=reset_keywords),
    ]

    keywords_card = theme.make_collapsible(
        title=t("components:user_config._keywords.文件关键字配置_c38a"),
        subtitle=t("components:user_config._keywords.用于批量处理时自动识别文件夹中_9d40"),
        icon=ft.Icons.KEY,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                t("components:user_config._keywords.所有类型均按文件名关键字匹配，_f0c5"),
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
