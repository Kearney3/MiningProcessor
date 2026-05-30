"""用户自定义配置区域组件（优化后的表单布局与错误处理）"""
import logging
import re

import flet as ft

from .types import UserConfigRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from func.config_loader import DEFAULT_FILE_KEYWORDS
from .common import _log_message

_DB_SECTION = "database"

DEFAULT_DB_CONFIG: dict[str, str | int] = {
    "db_type": "",
    "db_host": "localhost",
    "db_port": 3306,
    "db_name": "",
    "db_user": "",
    "db_password": "",
}

DB_TYPE_OPTIONS = [
    ft.dropdown.Option(key="mysql", text="MySQL"),
    ft.dropdown.Option(key="postgres", text="PostgreSQL"),
    ft.dropdown.Option(key="sqlite", text="SQLite"),
    ft.dropdown.Option(key="sqlserver", text="SQL Server"),
    ft.dropdown.Option(key="oracle", text="Oracle"),
    ft.dropdown.Option(key="", text="未指定"),
]


def _current_db_config() -> dict[str, str | int]:
    saved = config_loader.get_user_config(_DB_SECTION, {}) or {}
    merged = dict(DEFAULT_DB_CONFIG)
    merged.update({k: v for k, v in saved.items() if k in DEFAULT_DB_CONFIG})
    return merged


def _sync_port_state(port_field: ft.TextField, is_valid: bool, message: str = ""):
    """统一端口字段的边框和提示状态。"""
    port_field.border_color = ft.Colors.RED if not is_valid else theme.BORDER
    port_field.error_text = message or None
    try:
        port_field.update()
    except (RuntimeError, AttributeError):
        pass


def _normalize_port_text(value: str | None) -> str:
    return re.sub(r"\D+", "", (value or "").strip())


