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


def create_file_scan_panel() -> tuple[ft.Container, dict[str, Any]]:
    """创建扫描结果面板并返回操作 refs。

    ``set_result`` 接受 ``func.file_scanner.scan_folder`` 的返回值；
    ``get_selected_matched`` 可直接作为批处理/同步的文件映射。
    """
    rows = ft.Column([], spacing=2, scroll=ft.ScrollMode.AUTO, height=220)
    summary = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    select_all = ft.Checkbox(
        label=t("components:fileScan.enableAll"),
        value=True,
        active_color=theme.PRIMARY,
    )
    state: dict[str, Any] = {
        "result": None,
        "records": [],
        "checks": {},
    }

    def _safe_update(control):
        with contextlib.suppress(RuntimeError, AttributeError):
            control.update()

    def _refresh_summary():
        records = state["records"]
        recognized = [r for r in records if r.get("types")]
        enabled = sum(bool(state["checks"].get(r["path"]) and state["checks"][r["path"]].value) for r in recognized)
        summary.value = t("components:fileScan.selectedCount", selected=enabled, total=len(recognized))
        select_all.value = bool(recognized) and enabled == len(recognized)
        _safe_update(summary)
        _safe_update(select_all)

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
        rows.controls.clear()
        if result:
            for record in state["records"]:
                types = list(record.get("types") or [])
                recognized = bool(types)
                check = ft.Checkbox(
                    value=bool(record.get("selected", recognized)) if recognized else False,
                    disabled=not recognized,
                    on_change=_on_file_change,
                )
                state["checks"][record["path"]] = check
                labels = ", ".join(_type_label(data_type) for data_type in types)
                rows.controls.append(
                    ft.Row(
                        [
                            check,
                            ft.Text(record.get("relative_path") or record.get("name") or record["path"], expand=True, size=12),
                            ft.Text(labels or t("components:fileScan.unrecognized"), size=11, color=theme.PRIMARY if recognized else theme.TEXT_TERTIARY),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
        panel.visible = bool(result)
        _refresh_summary()
        _safe_update(panel)

    def _type_label(data_type: str) -> str:
        key = f"components:fileScan.type.{data_type}"
        label = t(key)
        return data_type if label == key else label

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
                rows,
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
