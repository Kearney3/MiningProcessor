"""MineBase 多连接档案配置区域组件。"""
import contextlib
import logging
import uuid

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


def _profile_summary(profile: dict) -> str:
    """为档案下拉框生成不含密码的摘要。"""
    name = profile.get("name") or t("components:user_config._minebase.unnamedProfile")
    if profile.get("mode") == "database":
        address = profile.get("database", {}).get("host", "")
    else:
        address = profile.get("api", {}).get("url", "")
    return f"{name} · {address or t('components:user_config._minebase.noAddress')}"


def _create_minebase_section(page: ft.Page, log):
    """创建 MineBase 多连接配置卡片，返回 (card, refs_dict)。"""

    mb_profile = ft.Dropdown(
        label=t("components:user_config._minebase.savedProfiles"),
        expand=True,
        options=[],
    )
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
    mb_profile_name = ft.TextField(
        label=t("components:user_config._minebase.profileName"),
        expand=True,
        color=theme.TEXT_PRIMARY,
    )
    mb_api_url = ft.TextField(
        label=t("components:user_config._minebase.apiUrl"),
        hint_text="http://localhost:3000",
        expand=True,
        color=theme.TEXT_PRIMARY,
    )
    mb_api_user = ft.TextField(label=t("components:user_config._minebase.username"), expand=True, color=theme.TEXT_PRIMARY)
    mb_api_pass = ft.TextField(label=t("components:user_config._minebase.password"), password=True, can_reveal_password=True, expand=True)
    # 数据库配置
    mb_db_host = ft.TextField(label=t("components:user_config._minebase.databaseHost"), hint_text="localhost", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_port = ft.TextField(
        label=t("components:user_config._minebase.port"),
        value="5432",
        width=120,
        max_length=5,
        input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"),
    )
    mb_db_name = ft.TextField(label=t("components:user_config._minebase.databaseName"), hint_text="minebase", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_user = ft.TextField(label=t("components:user_config._minebase.username"), expand=True, color=theme.TEXT_PRIMARY)
    mb_db_pass = ft.TextField(label=t("components:user_config._minebase.password"), password=True, can_reveal_password=True, expand=True)

    from func.secret_store import MINEBASE_PASSWORD_MASK as _MASKED

    profiles: list[dict] = []
    _selected_profile_id = ""
    _api_pass_saved = False
    _db_pass_saved = False
    _api_pass_raw = ""
    _db_pass_raw = ""
    mb_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    mb_api_test_btn = theme.secondary_btn(t("components:user_config._minebase.testConnection"), icon=ft.Icons.LAN)
    mb_api_test_result = ft.Text("", size=13, visible=False)
    mb_test_btn = theme.secondary_btn(t("components:user_config._minebase.testConnection"), icon=ft.Icons.LAN)
    mb_test_result = ft.Text("", size=13, visible=False)

    # API / 数据库字段分组容器，按模式显示
    mb_api_fields = ft.Column(
        [
            mb_api_url,
            ft.Row([mb_api_user, mb_api_pass], spacing=8),
            ft.Row([mb_api_test_btn, mb_api_test_result], spacing=8, alignment=ft.MainAxisAlignment.START),
        ],
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
        with contextlib.suppress(RuntimeError, AttributeError):
            mb_api_fields.update()
            mb_db_fields.update()

    def _apply_profile(profile: dict):
        nonlocal _selected_profile_id, _api_pass_saved, _db_pass_saved, _api_pass_raw, _db_pass_raw

        _selected_profile_id = profile.get("id", "")
        mb_profile_name.value = profile.get("name", "")
        mb_mode.value = profile.get("mode", "api")

        api = profile.get("api", {})
        mb_api_url.value = api.get("url", "")
        mb_api_user.value = api.get("username", "")
        api_pass = api.get("password", "")
        _api_pass_saved = bool(api_pass)
        _api_pass_raw = api_pass
        mb_api_pass.value = _MASKED if _api_pass_saved else ""

        database = profile.get("database", {})
        mb_db_host.value = database.get("host", "localhost")
        mb_db_port.value = str(database.get("port", 5432))
        mb_db_name.value = database.get("database", "minebase")
        mb_db_user.value = database.get("user", "postgres")
        db_pass = database.get("password", "")
        _db_pass_saved = bool(db_pass)
        _db_pass_raw = db_pass
        mb_db_pass.value = _MASKED if _db_pass_saved else ""
        _toggle_mb_fields()

    def _current_profile() -> dict | None:
        return next((profile for profile in profiles if profile.get("id") == _selected_profile_id), None)

    def _commit_current_profile() -> None:
        profile = _current_profile()
        if profile is None:
            return

        def _resolve_password(value: str | None, saved: bool, raw: str) -> str:
            if saved and value == _MASKED:
                return raw
            return value or ""

        profile.update({
            "name": (mb_profile_name.value or "").strip() or t("components:user_config._minebase.unnamedProfile"),
            "mode": mb_mode.value or "api",
            "api": {
                "url": (mb_api_url.value or "").strip(),
                "username": (mb_api_user.value or "").strip(),
                "password": _resolve_password(mb_api_pass.value, _api_pass_saved, _api_pass_raw),
            },
            "database": {
                "host": (mb_db_host.value or "").strip() or "localhost",
                "port": int(_normalize_port_text(mb_db_port.value) or "5432"),
                "database": (mb_db_name.value or "").strip() or "minebase",
                "user": (mb_db_user.value or "").strip() or "postgres",
                "password": _resolve_password(mb_db_pass.value, _db_pass_saved, _db_pass_raw),
            },
        })

    def _refresh_profile_options():
        mb_profile.options = [
            ft.dropdown.Option(key=profile.get("id", ""), text=_profile_summary(profile))
            for profile in profiles
        ]
        mb_profile.value = _selected_profile_id
        with contextlib.suppress(RuntimeError, AttributeError):
            mb_profile.update()

    def _apply_mb_config(cfg: dict):
        nonlocal profiles, _selected_profile_id

        raw_profiles = cfg.get("profiles", [])
        profiles = [dict(profile) for profile in raw_profiles] if isinstance(raw_profiles, list) else []
        if not profiles:
            profile = {
                "id": "local-api",
                "name": t("components:user_config._minebase.defaultProfileName"),
                "mode": "api",
                "api": {"url": "http://localhost:3000", "username": "", "password": ""},
                "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
            }
            profiles = [profile]
        _selected_profile_id = cfg.get("active_profile_id") or profiles[0].get("id", "")
        if not any(profile.get("id") == _selected_profile_id for profile in profiles):
            _selected_profile_id = profiles[0].get("id", "")
        _refresh_profile_options()
        profile = _current_profile()
        if profile:
            _apply_profile(profile)

    def _on_profile_select(_e):
        nonlocal _selected_profile_id

        _commit_current_profile()
        _selected_profile_id = mb_profile.value or _selected_profile_id
        profile = _current_profile()
        if profile:
            _apply_profile(profile)

    mb_profile.on_select = _on_profile_select
    mb_mode.on_select = lambda _: _toggle_mb_fields()

    def _add_profile(_e):
        nonlocal _selected_profile_id

        _commit_current_profile()
        profile = {
            "id": f"profile-{uuid.uuid4().hex[:10]}",
            "name": t("components:user_config._minebase.newProfileName"),
            "mode": "api",
            "api": {"url": "http://localhost:3000", "username": "", "password": ""},
            "database": {"host": "localhost", "port": 5432, "database": "minebase", "user": "postgres", "password": ""},
        }
        profiles.append(profile)
        _selected_profile_id = profile["id"]
        _refresh_profile_options()
        _apply_profile(profile)
        mb_status_text.value = t("components:user_config._minebase.newProfileAdded")
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _remove_profile(_e):
        nonlocal profiles, _selected_profile_id

        if len(profiles) <= 1:
            mb_status_text.value = t("components:user_config._minebase.keepOneProfile")
            return
        _commit_current_profile()
        profiles = [profile for profile in profiles if profile.get("id") != _selected_profile_id]
        _selected_profile_id = profiles[0].get("id", "")
        _refresh_profile_options()
        _apply_profile(profiles[0])
        mb_status_text.value = t("components:user_config._minebase.profileRemoved")
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _reload_mb_config():
        cfg = config_loader.get_minebase_config()
        _apply_mb_config(cfg)
        mb_status_text.value = ""

    def _collect_mb_config() -> dict:
        _commit_current_profile()
        return {
            "active_profile_id": _selected_profile_id,
            "profiles": profiles,
        }

    def _save_mb_config(_e):
        cfg = _collect_mb_config()
        for profile in cfg["profiles"]:
            if profile.get("mode") != "database":
                continue
            port_val = int(profile.get("database", {}).get("port", 5432))
            if port_val < 0 or port_val > 65535:
                _sync_port_state(mb_db_port, False, t("components:user_config._minebase.item065535Item"))
                _log_message(log, t("components:user_config._minebase.saveMinebaseConfigurationfailedConfiguration"), level=logging.WARNING)
                return
        _sync_port_state(mb_db_port, True)
        config_loader.save_minebase_config(cfg)
        mb_status_text.value = t("components:user_config._minebase.minebaseConfigurationconfigurationsaved")
        _log_message(log, t("components:user_config._minebase.savedMinebaseConfigurationconfiguration"))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _reset_mb_config(_e):
        defaults = get_minebase_config_default()
        config_loader.save_minebase_config(defaults)
        _apply_mb_config(defaults)
        mb_status_text.value = t("components:user_config._minebase.defaultConfigurationRestored")
        _log_message(log, t("components:user_config._minebase.defaultMinebaseDefaultdefaultconfiguration"))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    mb_add_profile_btn = theme.secondary_btn(
        t("components:user_config._minebase.addProfile"), icon=ft.Icons.ADD, on_click=_add_profile,
    )
    mb_remove_profile_btn = theme.secondary_btn(
        t("components:user_config._minebase.removeProfile"), icon=ft.Icons.DELETE_OUTLINE, on_click=_remove_profile,
    )
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
            ft.Row([mb_profile, mb_add_profile_btn, mb_remove_profile_btn], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([mb_profile_name, mb_mode], spacing=8),
            mb_api_fields,
            mb_db_fields,
            ft.Row(mb_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            mb_status_text,
        ],
    )

    _reload_mb_config()

    return minebase_card, {
        "mb_profile": mb_profile,
        "mb_profile_name": mb_profile_name,
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
        "mb_add_profile_btn": mb_add_profile_btn,
        "mb_remove_profile_btn": mb_remove_profile_btn,
        "mb_api_test_btn": mb_api_test_btn,
        "mb_api_test_result": mb_api_test_result,
        "mb_test_btn": mb_test_btn,
        "mb_test_result": mb_test_result,
        "reload": _reload_mb_config,
        "save": _save_mb_config,
        "reset": _reset_mb_config,
    }
