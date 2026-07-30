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


def _create_keywords_section(page: ft.Page, log):
    """创建文件关键字配置卡片，返回 (card, refs_dict)。"""

    fuel_input, fuel_get, fuel_set = _create_keyword_input(page, "燃油数据", "输入关键字后按回车或点击添加")
    elec_input, elec_get, elec_set = _create_keyword_input(page, "电力数据", "输入关键字后按回车或点击添加")
    prod_input, prod_get, prod_set = _create_keyword_input(page, "生产数据", "输入关键字后按回车或点击添加")
    work_input, work_get, work_set = _create_keyword_input(page, "工时数据", "输入关键字后按回车或点击添加")
    maint_input, maint_get, maint_set = _create_keyword_input(page, "维修数据", "输入关键字后按回车或点击添加")

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
        kw_status_text.value = "文件关键字配置已保存"
        _log_message(log, "已保存文件关键字配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def reset_keywords(_e):
        config_loader.update_user_config({"file_keywords": dict(DEFAULT_FILE_KEYWORDS)})
        _apply_kw_to_ui(DEFAULT_FILE_KEYWORDS)
        kw_status_text.value = "已恢复默认关键字"
        _log_message(log, "已恢复默认文件关键字配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    kw_action_buttons = [
        theme.primary_btn("保存关键字", icon=ft.Icons.SAVE, on_click=save_keywords),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_keywords()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=reset_keywords),
    ]

    keywords_card = theme.make_collapsible(
        title="文件关键字配置",
        subtitle="用于批量处理时自动识别文件夹中的数据文件",
        icon=ft.Icons.KEY,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                "所有类型均按文件名关键字匹配，Sheet 级别识别由各处理器内部完成。点击关键字标签可删除。",
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
