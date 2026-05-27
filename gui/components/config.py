"""设备装载量配置区域组件"""
import json
import logging
from pathlib import Path

import flet as ft

from .common import _log_message
from .types import ConfigRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_config_section(page: ft.Page, log) -> tuple[ft.Container, "ConfigRefs"]:
    """创建设备装载量配置区域，返回 (container, refs)"""
    from func import config_loader

    PAGE_SIZE = 20
    config_state: list[dict] = []
    _config_page = [0]
    _last_directory = [""]  # 记住上次文件选择器的目录
    refs = {}

    def normalize_row(row: dict) -> dict:
        return {
            "selected": bool(row.get("selected", False)),
            "device": str(row.get("device", "")),
            "capacity": str(row.get("capacity", "0")),
        }

    config_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("选择")),
            ft.DataColumn(ft.Text("设备型号")),
            ft.DataColumn(ft.Text("装载量 (方)")),
        ],
        rows=[],
        show_checkbox_column=False,
    )

    config_page_label = ft.Text("0 / 0", size=12, color=theme.TEXT_SECONDARY)
    config_prev_btn = ft.IconButton(
        icon=ft.icons.Icons.CHEVRON_LEFT, tooltip="上一页", icon_size=18, disabled=True,
    )
    config_next_btn = ft.IconButton(
        icon=ft.icons.Icons.CHEVRON_RIGHT, tooltip="下一页", icon_size=18, disabled=True,
    )
    config_pagination = ft.Row(
        [config_prev_btn, config_page_label, config_next_btn],
        spacing=4, alignment=ft.MainAxisAlignment.CENTER,
    )

    def _config_total_pages():
        return max(1, (len(config_state) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_config_page_controls():
        total = _config_total_pages()
        cur = _config_page[0]
        config_page_label.value = f"{cur + 1} / {total}"
        config_prev_btn.disabled = cur <= 0
        config_next_btn.disabled = cur >= total - 1

    def build_table():
        start = _config_page[0] * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = list(enumerate(config_state))[start:end]

        rows = []
        for index, row_state in page_items:
            checkbox = ft.Checkbox(value=row_state["selected"])
            device_field = ft.TextField(
                value=row_state["device"],
                text_size=13,
                hint_text="设备型号" if not row_state["device"] else None,
                border_color=ft.Colors.TRANSPARENT,
                focused_border_color=theme.PRIMARY,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
            )
            capacity_field = ft.TextField(
                value=str(row_state["capacity"]),
                text_size=13,
                width=80,
                hint_text="吨" if not str(row_state["capacity"]).strip() else None,
                border_color=ft.Colors.TRANSPARENT,
                focused_border_color=theme.PRIMARY,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
            )

            def on_checkbox_change(e: ft.ControlEvent, idx=index):
                config_state[idx]["selected"] = bool(e.control.value)

            def on_device_change(e: ft.ControlEvent, idx=index):
                config_state[idx]["device"] = e.control.value

            def on_capacity_change(e: ft.ControlEvent, idx=index):
                config_state[idx]["capacity"] = e.control.value

            checkbox.on_change = on_checkbox_change
            device_field.on_change = on_device_change
            capacity_field.on_change = on_capacity_change

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(checkbox),
                        ft.DataCell(device_field),
                        ft.DataCell(capacity_field),
                    ]
                )
            )

        config_table.rows = rows
        _update_config_page_controls()
        page.update()

    def set_config_state(rows: list[dict]):
        nonlocal config_state
        config_state = [normalize_row(row) for row in rows]
        refs["config_state"] = config_state
        _config_page[0] = 0
        build_table()

    def append_row(device: str = "", capacity: int | str = 0):
        config_state.append(normalize_row({"selected": False, "device": device, "capacity": capacity}))
        _config_page[0] = _config_total_pages() - 1
        build_table()

    def remove_selected_rows():
        nonlocal config_state
        config_state = [row for row in config_state if not row["selected"]]
        refs["config_state"] = config_state
        if _config_page[0] >= _config_total_pages():
            _config_page[0] = max(0, _config_total_pages() - 1)
        build_table()

    def _config_prev(e):
        if _config_page[0] > 0:
            _config_page[0] -= 1
            build_table()

    def _config_next(e):
        if _config_page[0] < _config_total_pages() - 1:
            _config_page[0] += 1
            build_table()

    config_prev_btn.on_click = _config_prev
    config_next_btn.on_click = _config_next

    def load_config():
        try:
            device_map = config_loader.get_device_load_map()
        except Exception:
            logging.getLogger(__name__).warning("加载配置失败，使用空配置", exc_info=True)
            device_map = {}
        set_config_state(
            [
                {"selected": False, "device": device, "capacity": cap}
                for device, cap in sorted(device_map.items())
            ]
        )

    def build_device_load_map() -> dict[str, int]:
        device_load_map = {}
        for row in config_state:
            device = row["device"]
            cap_text = row["capacity"]
            if not device or not cap_text:
                continue
            try:
                device_load_map[device] = int(cap_text)
            except (TypeError, ValueError):
                _log_message(log, f"'{cap_text}' 不是有效数字，跳过 {device}", level=logging.WARNING)
        return device_load_map

    def load_default_config_file(path):
        if not path:
            return
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        imported = data.get("device_load_map", {})
        set_config_state(
            [
                {"selected": False, "device": device, "capacity": cap}
                for device, cap in sorted(imported.items())
            ]
        )

    def save_config_to_path(path):
        if not path:
            return

        device_load_map = build_device_load_map()

        with Path(path).open("w", encoding="utf-8") as f:
            json.dump({"device_load_map": device_load_map}, f, ensure_ascii=False)

    async def save_config(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title="保存配置文件",
            file_name="device-load-map.json",
            allowed_extensions=["json"],
            initial_directory=_last_directory[0] or None,
        )
        if not path:
            return
        _last_directory[0] = str(Path(path).parent)
        try:
            save_config_to_path(path)
            _log_message(log, f"配置已另存为: {path}")
        except Exception as ex:
            _log_message(log, f"保存配置失败: {ex}", level=logging.ERROR)

    def restore_default_config(e: ft.ControlEvent):
        try:
            load_default_config_file(config_loader.get_config_file_path())
            _log_message(log, "已恢复默认配置")
        except Exception as ex:
            _log_message(log, f"恢复默认配置失败: {ex}", level=logging.ERROR)

    def apply_current_config(e: ft.ControlEvent):
        try:
            config_loader.apply_device_load_map(build_device_load_map())
            _log_message(log, "当前配置已应用")
        except Exception as ex:
            _log_message(log, f"应用当前配置失败: {ex}", level=logging.ERROR)

    def add_device(e: ft.ControlEvent):
        append_row()

    def remove_selected(e: ft.ControlEvent):
        remove_selected_rows()

    async def import_config(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="导入配置文件",
            allowed_extensions=["json"],
            initial_directory=_last_directory[0] or None,
        )
        if not files:
            return
        path = files[0].path
        _last_directory[0] = str(Path(path).parent)
        try:
            import json as _json
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            imported = data.get("device_load_map", {})
            if not imported:
                _log_message(log, "文件不含 device_load_map", level=logging.WARNING)
                return
            set_config_state(
                [
                    {"selected": False, "device": device, "capacity": cap}
                    for device, cap in sorted(imported.items())
                ]
            )
            _log_message(log, f"已导入 {len(imported)} 条设备装载量配置")
        except Exception as ex:
            _log_message(log, f"导入配置失败: {ex}", level=logging.ERROR)

    action_buttons = [
        theme.primary_btn("添加设备", icon=ft.icons.Icons.ADD, on_click=add_device),
        theme.secondary_btn("导入配置", icon=ft.icons.Icons.FILE_UPLOAD, on_click=import_config),
        theme.secondary_btn("保存配置", icon=ft.icons.Icons.SAVE, on_click=save_config),
        ft.Container(width=16),
        theme.accent_btn("应用当前配置", icon=ft.icons.Icons.CHECK_CIRCLE, on_click=apply_current_config),
        theme.secondary_btn("恢复默认", icon=ft.icons.Icons.RESTART_ALT, on_click=restore_default_config),
        ft.Container(width=16),
        theme.destructive_btn("删除选中", icon=ft.icons.Icons.DELETE, on_click=remove_selected),
    ]
    action_button_rows = [
        ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
    ]

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("设备装载量配置"),
                *action_button_rows,
                ft.Container(
                    content=ft.ListView([config_table], expand=True, spacing=5),
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    expand=True,
                    bgcolor=theme.SURFACE_HIGH,
                ),
                config_pagination,
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

    refs = {
        "config_table": config_table,
        "config_state": config_state,
        "load_config": load_config,
        "load_default_config_file": load_default_config_file,
        "save_config_to_path": save_config_to_path,
        "set_config_state": set_config_state,
        "append_row": append_row,
        "remove_selected_rows": remove_selected_rows,
        "action_buttons": action_buttons,
        "action_button_rows": action_button_rows,
    }
    return container, refs
