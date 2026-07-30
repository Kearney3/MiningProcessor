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
from func.config_loader import DEFAULT_FILE_KEYWORDS, get_minebase_column_mapping, save_minebase_column_mapping, reset_minebase_column_mapping, get_minebase_config_default
from .common import _log_message, safe_update


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


# ---------------------------------------------------------------------------
# 1. 文件关键字配置
# ---------------------------------------------------------------------------

def _create_keyword_input(page: ft.Page, label: str, hint_text: str):
    """创建单个关键字 chip 输入组件，返回 (column, get_keywords, set_keywords)。"""
    _items: list[str] = []
    chips_row = ft.Row(spacing=4, wrap=True, run_spacing=4)
    input_field = ft.TextField(
        hint_text=hint_text,
        expand=True,
        dense=True,
        text_size=13,
        color=theme.TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
        border_color=theme.BORDER,
        focused_border_color=theme.PRIMARY,
    )

    def _rebuild_chips():
        chips_row.controls.clear()
        for i, kw in enumerate(_items):
            idx = i

            def _on_delete(e, _idx=idx):
                _items.pop(_idx)
                _rebuild_chips()
                safe_update(chips_row)

            chip = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(kw, size=12, color=ft.Colors.BLUE_700),
                        ft.Icon(ft.Icons.CLOSE, size=14, color=ft.Colors.BLUE_400),
                    ],
                    spacing=2,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                on_click=_on_delete,
                tooltip="点击删除",
            )
            chips_row.controls.append(chip)
        safe_update(chips_row)

    def _on_add(e=None):
        val = (input_field.value or "").strip()
        if not val:
            return
        _items.append(val)
        input_field.value = ""
        _rebuild_chips()
        safe_update(input_field)

    input_field.on_submit = _on_add
    add_btn = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        tooltip="添加关键字",
        icon_size=22,
        icon_color=theme.PRIMARY,
        on_click=_on_add,
    )

    column = ft.Column(
        [
            ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            chips_row,
            ft.Row([input_field, add_btn], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        spacing=4,
    )

    def get_keywords() -> list[str]:
        return list(_items)

    def set_keywords(items: list[str]):
        _items.clear()
        _items.extend(items)
        _rebuild_chips()

    return column, get_keywords, set_keywords


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


# ---------------------------------------------------------------------------
# 2. 工作效率表头映射配置
# ---------------------------------------------------------------------------

def _create_header_mapping_section(page: ft.Page, log):
    """创建工作效率表头映射配置卡片，返回 (card, refs_dict)。

    与 Tauri 端保持一致的交互模式：
    - 紧凑模式：所有字段只读，整行可点击展开编辑
    - 展开模式：Row1=列号+徽章+新列名+折叠/删除，Row2=关键字 chip 输入
    - 顶部工具栏：搜索 + 保存 + 添加（主操作），重新加载/恢复默认/全部展开折叠（次操作）
    """

    _header_mapping_state: list[dict] = []  # [{index, keywords, new, _kw_get?}, ...]
    _expanded_rows: set[int] = set()
    _search_query: str = ""

    header_content_column = ft.Column(spacing=0, expand=True)
    header_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    # ── 搜索过滤栏 ──
    search_field = ft.TextField(
        hint_text="搜索列名或关键字...",
        expand=True,
        dense=True,
        text_size=13,
        color=theme.TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
        border_color=theme.BORDER,
        focused_border_color=theme.PRIMARY,
        prefix_icon=ft.Icons.SEARCH,
        height=38,
    )

    def _on_search_change(e):
        nonlocal _search_query
        _search_query = (e.control.value or "").strip().lower()
        _build_header_rows()

    search_field.on_change = _on_search_change

    def _matches_search(entry: dict) -> bool:
        if not _search_query:
            return True
        q = _search_query
        if q in (entry.get("new") or "").lower():
            return True
        if any(q in kw.lower() for kw in entry.get("keywords", [])):
            return True
        idx = entry.get("index")
        if idx is not None and q in str(idx):
            return True
        return False

    # ── 行构建 ──
    def _build_header_rows():
        controls = []

        # 表头（与 Tauri grid 对齐：列号 | 匹配 | 关键字 | 新列名 | 操作）
        header_labels = ft.Container(
            content=ft.Row(
                [
                    ft.Text("列号", width=52, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text("匹配", width=56, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text("关键字（名称匹配）", expand=True, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text("新列名", width=140, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text("", width=36),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            bgcolor=theme.SURFACE_LOW,
            border_radius=ft.BorderRadius.only(top_left=8, top_right=8),
        )
        controls.append(header_labels)

        visible_count = 0
        for i, entry in enumerate(_header_mapping_state):
            if not _matches_search(entry):
                continue
            idx = i
            visible_count += 1

            is_expanded = idx in _expanded_rows
            has_index = entry.get("index") is not None
            has_keywords = bool(entry.get("keywords", []))
            match_mode = "位置" if has_index else ("关键字" if has_keywords else "—")

            # 徽章样式（与 Tauri tailwind 色值一致）
            badge_color = ft.Colors.TEAL_100 if has_index else (
                ft.Colors.AMBER_100 if has_keywords else ft.Colors.GREY_100
            )
            badge_text_color = ft.Colors.TEAL_800 if has_index else (
                ft.Colors.AMBER_800 if has_keywords else ft.Colors.GREY_500
            )
            match_badge = ft.Container(
                content=ft.Text(match_mode, size=10, color=badge_text_color, weight=ft.FontWeight.W_500),
                bgcolor=badge_color,
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                width=52,
                alignment=ft.Alignment.CENTER,
            )

            if is_expanded:
                # ── 展开编辑模式 ──
                # Row1: 列号输入 + 徽章 + 新列名输入 + 折叠/删除按钮
                index_field = ft.TextField(
                    value=str(entry.get("index", "")) if entry.get("index") is not None else "",
                    hint_text="从1起",
                    width=52,
                    text_size=13,
                    dense=True,
                    color=theme.TEXT_PRIMARY,
                    hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
                    border_color=theme.BORDER,
                    focused_border_color=theme.PRIMARY,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"),
                )

                def _on_index_change(e, _idx=idx):
                    val = e.control.value.strip()
                    _header_mapping_state[_idx]["index"] = int(val) if val else None

                index_field.on_change = _on_index_change

                new_field = ft.TextField(
                    value=entry.get("new", ""),
                    hint_text="新列名",
                    expand=True,
                    text_size=13,
                    dense=True,
                    color=theme.TEXT_PRIMARY,
                    hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
                    border_color=theme.BORDER,
                    focused_border_color=theme.PRIMARY,
                )

                def _on_new_change(e, _idx=idx):
                    _header_mapping_state[_idx]["new"] = e.control.value

                new_field.on_change = _on_new_change

                # 折叠 + 删除按钮
                fold_btn = ft.IconButton(
                    icon=ft.Icons.EXPAND_LESS,
                    tooltip="折叠",
                    icon_size=16,
                    icon_color=theme.TEXT_SECONDARY,
                )

                def _on_fold(e, _idx=idx):
                    _toggle_expand(_idx)

                fold_btn.on_click = _on_fold

                delete_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="删除此行",
                    icon_size=16,
                    icon_color=theme.ERROR,
                )

                def _on_remove(e, _idx=idx):
                    _header_mapping_state.pop(_idx)
                    _expanded_rows.discard(_idx)
                    _build_header_rows()

                delete_btn.on_click = _on_remove

                # Row2: 关键字 chip 输入
                kw_column, kw_get, kw_set = _create_keyword_input(
                    page, "", "输入关键字后回车添加",
                )
                kw_set(entry.get("keywords", []))
                _header_mapping_state[idx]["_kw_get"] = kw_get

                row_content = ft.Column(
                    [
                        ft.Row(
                            [index_field, match_badge, new_field, fold_btn, delete_btn],
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        kw_column,
                    ],
                    spacing=4,
                    tight=True,
                )
            else:
                # ── 紧凑只读模式（与 Tauri 完全对齐） ──
                index_display = ft.Text(
                    str(entry.get("index", "—")),
                    size=12,
                    width=52,
                    color=theme.TEXT_PRIMARY,
                    text_align=ft.TextAlign.CENTER,
                )

                kw_chips = ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(kw, size=10, color=ft.Colors.BLUE_700),
                            bgcolor=ft.Colors.BLUE_50,
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=1),
                        )
                        for kw in entry.get("keywords", [])
                    ]
                    or [ft.Text("—", size=12, color=theme.TEXT_SECONDARY)],
                    spacing=2,
                    wrap=True,
                    run_spacing=2,
                )

                new_name_display = ft.Text(
                    entry.get("new") or "—",
                    size=12,
                    width=140,
                    color=theme.TEXT_PRIMARY,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )

                expand_hint = ft.Icon(
                    ft.Icons.EXPAND_MORE,
                    size=16,
                    color=theme.TEXT_SECONDARY,
                )

                row_content = ft.Row(
                    [index_display, match_badge, ft.Container(content=kw_chips, expand=True), new_name_display, expand_hint],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )

            # 行背景：交替色 + 展开高亮
            if is_expanded:
                row_bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.BLUE)
            elif visible_count % 2 == 0:
                row_bgcolor = ft.Colors.with_opacity(0.03, theme.TEXT_PRIMARY)
            else:
                row_bgcolor = None

            row_container = ft.Container(
                content=row_content,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4 if not is_expanded else 6),
                bgcolor=row_bgcolor,
                border=ft.Border(bottom=ft.BorderSide(1, theme.BORDER)),
                on_click=lambda e, _idx=idx: _toggle_expand(_idx) if _idx not in _expanded_rows else None,
            )
            controls.append(row_container)

        # 空状态
        if visible_count == 0 and _header_mapping_state:
            controls.append(
                ft.Container(
                    content=ft.Text("没有匹配的映射", size=12, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    padding=ft.Padding.symmetric(vertical=16),
                    alignment=ft.Alignment.CENTER,
                )
            )
        elif not _header_mapping_state:
            controls.append(
                ft.Container(
                    content=ft.Text("暂无映射配置，点击「添加映射」开始", size=12, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    padding=ft.Padding.symmetric(vertical=16),
                    alignment=ft.Alignment.CENTER,
                )
            )

        header_content_column.controls = controls
        try:
            header_content_column.update()
        except (RuntimeError, AttributeError):
            pass

    def _toggle_expand(idx: int):
        if idx in _expanded_rows:
            # 折叠前：保存当前展开行的编辑结果
            kw_getter = _header_mapping_state[idx].get("_kw_get")
            if kw_getter:
                _header_mapping_state[idx]["keywords"] = kw_getter()
            _expanded_rows.discard(idx)
        else:
            _expanded_rows.add(idx)
        _build_header_rows()

    def _add_header_row(e=None):
        _header_mapping_state.append({"index": None, "keywords": [], "new": ""})
        new_idx = len(_header_mapping_state) - 1
        _expanded_rows.add(new_idx)  # 新行自动展开
        _build_header_rows()

    def _expand_all(e=None):
        _expanded_rows.clear()
        _expanded_rows.update(range(len(_header_mapping_state)))
        _build_header_rows()

    def _collapse_all(e=None):
        _expanded_rows.clear()
        _build_header_rows()

    def _reload_header_mapping():
        _header_mapping_state.clear()
        _expanded_rows.clear()
        config = config_loader.get_worktime_header_mapping()
        for entry in config.get("entries", []):
            _header_mapping_state.append(dict(entry))
        _build_header_rows()
        header_status_text.value = ""

    def _save_header_mapping(e=None):
        entries = []
        indices_seen: dict[int, int] = {}
        has_error = False

        for i, pair in enumerate(_header_mapping_state):
            row_num = i + 1
            idx_raw = pair.get("index")
            new_name = (pair.get("new") or "").strip()

            kw_getter = pair.get("_kw_get")
            keywords = kw_getter() if kw_getter else list(pair.get("keywords", []))

            idx_val = None
            if idx_raw is not None:
                try:
                    idx_val = int(idx_raw)
                except (TypeError, ValueError):
                    idx_val = None

            if idx_val is None and not keywords and not new_name:
                continue

            if not new_name:
                header_status_text.value = f"第 {row_num} 行：新列名不能为空"
                header_status_text.color = theme.ERROR
                has_error = True
                break

            if idx_val is not None:
                if idx_val in indices_seen:
                    header_status_text.value = (
                        f"行号 {idx_val} 重复（第 {indices_seen[idx_val]} 行和第 {row_num} 行）"
                    )
                    header_status_text.color = theme.ERROR
                    has_error = True
                    break
                indices_seen[idx_val] = row_num

            entry = {"new": new_name}
            if idx_val is not None:
                entry["index"] = idx_val
            if keywords:
                entry["keywords"] = keywords
            entries.append(entry)

        if has_error:
            _log_message(log, header_status_text.value, level=logging.WARNING)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return

        mapping_config = {"mode": "position", "entries": entries}
        config_loader.save_worktime_header_mapping(mapping_config)

        pos_count = sum(1 for e in entries if "index" in e)
        kw_count = sum(1 for e in entries if e.get("keywords"))
        hints = []
        if pos_count:
            hints.append(f"{pos_count} 条按位置匹配")
        if kw_count:
            hints.append(f"{kw_count} 条按关键字匹配")
        hint_text = "；".join(hints) if hints else ""
        status_msg = f"已保存 {len(entries)} 条表头映射"
        if hint_text:
            status_msg += f"（{hint_text}）"
        header_status_text.value = status_msg
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, f"已保存工作效率表头映射（{len(entries)} 条）")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_header_mapping(e=None):
        cfg = config_loader.load_config()
        default_entries = cfg.get("worktime_header_mapping", {}).get("entries", [])
        config_loader.save_worktime_header_mapping({"entries": default_entries})
        _header_mapping_state.clear()
        _expanded_rows.clear()
        for entry in default_entries:
            _header_mapping_state.append(dict(entry))
        _build_header_rows()
        header_status_text.value = "已恢复默认配置"
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已重置工作效率表头映射")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _clear_header_mapping(e=None):
        config_loader.save_worktime_header_mapping({"entries": []})
        _header_mapping_state.clear()
        _expanded_rows.clear()
        _build_header_rows()
        header_status_text.value = "已清空配置"
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已清空工作效率表头映射配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    # ── 工具栏（与 Tauri 对齐） ──
    toolbar = ft.Row(
        [
            search_field,
            theme.primary_btn("保存", icon=ft.Icons.SAVE, on_click=_save_header_mapping),
            theme.accent_btn("添加映射", icon=ft.Icons.ADD, on_click=_add_header_row),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    secondary_toolbar = ft.Row(
        [
            theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_header_mapping(), height=34),
            theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_header_mapping, height=34),
            theme.secondary_btn("清空配置", icon=ft.Icons.DELETE_SWEEP, on_click=_clear_header_mapping, height=34),
            ft.Container(expand=True),
            theme.secondary_btn("全部展开", icon=ft.Icons.UNFOLD_MORE, on_click=_expand_all, height=34),
            theme.secondary_btn("全部折叠", icon=ft.Icons.UNFOLD_LESS, on_click=_collapse_all, height=34),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    header_mapping_card = theme.make_collapsible(
        title="工作效率表头映射配置",
        subtitle="配置列号（位置匹配）或关键字（名称匹配）到新列名的映射",
        icon=ft.Icons.TABLE_CHART,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                "点击行可展开编辑；关键字默认以标签展示。绿色=位置匹配，黄色=关键字匹配。",
                size=11,
                color=theme.TEXT_SECONDARY,
            ),
            toolbar,
            secondary_toolbar,
            ft.Container(
                content=header_content_column,
                border=ft.Border.all(1, theme.BORDER),
                border_radius=8,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            header_status_text,
        ],
    )

    return header_mapping_card, {"reload": _reload_header_mapping}


# ---------------------------------------------------------------------------
# 3. MineBase 连接配置
# ---------------------------------------------------------------------------

def _create_minebase_section(page: ft.Page, log):
    """创建 MineBase 连接配置卡片，返回 (card, refs_dict)。"""

    mb_mode = ft.Dropdown(
        label="同步模式",
        width=200,
        options=[
            ft.dropdown.Option(key="api", text="API 模式"),
            ft.dropdown.Option(key="database", text="直连数据库"),
        ],
        value="api",
    )
    # API 配置
    mb_api_url = ft.TextField(label="API 地址", hint_text="http://localhost:3000", expand=True, color=theme.TEXT_PRIMARY)
    mb_api_user = ft.TextField(label="用户名", expand=True, color=theme.TEXT_PRIMARY)
    mb_api_pass = ft.TextField(label="密码", password=True, can_reveal_password=True, expand=True)
    # 数据库配置
    mb_db_host = ft.TextField(label="数据库主机", hint_text="localhost", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_port = ft.TextField(label="端口", value="5432", width=120, max_length=5,
                              input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"))
    mb_db_name = ft.TextField(label="数据库名", hint_text="minebase", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_user = ft.TextField(label="用户名", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_pass = ft.TextField(label="密码", password=True, can_reveal_password=True, expand=True)

    from func.secret_store import MINEBASE_PASSWORD_MASK as _MASKED, LLM_KEY_MASK as _LLM_KEY_MASKED
    _api_pass_saved = False  # 是否已有保存的 API 密码
    _db_pass_saved = False   # 是否已有保存的 DB 密码
    _api_pass_raw = ""       # 原始加密密码值
    _db_pass_raw = ""        # 原始加密密码值
    mb_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    mb_api_test_btn = theme.secondary_btn("测试连接", icon=ft.Icons.LAN)
    mb_api_test_result = ft.Text("", size=13, visible=False)
    mb_test_btn = theme.secondary_btn("测试连接", icon=ft.Icons.LAN)
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
            _sync_port_state(mb_db_port, False, "端口必须在 0-65535 之间")
            _log_message(log, "保存 MineBase 配置失败：端口不合法", level=logging.WARNING)
            return
        _sync_port_state(mb_db_port, True)
        cfg = _collect_mb_config()
        config_loader.save_minebase_config(cfg)
        mb_status_text.value = "MineBase 连接配置已保存"
        _log_message(log, "已保存 MineBase 连接配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_mb_config(_e):
        defaults = get_minebase_config_default()
        config_loader.save_minebase_config(defaults)
        _apply_mb_config(defaults)
        mb_status_text.value = "已恢复默认配置"
        _log_message(log, "已恢复 MineBase 默认连接配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    mb_action_buttons = [
        theme.primary_btn("保存配置", icon=ft.Icons.SAVE, on_click=_save_mb_config),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_mb_config()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_mb_config),
    ]

    minebase_card = theme.make_collapsible(
        title="数据库连接配置",
        subtitle="配置 MineBase 数据库同步的连接参数（API / 直连数据库）",
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


# ---------------------------------------------------------------------------
# 4. 列映射配置
# ---------------------------------------------------------------------------

def _create_column_mapping_section(page: ft.Page, log):
    """创建 MineBase 列映射配置卡片，返回 (card, refs_dict)。"""

    _mapping_state: dict[str, dict[str, str]] = {}  # {data_type: {src: dst}}
    _mapping_data_types = ["work_efficiency", "fuel_consumption", "electricity_consumption", "equipment_operation", "production_record"]
    _mapping_type_labels = {
        "work_efficiency": "工作效率",
        "fuel_consumption": "油耗",
        "electricity_consumption": "电耗",
        "equipment_operation": "设备运行",
        "production_record": "生产数据",
    }
    # 每种数据类型对应的 MineBase 目标字段选项（camelCase API 字段名）
    _MINEBASE_FIELD_OPTIONS: dict[str, list[str]] = {
        "work_efficiency": [
            "equipmentName", "equipmentCode", "company", "plannedMinutes", "plannedHours",
            "parkShift", "transfer", "auxiliaryWork", "waitingLoad", "blasting",
            "mealBreak", "refueling", "plannedMaintenance", "unplannedFault", "standby",
            "weatherSnow", "weatherDust", "fillWater", "totalProductionMinutes",
            "powerIssuePlanned", "powerIssueUnplanned", "totalProductionHours", "remark",
        ],
        "fuel_consumption": [
            "date", "shiftType", "equipmentName", "equipmentCode", "fuelName", "consumption",
        ],
        "electricity_consumption": [
            "date", "shiftType", "equipmentName", "consumption",
        ],
        "equipment_operation": [
            "date", "shiftType", "equipmentName", "company",
            "engineHoursStart", "engineHoursEnd", "runningHours",
            "milemeterStart", "milemeterEnd", "mileage", "tripCount",
        ],
        "production_record": [
            "date", "shiftType", "truckName", "excavatorName",
            "materialTypeName", "tripCount", "production",
        ],
    }
    _current_mapping_type = [_mapping_data_types[0]]

    # 每个数据类型维护一个 [(src, dst), ...] 列表，用索引做闭包引用
    _mapping_rows: dict[str, list[list[str]]] = {}

    mapping_type_dropdown = ft.Dropdown(
        label="数据类型",
        width=180,
        options=[ft.dropdown.Option(key=k, text=_mapping_type_labels.get(k, k)) for k in _mapping_data_types],
        value=_mapping_data_types[0],
    )
    mapping_rows_column = ft.Column(spacing=4, expand=True)
    mapping_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _sync_state_from_rows():
        """将当前行列表同步回 _mapping_state（保存前调用）。"""
        for dt, rows in _mapping_rows.items():
            state = {}
            for r in rows:
                if r[0].strip():
                    state[r[0]] = _SKIP if (len(r) > 2 and r[2]) else r[1]
            _mapping_state[dt] = state

    _SKIP = "__SKIP__"

    def _build_mapping_rows():
        controls = []
        dt = _current_mapping_type[0]
        rows = _mapping_rows.get(dt, [])

        # 表头
        controls.append(ft.Row(
            [
                ft.Text("", width=40),
                ft.Text("源列名（Excel 列）", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("目标字段（MineBase）", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("", width=40),
            ],
            spacing=4,
        ))

        for i in range(len(rows)):
            is_excluded = (rows[i][1] == _SKIP)

            src_field = ft.TextField(
                value=rows[i][0], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER, focused_border_color=theme.PRIMARY,
            )
            dst_field = ft.TextField(
                value="" if is_excluded else rows[i][1], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER, focused_border_color=theme.PRIMARY,
                disabled=is_excluded,
            )

            def _on_menu_select(e, _field=dst_field, _idx=i):
                val = e.control.content.value
                _field.value = val
                _field.update()
                rows[_idx][1] = val

            options = _MINEBASE_FIELD_OPTIONS.get(dt, [])
            dst_menu = ft.PopupMenuButton(
                icon=ft.Icons.ARROW_DROP_DOWN,
                tooltip="选择目标字段",
                icon_size=20,
                disabled=is_excluded,
                items=[
                    ft.PopupMenuItem(content=ft.Text(v), on_click=_on_menu_select) for v in options
                ],
            )
            remove_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="删除", icon_size=18, icon_color=theme.ERROR)

            exclude_cb = ft.Checkbox(
                value=is_excluded,
                tooltip="排除此列（不导入）",
                active_color=theme.WARNING,
            )

            def _on_exclude_change(e, _idx=i, _dst=dst_field, _menu=dst_menu):
                excluded = e.control.value
                if excluded:
                    rows[_idx][1] = _SKIP
                    _dst.value = ""
                    _dst.disabled = True
                    _menu.disabled = True
                else:
                    rows[_idx][1] = ""
                    _dst.disabled = False
                    _menu.disabled = False
                _dst.update()
                _menu.update()

            def _on_src_change(e, _idx=i):
                rows[_idx][0] = e.control.value.strip()

            def _on_dst_change(e, _idx=i):
                rows[_idx][1] = e.control.value.strip()

            def _on_remove(e, _idx=i):
                rows.pop(_idx)
                _build_mapping_rows()

            exclude_cb.on_change = _on_exclude_change
            src_field.on_change = _on_src_change
            dst_field.on_change = _on_dst_change
            remove_btn.on_click = _on_remove

            controls.append(ft.Row([exclude_cb, src_field, dst_field, dst_menu, remove_btn], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        mapping_rows_column.controls = controls
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_mapping_type_change(e):
        _current_mapping_type[0] = mapping_type_dropdown.value
        _build_mapping_rows()

    mapping_type_dropdown.on_select = _on_mapping_type_change

    def _add_mapping_row(e=None):
        dt = _current_mapping_type[0]
        if dt not in _mapping_rows:
            _mapping_rows[dt] = []
        _mapping_rows[dt].append(["", "", False])
        _build_mapping_rows()

    def _reload_mapping():
        _mapping_state.clear()
        _mapping_rows.clear()
        data = get_minebase_column_mapping()
        for dt in _mapping_data_types:
            if dt in data:
                _mapping_state[dt] = dict(data[dt])
        # 从 _mapping_state 初始化行列表
        for dt in _mapping_data_types:
            entries = _mapping_state.get(dt, {})
            _mapping_rows[dt] = [[k, v, v == _SKIP] for k, v in entries.items()]
        mapping_status_text.value = ""

    def _save_mapping(e=None):
        # 从行列表同步到 state，清理空键
        _sync_state_from_rows()
        for dt in _mapping_state:
            _mapping_state[dt] = {k: v for k, v in _mapping_state[dt].items() if k.strip()}

        try:
            save_minebase_column_mapping(dict(_mapping_state))
        except Exception as ex:
            mapping_status_text.value = f"保存失败: {ex}"
            mapping_status_text.color = theme.ERROR
            _log_message(log, f"保存列映射配置失败: {ex}", level=logging.ERROR)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return

        total = sum(len(v) for v in _mapping_state.values())
        mapping_status_text.value = f"已保存 {total} 条列映射"
        mapping_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, f"已保存列映射配置（{total} 条）")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_mapping(e=None):
        reset_minebase_column_mapping()
        _reload_mapping()
        mapping_status_text.value = "已恢复默认映射"
        mapping_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已恢复默认列映射配置")
        _build_mapping_rows()
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    mapping_action_buttons = [
        theme.primary_btn("保存映射", icon=ft.Icons.SAVE, on_click=_save_mapping),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: (_reload_mapping(), _build_mapping_rows())),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_mapping),
        theme.accent_btn("添加映射", icon=ft.Icons.ADD, on_click=_add_mapping_row),
    ]

    mapping_card = theme.make_collapsible(
        title="MineBase 列映射配置",
        subtitle="配置 MiningProcessor 输出列到 MineBase 字段的映射关系",
        icon=ft.Icons.MAP,
        initially_expanded=False,
        content_controls=[
            mapping_type_dropdown,
            mapping_rows_column,
            ft.Row(mapping_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            mapping_status_text,
        ],
    )

    return mapping_card, {"reload": _reload_mapping, "build": _build_mapping_rows}


# ---------------------------------------------------------------------------
# 5. 异常值检测配置
# ---------------------------------------------------------------------------

def _create_anomaly_config_section(page: ft.Page, log):
    """创建异常值检测配置卡片，返回 (card, refs_dict)。"""

    from func.anomaly.rules import ALL_NUMERIC_SENTINEL, DEFAULT_THRESHOLDS

    # 数据类型选项
    _DATA_TYPE_OPTIONS = [
        ("fuel", "油耗"),
        ("fuel_engine", "发动机"),
        ("production_running", "运行数据"),
        ("production", "生产数据"),
        ("electrical", "电力消耗"),
        ("worktime", "工时数据"),
    ]

    # 当前选中的数据类型
    _current_type = ["fuel"]

    # 每个数据类型的阈值行：{data_type: [[col, min, max, default], ...]}
    _threshold_rows: dict[str, list[list[str]]] = {}

    # 全局统计参数
    sigma_field = ft.TextField(
        label="σ 倍数", value="3.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text="默认 3.0",
    )
    pct_low_field = ft.TextField(
        label="百分位下限", value="1.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text="默认 1.0",
    )
    pct_high_field = ft.TextField(
        label="百分位上限", value="99.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text="默认 99.0",
    )

    # 检测方法开关
    use_threshold_toggle = ft.Checkbox(
        label="绝对阈值检测", value=True,
        tooltip="基于用户配置的 min/max 范围检测",
    )
    use_sigma_toggle = ft.Checkbox(
        label="σ 异常检测", value=True,
        tooltip="基于标准差的统计离群检测",
    )
    use_percentile_toggle = ft.Checkbox(
        label="百分位检测", value=True,
        tooltip="基于百分位数的极端值检测",
    )

    # --- 逐列检测开关（持久化到用户配置） ---
    _COLUMN_LABELS: dict[str, str] = {
        "fuel": "油耗", "fuel_engine": "发动机",
        "production_running": "运行", "production": "生产",
        "electrical": "电力", "worktime": "工时",
    }
    _COLUMN_DEFS: dict[str, dict[str, list[str]]] = {
        "fuel": {"threshold": ["油品消耗"], "statistical": ["油品消耗"]},
        "fuel_engine": {"threshold": ["发动机小时数开始", "发动机小时数结束", "运行小时数"], "statistical": ["运行小时数"]},
        "production_running": {"threshold": ["运行里程", "运行小时数", "趟次"], "statistical": ["运行里程", "运行小时数", "趟次"]},
        "production": {"threshold": ["趟次", "产量"], "statistical": ["趟次", "产量"]},
        "electrical": {"threshold": ["电力消耗"], "statistical": ["电力消耗"]},
        "worktime": {"threshold": ["__all_numeric__"], "statistical": []},
    }
    column_toggles: dict[str, ft.Checkbox] = {}  # key: "dtype:col"
    column_toggle_rows: dict[str, ft.Row] = {}

    def _build_column_toggles():
        """构建逐列开关 UI。"""
        for dtype in _COLUMN_LABELS:
            cols_cfg = _COLUMN_DEFS.get(dtype, {})
            all_cols = sorted(set(cols_cfg.get("threshold", []) + cols_cfg.get("statistical", [])))
            if not all_cols:
                continue
            cbs: list[ft.Control] = []
            for col in all_cols:
                key = f"{dtype}:{col}"
                label = "全部数值列" if col == "__all_numeric__" else col
                cb = ft.Checkbox(
                    label=label,
                    value=True,
                    visual_density=ft.VisualDensity.COMPACT,
                )
                column_toggles[key] = cb
                cbs.append(
                    ft.Container(
                        content=cb,
                        width=190 if len(label) >= 7 else 140,
                    )
                )
            column_toggle_rows[dtype] = ft.Row(
                cbs,
                wrap=True,
                spacing=8,
                run_spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

    column_toggle_area = ft.Column(spacing=4)
    _build_column_toggles()

    def _show_column_toggles(data_type: str):
        selected_row = column_toggle_rows.get(data_type)
        column_toggle_area.controls = [selected_row] if selected_row else []
        safe_update(column_toggle_area)

    _show_column_toggles(_current_type[0])

    type_segment = ft.SegmentedButton(
        selected=[_current_type[0]],
        segments=[
            ft.Segment(value=key, label=ft.Text(_COLUMN_LABELS[key]))
            for key, _ in _DATA_TYPE_OPTIONS
        ],
        allow_empty_selection=False,
        show_selected_icon=False,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_500),
        ),
    )
    rows_column = ft.Column(spacing=4, expand=True)
    status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _build_rows():
        """根据当前数据类型构建阈值编辑行。"""
        controls = []
        dt = _current_type[0]
        rows = _threshold_rows.get(dt, [])

        # 表头
        controls.append(ft.Row(
            [
                ft.Text("列名 / 标记", expand=True, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("最小值", width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("最大值", width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("默认值", width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY,
                        tooltip="处理异常值时的替换值"),
                ft.Text("", width=40),
            ],
            spacing=4,
        ))

        for i in range(len(rows)):
            idx = i

            col_field = ft.TextField(
                value=rows[idx][0], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="列名或 __all_numeric__",
            )
            min_field = ft.TextField(
                value=rows[idx][1], width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="无下限",
            )
            max_field = ft.TextField(
                value=rows[idx][2], width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="无上限",
            )
            default_field = ft.TextField(
                value=rows[idx][3] if len(rows[idx]) > 3 else "",
                width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="0",
                tooltip="选择「处理异常值」时替换为此值",
            )

            def _on_col_change(e, _idx=idx):
                rows[_idx][0] = e.control.value.strip()

            def _on_min_change(e, _idx=idx):
                rows[_idx][1] = e.control.value.strip()

            def _on_max_change(e, _idx=idx):
                rows[_idx][2] = e.control.value.strip()

            def _on_default_change(e, _idx=idx):
                rows[_idx][3] = e.control.value.strip()

            def _on_remove(e, _idx=idx):
                rows.pop(_idx)
                _build_rows()

            col_field.on_change = _on_col_change
            min_field.on_change = _on_min_change
            max_field.on_change = _on_max_change
            default_field.on_change = _on_default_change
            remove_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, tooltip="删除",
                icon_size=18, icon_color=theme.ERROR, on_click=_on_remove,
            )

            controls.append(ft.Row(
                [col_field, min_field, max_field, default_field, remove_btn],
                spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ))

        rows_column.controls = controls
        safe_update(rows_column)

    def _on_type_change(e):
        selected_values = e.control.selected
        if not selected_values:
            return
        _current_type[0] = selected_values[0]
        _show_column_toggles(_current_type[0])
        _build_rows()

    type_segment.on_change = _on_type_change

    def _add_row(e=None):
        dt = _current_type[0]
        if dt not in _threshold_rows:
            _threshold_rows[dt] = []
        _threshold_rows[dt].append(["", "", "", ""])
        _build_rows()

    def _reload():
        """从配置文件加载。"""
        ad = config_loader.get_anomaly_detection_config()

        # 加载阈值 + 处理规则
        _threshold_rows.clear()
        thresholds = ad.get("thresholds", {})
        handling = ad.get("handling_rules", {})
        for dt, _ in _DATA_TYPE_OPTIONS:
            dt_thresholds = thresholds.get(dt, {})
            dt_handling = handling.get(dt, {})
            rows = []
            for col, bounds in dt_thresholds.items():
                rule = dt_handling.get(col, {})
                default_val = str(rule.get("default", "")) if rule.get("strategy") == "default_value" else ""
                rows.append([
                    col,
                    str(bounds.get("min", "")) if "min" in bounds else "",
                    str(bounds.get("max", "")) if "max" in bounds else "",
                    default_val,
                ])
            _threshold_rows[dt] = rows

        # 加载统计参数
        sigma_field.value = str(ad.get("sigma_n", 3.0))
        pct_low_field.value = str(ad.get("percentile_low", 1.0))
        pct_high_field.value = str(ad.get("percentile_high", 99.0))

        # 加载检测方法开关
        use_threshold_toggle.value = ad.get("use_threshold", True)
        use_sigma_toggle.value = ad.get("use_sigma", True)
        use_percentile_toggle.value = ad.get("use_percentile", True)

        # 加载逐列检测开关
        thresholds_data = ad.get("thresholds", {})
        stat_data = ad.get("statistical_columns", {})
        for key, cb in column_toggles.items():
            dtype, col = key.split(":", 1)
            t_cfg = thresholds_data.get(dtype, {}).get(col, {})
            s_cfg = stat_data.get(dtype, {}).get(col, {})
            t_enabled = t_cfg.get("enabled", True) if isinstance(t_cfg, dict) else True
            s_enabled = s_cfg.get("enabled", True) if isinstance(s_cfg, dict) else True
            cb.value = t_enabled and s_enabled

        status_text.value = ""
        type_segment.selected = [_current_type[0]]
        _show_column_toggles(_current_type[0])
        _build_rows()
        safe_update(sigma_field)
        safe_update(pct_low_field)
        safe_update(pct_high_field)
        safe_update(use_threshold_toggle)
        safe_update(use_sigma_toggle)
        safe_update(use_percentile_toggle)
        safe_update(type_segment)
        for cb in column_toggles.values():
            safe_update(cb)

    def _collect_and_save(_e=None):
        """收集 UI 值并保存。"""
        # 收集阈值 + 处理规则
        thresholds = {}
        handling_rules = {}
        for dt, rows in _threshold_rows.items():
            dt_thresholds = {}
            dt_handling = {}
            for r in rows:
                col = r[0].strip()
                if not col:
                    continue
                # 阈值
                bounds = {}
                if r[1].strip():
                    try:
                        bounds["min"] = float(r[1])
                    except ValueError:
                        pass
                if r[2].strip():
                    try:
                        bounds["max"] = float(r[2])
                    except ValueError:
                        pass
                if bounds:
                    dt_thresholds[col] = bounds
                # 默认值（处理异常值时替换用）
                if len(r) > 3 and r[3].strip():
                    try:
                        dt_handling[col] = {"strategy": "default_value", "default": float(r[3])}
                    except ValueError:
                        dt_handling[col] = {"strategy": "default_value", "default": 0}
            if dt_thresholds:
                thresholds[dt] = dt_thresholds
            if dt_handling:
                handling_rules[dt] = dt_handling

        # 收集统计参数
        try:
            sigma_n = float(sigma_field.value or "3.0")
        except ValueError:
            sigma_n = 3.0
        try:
            pct_low = float(pct_low_field.value or "1.0")
        except ValueError:
            pct_low = 1.0
        try:
            pct_high = float(pct_high_field.value or "99.0")
        except ValueError:
            pct_high = 99.0

        updates = {
            "thresholds": thresholds,
            "handling_rules": handling_rules,
            "sigma_n": sigma_n,
            "percentile_low": pct_low,
            "percentile_high": pct_high,
            "use_threshold": use_threshold_toggle.value,
            "use_sigma": use_sigma_toggle.value,
            "use_percentile": use_percentile_toggle.value,
        }

        # 合并逐列检测开关到 thresholds 和 statistical_columns
        thresholds_out = updates["thresholds"]
        stat_cols_out: dict[str, dict] = {}
        for key, cb in column_toggles.items():
            dtype, col = key.split(":", 1)
            val = cb.value
            # thresholds 中标记 enabled
            if dtype in thresholds_out and col in thresholds_out[dtype]:
                thresholds_out[dtype][col] = {**thresholds_out[dtype][col], "enabled": val}
            elif val is False:
                # 列不在阈值表但被关闭，需记录
                thresholds_out.setdefault(dtype, {})[col] = {"enabled": False}
            # statistical_columns 中标记 enabled
            stat_cols_out.setdefault(dtype, {})[col] = {"enabled": val}
        updates["thresholds"] = thresholds_out
        updates["statistical_columns"] = stat_cols_out
        config_loader.update_anomaly_detection_config(updates)
        status_text.value = "异常值检测配置已保存"
        _log_message(log, "已保存异常值检测配置")
        safe_update(status_text)

    def _reset(_e=None):
        """恢复默认值。"""
        from func.config_loader import DEFAULT_ANOMALY_DETECTION
        config_loader.save_anomaly_detection_config(dict(DEFAULT_ANOMALY_DETECTION))
        _reload()
        status_text.value = "已恢复默认配置"
        _log_message(log, "已恢复异常值检测默认配置")
        safe_update(status_text)

    action_buttons = [
        theme.primary_btn("保存配置", icon=ft.Icons.SAVE, on_click=_collect_and_save),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset),
        theme.accent_btn("添加阈值", icon=ft.Icons.ADD, on_click=_add_row),
    ]

    card = theme.make_collapsible(
        title="异常值检测配置",
        subtitle="配置各数据类型的检测阈值、σ 倍数和百分位范围",
        icon=ft.Icons.TUNE,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                "检测方法：选择启用的检测策略，关闭的策略不会应用。\n"
                "阈值规则对指定列名设置 min/max 范围；"
                f"使用 {ALL_NUMERIC_SENTINEL} 可对所有数值列统一检测。"
                "默认值列仅在启用「处理异常值」模式时生效。",
                size=12, color=theme.TEXT_SECONDARY,
            ),
            ft.Row([use_threshold_toggle, use_sigma_toggle, use_percentile_toggle], spacing=16),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("统计参数", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.Row([sigma_field, pct_low_field, pct_high_field], spacing=12),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("数据类型", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            type_segment,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("逐列检测开关", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.Text(
                "关闭某列的开关后，该列将不参与任何异常检测（阈值、σ、百分位均跳过）。",
                size=11, color=theme.TEXT_SECONDARY,
            ),
            column_toggle_area,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("阈值配置", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            rows_column,
            ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            status_text,
        ],
    )

    return card, {
        "reload": _reload,
        "type_segment": type_segment,
        "column_toggle_area": column_toggle_area,
        "column_toggle_rows": column_toggle_rows,
        "rows_column": rows_column,
    }


# ---------------------------------------------------------------------------
# 6. LLM 标注配置
# ---------------------------------------------------------------------------

def _create_llm_config_section(page: ft.Page, log):
    """创建 LLM 标注配置卡片，返回 (card, refs_dict)。"""

    llm_url = ft.TextField(label="接口 URL", hint_text="https://api.example.com/v1", expand=True, color=theme.TEXT_PRIMARY)
    llm_api_key = ft.TextField(label="API Key", password=True, can_reveal_password=True, expand=True, color=theme.TEXT_PRIMARY)
    llm_model = ft.Dropdown(label="模型", expand=True, options=[], hint_text="点击「获取模型」加载列表")
    llm_format = ft.Dropdown(
        label="接口格式",
        width=160,
        options=[
            ft.dropdown.Option("openai", "OpenAI 兼容"),
            ft.dropdown.Option("anthropic", "Anthropic"),
        ],
        value="openai",
    )
    llm_status = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    llm_test_result = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    llm_verify_result = ft.Text("", size=12)
    from func.secret_store import LLM_KEY_MASK as _LLM_KEY_MASKED
    _llm_key_saved = False

    def _on_api_key_change(_e):
        nonlocal _llm_key_saved
        if llm_api_key.value != _LLM_KEY_MASKED:
            _llm_key_saved = False

    llm_api_key.on_change = _on_api_key_change

    def _apply_llm_to_ui(cfg: dict):
        nonlocal _llm_key_saved
        llm_url.value = cfg.get("url", "")
        raw_key = cfg.get("api_key", "")
        if raw_key:
            llm_api_key.value = _LLM_KEY_MASKED
            _llm_key_saved = True
        else:
            llm_api_key.value = ""
            _llm_key_saved = False
        llm_model.value = cfg.get("model", "") or None
        llm_format.value = cfg.get("format", "openai")
        llm_status.value = ""
        llm_test_result.value = ""

    def _reload_llm():
        cfg = config_loader.get_llm_config()
        _apply_llm_to_ui(cfg)
        if cfg.get("model") and not any(o.key == cfg["model"] for o in llm_model.options):
            llm_model.options.append(ft.dropdown.Option(cfg["model"]))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _resolve_api_key() -> str:
        val = (llm_api_key.value or "").strip()
        if _llm_key_saved and val == _LLM_KEY_MASKED:
            return ""  # 后端从持久化配置加载真实密钥
        return val

    def _fetch_models(_e):
        cfg = {
            "url": (llm_url.value or "").strip(),
            "api_key": _resolve_api_key(),
            "format": llm_format.value or "openai",
        }
        if not cfg["url"]:
            llm_test_result.value = "请先填写接口 URL"
            llm_test_result.color = ft.Colors.RED
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return
        llm_test_result.value = "正在获取模型列表..."
        llm_test_result.color = theme.TEXT_SECONDARY
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

        def _do_fetch():
            result = config_loader.test_llm_connection(cfg)
            def _update():
                if result["success"]:
                    models = result["models"]
                    llm_model.options = [ft.dropdown.Option(m) for m in models]
                    if models and not llm_model.value:
                        llm_model.value = models[0]
                    llm_test_result.value = f"获取到 {len(models)} 个模型"
                    llm_test_result.color = theme.TEXT_PRIMARY
                    _log_message(log, f"获取到 {len(models)} 个可用模型")
                else:
                    llm_test_result.value = f"连接失败: {result['error']}"
                    llm_test_result.color = ft.Colors.RED
                    _log_message(log.error, f"LLM 接口连接失败: {result['error']}")
                try:
                    page.update()
                except (RuntimeError, AttributeError):
                    pass
            _update()

        import threading
        threading.Thread(target=_do_fetch, daemon=True).start()

    def _save_llm(_e):
        api_key_val = llm_api_key.value or ""
        if _llm_key_saved and api_key_val == _LLM_KEY_MASKED:
            api_key_val = ""  # 未修改，后端跳过加密保留已有凭据
        updates = {
            "url": (llm_url.value or "").strip(),
            "api_key": api_key_val.strip(),
            "model": llm_model.value or "",
            "format": llm_format.value or "openai",
        }
        config_loader.update_llm_config(updates)
        # 重新加载以同步掩码状态
        _reload_llm()
        llm_status.value = "LLM 配置已保存"
        _log_message(log, "已保存 LLM 标注配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_llm(_e):
        config_loader.update_user_config({"llm_labeling": {}})
        _reload_llm()
        llm_status.value = "已恢复默认配置"
        _log_message(log, "已重置 LLM 标注配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    fetch_btn = theme.secondary_btn("获取模型", icon=ft.Icons.REFRESH, on_click=_fetch_models)

    def _verify_connection(_e):
        cfg = {
            "url": (llm_url.value or "").strip(),
            "api_key": _resolve_api_key(),
            "format": llm_format.value or "openai",
        }
        if not cfg["url"]:
            llm_verify_result.value = "⚠ 请先填写接口 URL"
            llm_verify_result.color = ft.Colors.AMBER
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return
        llm_verify_result.value = "正在验证..."
        llm_verify_result.color = theme.TEXT_SECONDARY
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

        def _do_verify():
            result = config_loader.test_llm_connection(cfg)
            selected_model = (llm_model.value or "").strip()

            def _update():
                if result["success"]:
                    models = result["models"]
                    if selected_model and selected_model not in models:
                        llm_verify_result.value = (
                            f"⚠ 连接成功，但所选模型「{selected_model}」"
                            f"不在可用列表中（共 {len(models)} 个模型）"
                        )
                        llm_verify_result.color = ft.Colors.AMBER
                    else:
                        model_info = f"，模型「{selected_model}」可用" if selected_model else ""
                        llm_verify_result.value = f"✓ 连接成功（{len(models)} 个模型可用{model_info}）"
                        llm_verify_result.color = ft.Colors.GREEN
                else:
                    llm_verify_result.value = f"✗ 连接失败: {result['error']}"
                    llm_verify_result.color = ft.Colors.RED
                try:
                    page.update()
                except (RuntimeError, AttributeError):
                    pass

            _update()

        import threading
        threading.Thread(target=_do_verify, daemon=True).start()

    verify_btn = theme.secondary_btn("验证连接", icon=ft.Icons.CHECK_CIRCLE, on_click=_verify_connection)
    action_buttons = [
        theme.primary_btn("保存配置", icon=ft.Icons.SAVE, on_click=_save_llm),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_llm()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_llm),
    ]

    llm_card = theme.make_collapsible(
        title="LLM 标注配置",
        subtitle="配置大模型接口用于维修记录智能标注",
        icon=ft.Icons.SMART_TOY,
        initially_expanded=False,
        content_controls=[
            ft.Row([llm_format, fetch_btn, verify_btn], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            llm_url,
            llm_api_key,
            llm_model,
            llm_verify_result,
            llm_test_result,
            ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            llm_status,
        ],
    )

    return llm_card, {
        "reload": _reload_llm,
        "save": _save_llm,
        "reset": _reset_llm,
    }


# ---------------------------------------------------------------------------
# 主组装函数
# ---------------------------------------------------------------------------

def create_user_config_section(page: ft.Page, log) -> tuple[ft.Container, "UserConfigRefs"]:
    """创建用户配置页面，返回 (container, refs)。"""

    section_hint = ft.Text(
        "这里用于管理与业务处理无关的个人偏好设置。",
        size=13,
        color=theme.TEXT_SECONDARY,
    )

    keywords_card, kw_refs = _create_keywords_section(page, log)
    header_mapping_card, hm_refs = _create_header_mapping_section(page, log)
    minebase_card, mb_refs = _create_minebase_section(page, log)
    mapping_card, map_refs = _create_column_mapping_section(page, log)
    anomaly_card, anomaly_refs = _create_anomaly_config_section(page, log)
    llm_card, llm_refs = _create_llm_config_section(page, log)

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("用户配置"),
                section_hint,
                llm_card,
                minebase_card,
                keywords_card,
                header_mapping_card,
                mapping_card,
                anomaly_card,
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
        "mb_mode": mb_refs["mb_mode"],
        "mb_api_url": mb_refs["mb_api_url"],
        "mb_api_user": mb_refs["mb_api_user"],
        "mb_api_pass": mb_refs["mb_api_pass"],
        "mb_db_host": mb_refs["mb_db_host"],
        "mb_db_port": mb_refs["mb_db_port"],
        "mb_db_name": mb_refs["mb_db_name"],
        "mb_db_user": mb_refs["mb_db_user"],
        "mb_db_pass": mb_refs["mb_db_pass"],
        "mb_status_text": mb_refs["mb_status_text"],
        "mb_action_buttons": mb_refs["mb_action_buttons"],
        "mb_api_test_btn": mb_refs["mb_api_test_btn"],
        "mb_api_test_result": mb_refs["mb_api_test_result"],
        "mb_test_btn": mb_refs["mb_test_btn"],
        "mb_test_result": mb_refs["mb_test_result"],
        "reload_mb_config": mb_refs["reload"],
        "save_mb_config": mb_refs["save"],
        "reset_mb_config": mb_refs["reset"],
        "reload_keywords": kw_refs["reload"],
        "reload_header_mapping": hm_refs["reload"],
        "reload_llm_config": llm_refs["reload"],
    }

    llm_refs["reload"]()
    kw_refs["reload"]()
    hm_refs["reload"]()
    mb_refs["reload"]()
    map_refs["reload"]()
    map_refs["build"]()
    anomaly_refs["reload"]()
    return container, refs
