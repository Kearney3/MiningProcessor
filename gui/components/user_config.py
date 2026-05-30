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


def _make_collapsible(
    title: str,
    subtitle: str,
    content_controls: list,
    icon: str,
    initially_expanded: bool = True,
) -> ft.Container:
    """将内容包装为可折叠的卡片区域。"""
    _open = [initially_expanded]

    body = ft.Container(
        content=ft.Column(content_controls, spacing=8),
        padding=ft.Padding.only(left=12, right=12, bottom=12),
        visible=initially_expanded,
    )

    chevron = ft.Icon(
        ft.Icons.EXPAND_LESS if initially_expanded else ft.Icons.EXPAND_MORE,
        color=theme.TEXT_SECONDARY,
        size=20,
    )

    def _toggle(e):
        _open[0] = not _open[0]
        body.visible = _open[0]
        chevron.name = ft.Icons.EXPAND_LESS if _open[0] else ft.Icons.EXPAND_MORE
        try:
            body.update()
            chevron.update()
        except (RuntimeError, AttributeError):
            pass

    header = ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=theme.PRIMARY, size=18),
                ft.Column(
                    [
                        ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                        ft.Text(subtitle, size=11, color=theme.TEXT_SECONDARY),
                    ],
                    spacing=1,
                    expand=True,
                ),
                chevron,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        on_click=_toggle,
        ink=True,
    )

    return ft.Container(
        content=ft.Column([header, body], spacing=0),
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_MD,
        bgcolor=theme.SURFACE,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


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

    keywords_card = _make_collapsible(
        title="文件关键字配置",
        subtitle="用于批量处理时自动识别文件夹中的数据文件",
        icon=ft.Icons.KEY,
        content_controls=[
            ft.Text(
                "所有类型均按文件名关键字匹配，Sheet 级别识别由各处理器内部完成。多个关键字用英文逗号分隔。",
                size=12,
                color=theme.TEXT_SECONDARY,
            ),
            kw_fuel,
            kw_electrical,
            kw_production,
            kw_worktime,
            ft.Row(kw_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            kw_status_text,
        ],
    )


    # ---------------------------------------------------------------------------
    # 工作效率表头映射配置
    # ---------------------------------------------------------------------------

    _header_mapping_state: list[dict] = []  # [{index: int|None, original: str, new: str}, ...]

    header_rows_column = ft.Column(spacing=4, expand=True)
    header_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    # ── 行构建 ──
    def _build_header_rows():
        controls = []

        # 表头行
        header_labels = ft.Row(
            [
                ft.Text("行号", width=80, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("原始列名", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("匹配列名", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("", width=40),
            ],
            spacing=4,
        )
        controls.append(header_labels)

        for i, entry in enumerate(_header_mapping_state):
            idx = i

            index_field = ft.TextField(
                value=str(entry.get("index", "")) if entry.get("index") is not None else "",
                hint_text="行号",
                width=80,
                text_size=13,
                dense=True,
                input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"),
            )
            orig_field = ft.TextField(
                value=entry.get("original", ""),
                hint_text="原始列名",
                expand=True,
                text_size=13,
                dense=True,
            )
            new_field = ft.TextField(
                value=entry.get("new", ""),
                hint_text="匹配列名",
                expand=True,
                text_size=13,
                dense=True,
            )
            remove_btn = ft.IconButton(
                icon=ft.icons.Icons.DELETE_OUTLINE,
                tooltip="删除此行",
                icon_size=18,
                icon_color=theme.ERROR,
            )

            def _on_index_change(e, _idx=idx):
                val = e.control.value.strip()
                _header_mapping_state[_idx]["index"] = int(val) if val else None

            def _on_orig_change(e, _idx=idx):
                _header_mapping_state[_idx]["original"] = e.control.value

            def _on_new_change(e, _idx=idx):
                _header_mapping_state[_idx]["new"] = e.control.value

            def _on_remove(e, _idx=idx):
                _header_mapping_state.pop(_idx)
                _build_header_rows()

            index_field.on_change = _on_index_change
            orig_field.on_change = _on_orig_change
            new_field.on_change = _on_new_change
            remove_btn.on_click = _on_remove

            row = ft.Row(
                [index_field, orig_field, new_field, remove_btn],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            controls.append(row)

        header_rows_column.controls = controls
        try:
            header_rows_column.update()
        except (RuntimeError, AttributeError):
            pass

    def _add_header_row(e=None):
        _header_mapping_state.append({"index": None, "original": "", "new": ""})
        _build_header_rows()

    def _reload_header_mapping():
        _header_mapping_state.clear()
        config = config_loader.get_worktime_header_mapping()
        for entry in config.get("entries", []):
            _header_mapping_state.append(dict(entry))
        _build_header_rows()
        header_status_text.value = ""

    def _save_header_mapping(e=None):
        # 收集并验证
        entries = []
        indices_seen: dict[int, int] = {}  # index -> row number for error
        originals_seen: dict[str, int] = {}  # original -> row number for error
        has_error = False

        for i, pair in enumerate(_header_mapping_state):
            row_num = i + 1  # 1-based for display
            idx_raw = pair.get("index")
            orig = (pair.get("original") or "").strip()
            new_name = (pair.get("new") or "").strip()

            # 解析行号
            idx_val = None
            if idx_raw is not None:
                try:
                    idx_val = int(idx_raw)
                except (TypeError, ValueError):
                    idx_val = None

            # 跳过完全空行
            if idx_val is None and not orig and not new_name:
                continue

            # 匹配列名必填
            if not new_name:
                header_status_text.value = f"第 {row_num} 行：匹配列名不能为空"
                header_status_text.color = theme.ERROR
                has_error = True
                break

            # 去重检查：行号
            if idx_val is not None:
                if idx_val in indices_seen:
                    header_status_text.value = (
                        f"行号 {idx_val} 重复（第 {indices_seen[idx_val]} 行和第 {row_num} 行）"
                    )
                    header_status_text.color = theme.ERROR
                    has_error = True
                    break
                indices_seen[idx_val] = row_num

            # 去重检查：原始列名
            if orig:
                if orig in originals_seen:
                    header_status_text.value = (
                        f"原始列名「{orig}」重复（第 {originals_seen[orig]} 行和第 {row_num} 行）"
                    )
                    header_status_text.color = theme.ERROR
                    has_error = True
                    break
                originals_seen[orig] = row_num

            entries.append({"index": idx_val, "original": orig, "new": new_name})

        if has_error:
            _log_message(log, header_status_text.value, level=logging.WARNING)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return

        mapping_config = {
            "entries": entries,
        }
        config_loader.save_worktime_header_mapping(mapping_config)

        # 宽松提示：统计各条目适用模式
        pos_only = sum(1 for e in entries if e["index"] is not None and not e["original"])
        name_only = sum(1 for e in entries if e["index"] is None and e["original"])
        both = sum(1 for e in entries if e["index"] is not None and e["original"])
        hints = []
        if pos_only:
            hints.append(f"{pos_only} 条仅按位置有效")
        if name_only:
            hints.append(f"{name_only} 条仅按列名有效")
        if both:
            hints.append(f"{both} 条两种模式均有效")

        hint_text = "；".join(hints) if hints else ""
        status_msg = f"已保存 {len(entries)} 条表头映射"
        if hint_text:
            status_msg += f"（{hint_text}）"
        header_status_text.value = status_msg
        header_status_text.color = theme.WARNING if (pos_only or name_only) and not both else theme.TEXT_SECONDARY
        _log_message(log, f"已保存工作效率表头映射（{len(entries)} 条）")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_header_mapping(e=None):
        config_loader.save_worktime_header_mapping({"entries": config_loader.DEFAULT_WORKTIME_HEADER_MAPPING.get("entries", [])})
        _header_mapping_state.clear()
        _build_header_rows()
        header_status_text.value = "已恢复默认配置"
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已重置工作效率表头映射")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    header_action_buttons = [
        theme.primary_btn("保存映射", icon=ft.icons.Icons.SAVE, on_click=_save_header_mapping),
        theme.secondary_btn("重新加载", icon=ft.icons.Icons.REFRESH, on_click=lambda _: _reload_header_mapping()),
        theme.secondary_btn("恢复默认", icon=ft.icons.Icons.RESTART_ALT, on_click=_reset_header_mapping),
        theme.accent_btn("添加映射", icon=ft.icons.Icons.ADD, on_click=_add_header_row),
    ]

    header_mapping_card = _make_collapsible(
        title="工作效率表头映射配置",
        subtitle="配置行号/原始列名到新列名的映射关系",
        icon=ft.Icons.TABLE_CHART,
        initially_expanded=False,
        content_controls=[
            header_rows_column,
            ft.Row(header_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            header_status_text,
        ],
    )

    action_button_rows = [
        ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
    ]

    database_card = _make_collapsible(
        title="数据库连接配置",
        subtitle="用于配置常用数据库连接信息",
        icon=ft.Icons.STORAGE,
        content_controls=[
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
            ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            status_text,
        ],
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("用户配置"),
                section_hint,
                database_card,
                keywords_card,
                header_mapping_card,
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
        "reload_header_mapping": _reload_header_mapping,
    }

    _reload_database_config()
    _reload_keywords()
    _reload_header_mapping()
    return container, refs
