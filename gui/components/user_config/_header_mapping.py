"""工作效率表头映射配置区域组件。"""
import logging

import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from gui.components.common import _log_message
from gui.i18n import t

from ._helpers import _create_keyword_input


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
        hint_text=t("components:user_config.columnkeyword"),
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
                    ft.Text(t("components:user_config._header_mapping.columnNumber"), width=52, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text(t("components:user_config._header_mapping.matching"), width=56, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text(t("components:user_config._header_mapping.keywordNameMatching"), expand=True, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
                    ft.Text(t("components:user_config._header_mapping.newColumnName"), width=140, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
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
            match_mode = t("components:user_config._header_mapping.position") if has_index else (t("components:user_config._header_mapping.keyword") if has_keywords else "—")

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
                    hint_text=t("components:user_config._header_mapping.startingAt1"),
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
                    hint_text=t("components:user_config._header_mapping.newColumnName"),
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
                    tooltip=t("components:user_config._header_mapping.collapse"),
                    icon_size=16,
                    icon_color=theme.TEXT_SECONDARY,
                )

                def _on_fold(e, _idx=idx):
                    _toggle_expand(_idx)

                fold_btn.on_click = _on_fold

                delete_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip=t("components:user_config._header_mapping.deleteThisRow"),
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
                    page, "", t("components:user_config._header_mapping.enterAKeywordAndPressEnterToAdd"),
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
                    content=ft.Text(t("components:user_config._header_mapping.noMatchingMappings"), size=12, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    padding=ft.Padding.symmetric(vertical=16),
                    alignment=ft.Alignment.CENTER,
                )
            )
        elif not _header_mapping_state:
            controls.append(
                ft.Container(
                    content=ft.Text(t("components:user_config._header_mapping.noMappingRulesClickAddMappingToBegin"), size=12, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
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
                header_status_text.value = t("components:user_config._header_mapping.columnColumnNewColumnNamecolumn", row_num=row_num)
                header_status_text.color = theme.ERROR
                has_error = True
                break

            if idx_val is not None:
                if idx_val in indices_seen:
                    header_status_text.value = t(
                        "components:user_config._header_mapping.itemItemItemItemItem", idx_val=idx_val, first_row=indices_seen[idx_val], row_num=row_num
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
            hints.append(t("components:user_config._header_mapping.itemsbyPositionmatching", pos_count=pos_count))
        if kw_count:
            hints.append(t("components:user_config._header_mapping.itemsmatchingkeywordmatching", kw_count=kw_count))
        hint_text = "；".join(hints) if hints else ""
        status_msg = t("components:user_config._header_mapping.savedItemsconfiguration", count=len(entries))
        if hint_text:
            status_msg += f"（{hint_text}）"
        header_status_text.value = status_msg
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, t("components:user_config._header_mapping.savedworktimeHeaderMappingItems", count=len(entries)))
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
        header_status_text.value = t("components:user_config._header_mapping.defaultConfigurationRestored")
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, t("components:user_config._header_mapping.worktimeHeaderMappingReset"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _clear_header_mapping(e=None):
        config_loader.save_worktime_header_mapping({"entries": []})
        _header_mapping_state.clear()
        _expanded_rows.clear()
        _build_header_rows()
        header_status_text.value = t("components:user_config._header_mapping.configurationclearconfiguration")
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, t("components:user_config._header_mapping.configurationclearconfigurationconfiguration"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    # ── 工具栏（与 Tauri 对齐） ──
    toolbar = ft.Row(
        [
            search_field,
            theme.primary_btn(t("components:user_config._header_mapping.save"), icon=ft.Icons.SAVE, on_click=_save_header_mapping),
            theme.accent_btn(t("components:user_config._header_mapping.addMapping"), icon=ft.Icons.ADD, on_click=_add_header_row),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    secondary_toolbar = ft.Row(
        [
            theme.secondary_btn(t("components:user_config._header_mapping.reload"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload_header_mapping(), height=34),
            theme.secondary_btn(t("components:user_config._header_mapping.restoreDefault"), icon=ft.Icons.RESTART_ALT, on_click=_reset_header_mapping, height=34),
            theme.secondary_btn(t("components:user_config._header_mapping.clearConfiguration"), icon=ft.Icons.DELETE_SWEEP, on_click=_clear_header_mapping, height=34),
            ft.Container(expand=True),
            theme.secondary_btn(t("components:user_config._header_mapping.expandAll"), icon=ft.Icons.UNFOLD_MORE, on_click=_expand_all, height=34),
            theme.secondary_btn(t("components:user_config._header_mapping.collapseAll"), icon=ft.Icons.UNFOLD_LESS, on_click=_collapse_all, height=34),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    header_mapping_card = theme.make_collapsible(
        title=t("components:user_config._header_mapping.configurationconfiguration"),
        subtitle=t("components:user_config._header_mapping.configurationcolumnNumberPositionmatchingConfigurationkeywordNameMatchingConfigu"),
        icon=ft.Icons.TABLE_CHART,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                t("components:user_config._header_mapping.selectARowToEditGreenMeansPositionMatchYellowMeansKeywordMatch"),
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