def create_user_config_section(page: ft.Page, log) -> tuple[ft.Container, "UserConfigRefs"]:
    """创建用户配置页面，返回 (container, refs)。"""

    section_hint = ft.Text(
        "这里用于管理与业务处理无关的个人偏好设置，当前先支持常用数据库连接配置。",
        size=13,
        color=theme.TEXT_SECONDARY,
    )

    db_type = ft.Dropdown(
        label="数据库类型",
        width=240,
        options=DB_TYPE_OPTIONS,
        value="",
    )
    db_host = ft.TextField(label="数据库位置", hint_text="例如 127.0.0.1", expand=True)
    db_port = ft.TextField(
        label="端口",
        value="3306",
        width=120,
        max_length=5,
        counter="",
        input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"),
    )
    db_name = ft.TextField(label="数据库名称", hint_text="例如 mining_data", expand=True)
    db_user = ft.TextField(label="用户名", expand=True)
    db_password = ft.TextField(
        label="密码",
        password=True,
        can_reveal_password=True,
        expand=True,
    )

    status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _apply_db_config_to_ui(cfg: dict[str, str | int]):
        db_type.value = str(cfg.get("db_type", ""))
        db_host.value = str(cfg.get("db_host", ""))
        db_port.value = str(cfg.get("db_port", ""))
        db_name.value = str(cfg.get("db_name", ""))
        db_user.value = str(cfg.get("db_user", ""))
        db_password.value = str(cfg.get("db_password", ""))
        _sync_port_state(db_port, True)
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _collect_db_config_from_ui() -> dict[str, str | int]:
        port_text = _normalize_port_text(db_port.value)
        port_value = int(port_text) if port_text else 0
        return {
            "db_type": (db_type.value or "").strip(),
            "db_host": (db_host.value or "").strip(),
            "db_port": port_value,
            "db_name": (db_name.value or "").strip(),
            "db_user": (db_user.value or "").strip(),
            "db_password": db_password.value or "",
        }

    def _reload_database_config():
        _apply_db_config_to_ui(_current_db_config())
        status_text.value = ""
        _sync_port_state(db_port, True)

    def save_database_config(_e):
        port_text = _normalize_port_text(db_port.value)
        port_value = int(port_text) if port_text else -1
        if port_value < 0 or port_value > 65535:
            _sync_port_state(db_port, False, "端口必须在 0-65535 之间")
            _log_message(log, "保存数据库配置失败：端口不合法", level=logging.WARNING)
            return

        db_port.value = str(port_value)
        db_cfg = _collect_db_config_from_ui()
        config_loader.update_user_config({_DB_SECTION: db_cfg})

        _sync_port_state(db_port, True)
        status_text.value = "数据库连接配置已保存"
        _log_message(log, "已保存数据库连接配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def reset_database_config(_e):
        config_loader.update_user_config({_DB_SECTION: dict(DEFAULT_DB_CONFIG)})
        _apply_db_config_to_ui(DEFAULT_DB_CONFIG)
        status_text.value = "已恢复数据库默认配置"
        _log_message(log, "已恢复数据库默认配置")
        page.snack_bar = ft.SnackBar(ft.Text("已恢复数据库默认配置"))
        page.snack_bar.open = True
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    action_buttons = [
        theme.primary_btn("保存数据库配置", icon=ft.icons.Icons.SAVE, on_click=save_database_config),
        theme.secondary_btn("重新加载", icon=ft.icons.Icons.REFRESH, on_click=lambda _: _reload_database_config()),
        theme.secondary_btn("恢复默认", icon=ft.icons.Icons.RESTART_ALT, on_click=reset_database_config),
    ]

    # ── 文件关键字配置 ──────────────────────────────────────────
    kw_fuel = ft.TextField(label="燃油数据", hint_text="例如: 设备柴油消耗,Техник", expand=True)
    kw_electrical = ft.TextField(label="电力数据", hint_text="例如: Electrical", expand=True)
    kw_production = ft.TextField(label="生产数据", hint_text="例如: 白班,夜班", expand=True)
    kw_worktime = ft.TextField(label="工时数据", hint_text="例如: 工时", expand=True)
    kw_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _kw_defaults() -> dict[str, str]:
        return {k: ",".join(v) for k, v in DEFAULT_FILE_KEYWORDS.items()}

    def _apply_kw_to_ui(kw: dict[str, list[str]]):
        kw_fuel.value = ",".join(kw.get("fuel", []))
        kw_electrical.value = ",".join(kw.get("electrical", []))
        kw_production.value = ",".join(kw.get("production", []))
        kw_worktime.value = ",".join(kw.get("worktime", []))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _collect_kw_from_ui() -> dict[str, list[str]]:
        def _split(text: str) -> list[str]:
            return [s.strip() for s in (text or "").split(",") if s.strip()]
        return {
            "fuel": _split(kw_fuel.value),
            "electrical": _split(kw_electrical.value),
            "production": _split(kw_production.value),
            "worktime": _split(kw_worktime.value),
        }

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
        theme.primary_btn("保存关键字", icon=ft.icons.Icons.SAVE, on_click=save_keywords),
        theme.secondary_btn("重新加载", icon=ft.icons.Icons.REFRESH, on_click=lambda _: _reload_keywords()),
        theme.secondary_btn("恢复默认", icon=ft.icons.Icons.RESTART_ALT, on_click=reset_keywords),
    ]

    keywords_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("文件关键字配置", size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                ft.Text(
                    "用于批量处理时自动识别文件夹中的数据文件。多个关键字用英文逗号分隔，匹配时为「包含任意一个即匹配」。",
                    size=12,
                    color=theme.TEXT_SECONDARY,
                ),
                ft.Text("所有类型均按文件名关键字匹配，Sheet 级别识别由各处理器内部完成。", size=12, color=theme.TEXT_SECONDARY),
                kw_fuel,
                kw_electrical,
                kw_production,
                kw_worktime,
                ft.Row(kw_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
                kw_status_text,
            ],
            spacing=8,
        ),
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_MD,
        padding=12,
        bgcolor=theme.SURFACE,
    )

    action_button_rows = [
        ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
    ]

    database_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("数据库连接配置", size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                ft.Text(
                    "用于配置常用数据库连接信息，后续新增配置项可继续在本页扩展。",
                    size=12,
                    color=theme.TEXT_SECONDARY,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(db_type, col={"xs": 12, "md": 5}),
                        ft.Container(db_port, col={"xs": 12, "md": 3}),
                    ],
                    run_spacing=8,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                db_host,
                ft.ResponsiveRow(
                    [
                        ft.Container(db_name, col={"xs": 12, "md": 6}),
                        ft.Container(db_user, col={"xs": 12, "md": 6}),
                    ],
                    run_spacing=8,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                db_password,
                status_text,
            ],
            spacing=8,
        ),
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_MD,
        padding=12,
        bgcolor=theme.SURFACE,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("用户配置"),
                section_hint,
                *action_button_rows,
                database_card,
                keywords_card,
            ],
            spacing=8,
            expand=True,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    refs: UserConfigRefs = {
        "db_type": db_type,
        "db_host": db_host,
        "db_port": db_port,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "status_text": status_text,
        "action_buttons": action_buttons,
        "action_button_rows": action_button_rows,
        "reload_database_config": _reload_database_config,
        "save_database_config": save_database_config,
        "reset_database_config": reset_database_config,
        "reload_keywords": _reload_keywords,
    }

    _reload_database_config()
    _reload_keywords()
    return container, refs
