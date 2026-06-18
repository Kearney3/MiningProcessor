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
    header_toggle: ft.Checkbox
    header_mode: ft.Dropdown
    header_fuzzy: ft.Checkbox
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
    get_oil: Callable[[], Any]


class LogViewRefs(TypedDict):
    toolbar: ft.Row
    level_filter: ft.Dropdown
    export_button: ft.IconButton
    clear_button: ft.IconButton
    scroll_bottom_button: ft.IconButton
    resize_handle: ft.GestureDetector
    list_container: ft.Container
    log_list: ft.ListView
    _is_at_bottom: list[bool]


class SyncRefs(TypedDict):
    path: ft.TextField
    mode: Any  # ChipToggle
    types: dict[str, ft.Checkbox]
    dry_run: ft.Checkbox
    btn: ft.Button
    result_text: ft.Text
    year: ft.Dropdown
    month: ft.Dropdown
    header_row: ft.TextField
    date_start: ft.TextField
    date_end: ft.TextField


class UserConfigRefs(TypedDict):
    mb_mode: ft.Dropdown
    mb_api_url: ft.TextField
    mb_api_user: ft.TextField
    mb_api_pass: ft.TextField
    mb_db_host: ft.TextField
    mb_db_port: ft.TextField
    mb_db_name: ft.TextField
    mb_db_user: ft.TextField
    mb_db_pass: ft.TextField
    mb_status_text: ft.Text
    mb_action_buttons: list[ft.Button]
    mb_api_test_btn: ft.Button
    mb_api_test_result: ft.Text
    mb_test_btn: ft.Button
    mb_test_result: ft.Text
    reload_mb_config: Callable[[], None]
    save_mb_config: Callable[[Any], None]
    reset_mb_config: Callable[[Any], None]
