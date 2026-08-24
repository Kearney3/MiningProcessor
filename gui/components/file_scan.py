"""Flet 入口复用的逐文件扫描结果控件。"""

from __future__ import annotations

import contextlib
from typing import Any

import flet as ft

from gui.i18n import t

try:
    from . import theme
except ImportError:
    import gui.theme as theme


PAGE_SIZE = 8
ROW_HEIGHT = 48
ROWS_HEIGHT = PAGE_SIZE * ROW_HEIGHT + (PAGE_SIZE - 1) * 2
ALL_FILTER = "all"
TYPE_ORDER = ("fuel", "electrical", "production", "operation", "worktime")


def _filter_type_key(data_type: str) -> str:
    return "worktime" if data_type == "work_efficiency" else data_type


def create_file_scan_panel() -> tuple[ft.Container, dict[str, Any]]:
    """创建扫描结果面板并返回操作 refs。

    ``set_result`` 接受 ``func.file_scanner.scan_folder`` 的返回值；
    ``get_selected_matched`` 可直接作为批处理/同步的文件映射。
    """
    rows = ft.Column([], spacing=2, height=ROWS_HEIGHT)
    filter_tabs = ft.Row([], spacing=4, scroll=ft.ScrollMode.AUTO)
    summary = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    select_all = ft.Checkbox(
        label=t("components:fileScan.enableAll"),
        value=True,
        active_color=theme.PRIMARY,
    )
    page_label = ft.Text("", size=11, color=theme.TEXT_SECONDARY)
    previous_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT,
        tooltip=t("components:fileScan.previousPage"),
        icon_size=18,
        disabled=True,
    )
    next_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT,
        tooltip=t("components:fileScan.nextPage"),
        icon_size=18,
        disabled=True,
    )
    pagination = ft.Row(
        [page_label, ft.Container(expand=True), previous_btn, next_btn],
        visible=False,
        spacing=2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    state: dict[str, Any] = {
        "result": None,
        "records": [],
        "checks": {},
        "filter": ALL_FILTER,
        "page": 1,
    }

    def _safe_update(control):
        with contextlib.suppress(RuntimeError, AttributeError):
            control.update()

    def _type_label(data_type: str) -> str:
        key = f"components:fileScan.type.{data_type}"
        label = t(key)
        return data_type if label == key else label

    def _filtered_records() -> list[dict[str, Any]]:
        records = state["records"]
        active_filter = state["filter"]
        if active_filter == ALL_FILTER:
            return records
        return [
            record
            for record in records
            if record.get("types")
            and any(_filter_type_key(data_type) == active_filter for data_type in record.get("types") or [])
        ]

    def _filter_options() -> list[tuple[str, str, int]]:
        counts: dict[str, int] = {}
        for record in state["records"]:
            if not record.get("types"):
                continue
            for data_type in {_filter_type_key(value) for value in record.get("types") or []}:
                counts[data_type] = counts.get(data_type, 0) + 1

        def sort_key(data_type: str) -> tuple[int, str]:
            try:
                return TYPE_ORDER.index(data_type), data_type
            except ValueError:
                return len(TYPE_ORDER), data_type

        options = [(ALL_FILTER, t("components:fileScan.allTypes"), len(state["records"]))]
        options.extend(
            (data_type, _type_label(data_type), counts[data_type])
            for data_type in sorted(counts, key=sort_key)
        )
        return options

    def _total_pages() -> int:
        return max(1, (len(_filtered_records()) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _refresh_summary():
        records = state["records"]
        recognized = [r for r in records if r.get("types")]
        enabled = sum(bool(state["checks"].get(r["path"]) and state["checks"][r["path"]].value) for r in recognized)
        summary.value = t("components:fileScan.selectedCount", selected=enabled, total=len(recognized))
        all_selected = bool(recognized) and enabled == len(recognized)
        select_all.value = all_selected
        select_all.label = t("components:fileScan.disableAll" if all_selected else "components:fileScan.enableAll")
        _safe_update(summary)
        _safe_update(select_all)

    def _refresh_pagination():
        total = _total_pages()
        state["page"] = min(max(1, state["page"]), total)
        page_label.value = t(
            "components:fileScan.pageSummary",
            current=state["page"],
            total=total,
            count=len(_filtered_records()),
        )
        pagination.visible = total > 1
        previous_btn.disabled = state["page"] <= 1
        next_btn.disabled = state["page"] >= total
        _safe_update(page_label)
        _safe_update(previous_btn)
        _safe_update(next_btn)
        _safe_update(pagination)

    def _render_rows():
        filtered = _filtered_records()
        start = (state["page"] - 1) * PAGE_SIZE
        page_records = filtered[start:start + PAGE_SIZE]
        rows.controls.clear()
        if not page_records:
            rows.controls.append(
                ft.Container(
                    content=ft.Text(
                        t("components:fileScan.noExcelFiles" if not state["records"] else "components:fileScan.noMatchingFiles"),
                        size=12,
                        color=theme.TEXT_SECONDARY,
                    ),
                    height=ROW_HEIGHT,
                    alignment=ft.Alignment.CENTER,
                )
            )
        for record in page_records:
            types = list(record.get("types") or [])
            recognized = bool(types)
            check = state["checks"].get(record["path"])
            labels = ", ".join(_type_label(data_type) for data_type in types)
            rows.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            check,
                            ft.Text(
                                record.get("relative_path") or record.get("name") or record["path"],
                                expand=True,
                                size=12,
                                no_wrap=True,
                            ),
                            ft.Text(
                                labels or t("components:fileScan.unrecognized"),
                                size=11,
                                color=theme.PRIMARY if recognized else theme.TEXT_TERTIARY,
                                no_wrap=True,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    height=ROW_HEIGHT,
                    alignment=ft.Alignment.CENTER,
                )
            )
        for index in range(max(0, PAGE_SIZE - max(1, len(page_records)))):
            rows.controls.append(ft.Container(height=ROW_HEIGHT))
        _safe_update(rows)

    def _select_filter(filter_type: str):
        state["filter"] = filter_type
        state["page"] = 1
        _render_filters()
        _render_rows()
        _refresh_pagination()

    def _render_filters():
        filter_tabs.controls.clear()
        for filter_type, label, count in _filter_options():
            active = state["filter"] == filter_type
            filter_tabs.controls.append(
                ft.TextButton(
                    f"{label} {count}",
                    on_click=lambda e, value=filter_type: _select_filter(value),
                    style=ft.ButtonStyle(
                        bgcolor=theme.PRIMARY_CONTAINER if active else theme.SURFACE_HIGH,
                        color=theme.PRIMARY_HOVER if active else theme.TEXT_SECONDARY,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_SM),
                    ),
                )
            )
        _safe_update(filter_tabs)

    def _change_page(delta: int):
        total = _total_pages()
        state["page"] = min(max(1, state["page"] + delta), total)
        _render_rows()
        _refresh_pagination()

    previous_btn.on_click = lambda e: _change_page(-1)
    next_btn.on_click = lambda e: _change_page(1)

    def _on_select_all(e):
        for record in state["records"]:
            check = state["checks"].get(record["path"])
            if check is not None and record.get("types"):
                check.value = bool(select_all.value)
                _safe_update(check)
        _refresh_summary()

    select_all.on_change = _on_select_all

    def _on_file_change(e):
        _refresh_summary()

    def set_result(result: dict[str, Any] | None):
        state["result"] = result
        state["records"] = list((result or {}).get("files") or [])
        state["checks"] = {}
        state["filter"] = ALL_FILTER
        state["page"] = 1
        for record in state["records"]:
            types = list(record.get("types") or [])
            recognized = bool(types)
            state["checks"][record["path"]] = ft.Checkbox(
                value=bool(record.get("selected", recognized)) if recognized else False,
                disabled=not recognized,
                on_change=_on_file_change,
            )
        _render_filters()
        _render_rows()
        _refresh_pagination()
        panel.visible = bool(result)
        _refresh_summary()
        _safe_update(panel)

    def get_selected_paths() -> list[str]:
        return [
            record["path"]
            for record in state["records"]
            if record.get("types") and state["checks"].get(record["path"]) and state["checks"][record["path"]].value
        ]

    def get_selected_matched() -> dict[str, list[str]]:
        selected = set(get_selected_paths())
        matched: dict[str, list[str]] = {}
        for record in state["records"]:
            if record.get("path") not in selected:
                continue
            for data_type in record.get("types") or []:
                matched.setdefault(data_type, []).append(record["path"])
        return matched

    def has_scan() -> bool:
        return state["result"] is not None

    def get_result() -> dict[str, Any] | None:
        return state["result"]

    panel = ft.Container(
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SEARCH, size=16, color=theme.TEXT_SECONDARY),
                        ft.Text(t("components:fileScan.scanResults"), size=13, weight=ft.FontWeight.W_500),
                        summary,
                        ft.Container(expand=True),
                        select_all,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=1, color=theme.BORDER),
                ft.Container(filter_tabs, padding=ft.Padding.symmetric(vertical=2)),
                rows,
                pagination,
            ],
            spacing=6,
        ),
        bgcolor=theme.SURFACE_HIGH,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_SM,
        padding=theme.SPACING_SM,
    )

    return panel, {
        "container": panel,
        "set_result": set_result,
        "get_selected_paths": get_selected_paths,
        "get_selected_matched": get_selected_matched,
        "has_scan": has_scan,
        "get_result": get_result,
    }
