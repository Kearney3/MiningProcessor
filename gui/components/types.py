"""GUI 组件 refs 类型定义

为 create_*_section 返回的 refs dict 提供类型约束，
在编译期和测试期捕获 key 拼写错误。
"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

import flet as ft


class FuelRefs(TypedDict):
    path: ft.TextField
    year: ft.Dropdown
    btn: ft.Button


class ProdRefs(TypedDict):
    path: ft.TextField
    raw_start: ft.TextField
    btn: ft.Button


class ElecRefs(TypedDict):
    path: ft.TextField
    year: ft.Dropdown
    btn: ft.Button


class WorkRefs(TypedDict):
    path: ft.TextField
    year: ft.Dropdown
    month: ft.Dropdown
    btn: ft.Button


class MergeRefs(TypedDict):
    path: ft.TextField
    keyword: ft.TextField
    strip_time: ft.Checkbox
    btn: ft.Button
    sort_configs_state: list[dict]


class ModuleRefs(TypedDict):
    _match_toggle: ft.Checkbox
    fuel: FuelRefs
    prod: ProdRefs
    elec: ElecRefs
    work: WorkRefs
    merge: MergeRefs


class ConfigRefs(TypedDict):
    config_table: ft.DataTable
    config_state: list[dict]
    load_config: Callable[[], None]
    load_default_config_file: Callable[[Any], None]
    save_config_to_path: Callable[[str], None]
    set_config_state: Callable[[list[dict]], None]
    append_row: Callable[..., None]
    remove_selected_rows: Callable[[], None]
    action_buttons: list[ft.Button]
    action_button_rows: list[ft.Row]


class LedgerRefs(TypedDict):
    ledger_table: ft.DataTable
    ledger_path_label: ft.Text
    ledger_records: list[dict]
    get_ledger: Callable[[], Any]


class OilLedgerRefs(TypedDict):
    oil_table: ft.DataTable
    oil_path_label: ft.Text
    oil_records: list[dict]
    get_oil_ledger: Callable[[], Any]


class LogViewRefs(TypedDict):
    toolbar: ft.Row
    level_filter: ft.Dropdown
    export_button: ft.IconButton
    resize_handle: ft.GestureDetector
    list_container: ft.Container
    log_list: ft.ListView
    _is_at_bottom: list[bool]
