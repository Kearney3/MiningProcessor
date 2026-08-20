"""MineBase 连接配置区域组件。"""
import logging

import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from func.config_loader import get_minebase_config_default
from gui.components.common import _log_message
from gui.i18n import t

from ._helpers import _normalize_port_text, _sync_port_state


def _create_minebase_section(page: ft.Page, log):
    """创建 MineBase 连接配置卡片，返回 (card, refs_dict)。"""

    mb_mode = ft.Dropdown(
        label=t("components:user_config._minebase.syncMode"),
        width=200,
        options=[
            ft.dropdown.Option(key="api", text=t("components:user_config._minebase.apiMode")),
            ft.dropdown.Option(key="database", text=t("components:user_config._minebase.directDb")),
        ],
        value="api",
    )
    # API 配置
    mb_api_url = ft.TextField(label=t("components:user_config._minebase.apiUrl"), hint_text="http://localhost:3000", expand=True, color=theme.TEXT_PRIMARY)
    mb_api_user = ft.TextField(label=t("components:user_config._minebase.username"), expand=True, color=theme.TEXT_PRIMARY)
    mb_api_pass = ft.TextField(label=t("components:user_config._minebase.password"), password=True, can_reveal_password=True, expand=True)
    # 数据库配置
    mb_db_host = ft.TextField(label=t("components:user_config._minebase.databaseHost"), hint_text="localhost", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_port = ft.TextField(label=t("components:user_config._minebase.port"), value="5432", width=120, max_length=5,
                              input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"))
    mb_db_name = ft.TextField(label=t("components:user_config._minebase.databaseName"), hint_text="minebase", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_user = ft.TextField(label=t("components:user_config._minebase.username"), expand=True, color=theme.TEXT_PRIMARY)
    mb_db_pass = ft.TextField(label=t("components:user_config._minebase.password"), password=True, can_reveal_password=True, expand=True)

    from func.secret_store import MINEBASE_PASSWORD_MASK as _MASKED
    _api_pass_saved = False  # 是否已有保存的 API 密码
    _db_pass_saved = False   # 是否已有保存的 DB 密码
    _api_pass_raw = ""       # 原始加密密码值
    _db_pass_raw = ""        # 原始加密密码值
    mb_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    mb_api_test_btn = theme.secondary_btn(t("components:user_config._minebase.testConnection"), icon=ft.Icons.LAN)
    mb_api_test_result = ft.Text("", size=13, visible=False)
    mb_test_btn = theme.secondary_btn(t("components:user_config._minebase.testConnection"), icon=ft.Icons.LAN)
    mb_test_result = ft.Text("", size=13, visible=False)

    # API / 数据库字段分组容器，按模式显示
    mb_api_fields = ft.Column(
        [mb_api_url, ft.Row([mb_api_user, mb_api_pass], spacing=8),
         ft.Row([mb_api_test_btn, mb_api_test_result], spacing=8, alignment=ft.MainAxisAlignment.START)],
        spacing=8,
    )
    mb_db_fields = ft.Column(
        [
            ft.Row([mb_db_host, mb_db_port], spacing=8),
            mb_db_name,
            ft.Row([mb_db_user, mb_db_pass], spacing=8),
            ft.Row([mb_test_btn, mb_test_result], spacing=8, alignment=ft.MainAxisAlignment.START),
        ],
        spacing=8,
    )

    def _toggle_mb_fields():
        is_api = mb_mode.value == "api"
        mb_api_fields.visible = is_api
        mb_db_fields.visible = not is_api
        try:
            mb_api_fields.update()
            mb_db_fields.update()
        except (RuntimeError, AttributeError):
            pass

    mb_mode.on_select = lambda _: _toggle_mb_fields()

    def _apply_mb_config(cfg: dict):
        from func.secret_store import _ENCRYPTED_PREFIX

        nonlocal _api_pass_saved, _db_pass_saved, _api_pass_raw, _db_pass_raw

        mb_mode.value = cfg.get("mode", "api")
        api = cfg.get("api", {})
        mb_api_url.value = api.get("url", "")
        mb_api_user.value = api.get("username", "")
        api_pass = api.get("password", "")
        if api_pass.startswith(_ENCRYPTED_PREFIX) or api_pass:
            mb_api_pass.value = _MASKED
            _api_pass_saved = True
            _api_pass_raw = api_pass
        else:
            mb_api_pass.value = ""
            _api_pass_saved = False
            _api_pass_raw = ""

        db = cfg.get("database", {})
        mb_db_host.value = db.get("host", "")
        mb_db_port.value = str(db.get("port", 5432))
        mb_db_name.value = db.get("database", "")
        mb_db_user.value = db.get("user", "")
        db_pass = db.get("password", "")
        if db_pass.startswith(_ENCRYPTED_PREFIX) or db_pass:
            mb_db_pass.value = _MASKED
            _db_pass_saved = True
            _db_pass_raw = db_pass
        else:
            mb_db_pass.value = ""
            _db_pass_saved = False
            _db_pass_raw = ""
        _toggle_mb_fields()

    def _collect_mb_config() -> dict:
        def _resolve_pass(field_value: str, is_saved: bool, raw_value: str) -> str:
            """如果字段值是掩码且已有保存密码，返回原始加密值保留原密码。"""
            if is_saved and field_value == _MASKED:
                return raw_value
            return field_value or ""

        return {
            "mode": mb_mode.value or "api",
            "api": {
                "url": (mb_api_url.value or "").strip(),
                "username": (mb_api_user.value or "").strip(),
                "password": _resolve_pass(mb_api_pass.value, _api_pass_saved, _api_pass_raw),
            },
            "database": {
                "host": (mb_db_host.value or "").strip() or "localhost",
                "port": int(_normalize_port_text(mb_db_port.value) or "5432"),
                "database": (mb_db_name.value or "").strip() or "minebase",
                "user": (mb_db_user.value or "").strip() or "postgres",
                "password": _resolve_pass(mb_db_pass.value, _db_pass_saved, _db_pass_raw),
            },
        }

    def _reload_mb_config():
        cfg = config_loader.get_minebase_config()
        _apply_mb_config(cfg)
        mb_status_text.value = ""

    def _save_mb_config(_e):
        port_val = int(_normalize_port_text(mb_db_port.value) or "5432")
        if port_val < 0 or port_val > 65535:
            _sync_port_state(mb_db_port, False, t("components:user_config._minebase.item065535Item"))
            _log_message(log, t("components:user_config._minebase.saveMinebaseConfigurationfailedConfiguration"), level=logging.WARNING)
            return
        _sync_port_state(mb_db_port, True)
        cfg = _collect_mb_config()
        config_loader.save_minebase_config(cfg)
        mb_status_text.value = t("components:user_config._minebase.minebaseConfigurationconfigurationsaved")
        _log_message(log, t("components:user_config._minebase.savedMinebaseConfigurationconfiguration"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_mb_config(_e):
        defaults = get_minebase_config_default()
        config_loader.save_minebase_config(defaults)
        _apply_mb_config(defaults)
        mb_status_text.value = t("components:user_config._minebase.defaultConfigurationRestored")
        _log_message(log, t("components:user_config._minebase.defaultMinebaseDefaultdefaultconfiguration"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    mb_action_buttons = [
        theme.primary_btn(t("components:user_config._minebase.saveConfig"), icon=ft.Icons.SAVE, on_click=_save_mb_config),
        theme.secondary_btn(t("components:user_config._minebase.reload"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload_mb_config()),
        theme.secondary_btn(t("components:user_config._minebase.restoreDefault"), icon=ft.Icons.RESTART_ALT, on_click=_reset_mb_config),
    ]

    minebase_card = theme.make_collapsible(
        title=t("components:user_config._minebase.databaseConnection"),
        subtitle=t("components:user_config._minebase.configureMinebaseSynchronizationConnectionParametersApiDirectDatabase"),
        icon=ft.Icons.STORAGE,
        initially_expanded=False,
        content_controls=[
            mb_mode,
            mb_api_fields,
            mb_db_fields,
            ft.Row(mb_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            mb_status_text,
        ],
    )

    # 启动时自动加载已保存的配置（含 Keychain 密码解密）
    _reload_mb_config()

    return minebase_card, {
        "mb_mode": mb_mode,
        "mb_api_url": mb_api_url,
        "mb_api_user": mb_api_user,
        "mb_api_pass": mb_api_pass,
        "mb_db_host": mb_db_host,
        "mb_db_port": mb_db_port,
        "mb_db_name": mb_db_name,
        "mb_db_user": mb_db_user,
        "mb_db_pass": mb_db_pass,
        "mb_status_text": mb_status_text,
        "mb_action_buttons": mb_action_buttons,
        "mb_api_test_btn": mb_api_test_btn,
        "mb_api_test_result": mb_api_test_result,
        "mb_test_btn": mb_test_btn,
        "mb_test_result": mb_test_result,
        "reload": _reload_mb_config,
        "save": _save_mb_config,
        "reset": _reset_mb_config,
    }
