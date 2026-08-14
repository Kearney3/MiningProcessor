"""设备装载量配置区域组件"""
import json
import logging
from pathlib import Path

import flet as ft

from .common import _log_message, _last_directory, _update_last_directory, PAGE_SIZE, create_confirm_dialog
from .types import ConfigRefs
from gui.i18n import t

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def _device_map_to_rows(device_map: dict) -> list[dict]:
    """将设备装载量字典转换为配置表格行数据。"""
    return [{"selected": False, "device": d, "capacity": c} for d, c in sorted(device_map.items())]


def create_config_section(page: ft.Page, log) -> tuple[ft.Container, "ConfigRefs"]:
    """创建设备装载量配置区域，返回 (container, refs)"""
    from func import config_loader

    config_state: list[dict] = []
    _config_page = [0]
    refs = {}

    def normalize_row(row: dict) -> dict:
        return {
            "selected": bool(row.get("selected", False)),
            "device": str(row.get("device", "")),
            "capacity": str(row.get("capacity", "0")),
        }

    config_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text(t("components:config.选择_153f"))),
            ft.DataColumn(ft.Text(t("components:config.设备型号_5858"))),
            ft.DataColumn(ft.Text(t("components:config.装载量(方)_e3d9"))),
        ],
        rows=[],
        show_checkbox_column=False,
    )

    config_page_label = ft.Text("0 / 0", size=12, color=theme.TEXT_SECONDARY)
    config_prev_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT, tooltip=t("components:config.上一页_f4f8"), icon_size=18, disabled=True,
    )
    config_next_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT, tooltip=t("components:config.下一页_b4e1"), icon_size=18, disabled=True,
    )
    config_pagination = ft.Row(
        [config_prev_btn, config_page_label, config_next_btn],
        spacing=4, alignment=ft.MainAxisAlignment.CENTER,
    )

    _config_empty_state = theme.empty_state(
        ft.Icons.INVENTORY_2_OUTLINED,
        t("components:config.暂无设备配置_b508"),
        t("components:config.点击「添加设备」或「导入配置」_a00c"),
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
                hint_text="方" if not str(row_state["capacity"]).strip() else None,
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
        _config_empty_state.visible = not bool(rows)
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

    # ── 装载量版本切换 ──
    _current_version = [config_loader.get_load_map_version()]

    def _on_version_change(e: ft.ControlEvent):
        selected_values = e.control.selected
        if not selected_values:
            return
        new_ver = selected_values[0]
        if new_ver == _current_version[0]:
            return
        _current_version[0] = new_ver
        config_loader.set_load_map_version(new_ver)
        # 重新加载对应版本的配置
        try:
            device_map = config_loader.get_device_load_map(new_ver)
        except Exception:
            logging.getLogger(__name__).warning(t("components:config.加载配置失败_49fd"), exc_info=True)
            device_map = {}
        set_config_state(_device_map_to_rows(device_map))
        _log_message(log, t("components:config.已切换到装载量配置_1f57", version=t("components:config.旧版_6b10") if new_ver == 'old' else t("components:config.新版_1f09")))

    version_toggle = ft.SegmentedButton(
        selected=["new"] if _current_version[0] == "new" else ["old"],
        segments=[
            ft.Segment(value="new", label=ft.Text(t("components:config.新版配置_2a40"))),
            ft.Segment(value="old", label=ft.Text(t("components:config.旧版配置_5b9e"))),
        ],
        on_change=_on_version_change,
        allow_empty_selection=False,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        ),
    )

    def load_config():
        ver = _current_version[0]
        try:
            device_map = config_loader.get_device_load_map(ver)
        except Exception:
            logging.getLogger(__name__).warning(t("components:config.加载配置失败，使用空配置_1236"), exc_info=True)
            device_map = {}
        set_config_state(_device_map_to_rows(device_map))

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
                _log_message(log, t("components:config.''不是有效数字，跳过_8ebd", cap_text=cap_text, device=device), level=logging.WARNING)
        return device_load_map

    def load_default_config_file(path):
        if not path:
            return
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        imported = data.get("device_load_map", {})
        set_config_state(_device_map_to_rows(imported))

    def save_config_to_path(path):
        if not path:
            return

        device_load_map = build_device_load_map()

        with Path(path).open("w", encoding="utf-8") as f:
            json.dump({"device_load_map": device_load_map}, f, ensure_ascii=False)

    async def save_config(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title=t("components:config.保存配置文件_098d"),
            file_name="device-load-map.json",
            allowed_extensions=["json"],
            initial_directory=_last_directory[0] or None,
        )
        if not path:
            return
        _update_last_directory(path)
        try:
            save_config_to_path(path)
            _log_message(log, t("components:config.配置已另存为:_a25b", path=path))
        except Exception as ex:
            _log_message(log, t("components:config.保存配置失败:_b80a", ex=ex), level=logging.ERROR)

    def _restore_version(version: str, label: str):
        """执行恢复指定版本的默认配置"""
        def handler(e):
            page.pop_dialog()
            try:
                device_map = config_loader.get_default_load_map(version)
                set_config_state(_device_map_to_rows(device_map))
                _log_message(log, t("components:config.已恢复_161d", label=label))
            except Exception as ex:
                _log_message(log, t("components:config.恢复默认配置失败:_7906", ex=ex), level=logging.ERROR)
        return handler

    def restore_default_config(e: ft.ControlEvent):
        version_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(t("components:config.选择默认配置版本_1bfc")),
            content=ft.Column(
                [
                    ft.Text(t("components:config.请选择要恢复的设备装载量配置版_29c7")),
                    ft.Text(t("components:config.新版：当前在用的装载量标准_7b21"), size=12, color=theme.TEXT_SECONDARY),
                    ft.Text(t("components:config.旧版：历史使用的装载量标准_98cf"), size=12, color=theme.TEXT_SECONDARY),
                ],
                spacing=8,
                tight=True,
            ),
            actions=[
                ft.TextButton(t("components:config.取消_625f"), on_click=lambda e: page.pop_dialog()),
                ft.TextButton(t("components:config.旧版配置_5b9e"), on_click=_restore_version("old", t("components:config.旧版默认配置_24ce"))),
                ft.TextButton(t("components:config.新版配置_2a40"), on_click=_restore_version("new", t("components:config.新版默认配置_5da5")),
                              style=ft.ButtonStyle(color=theme.PRIMARY)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(version_dialog)

    def apply_current_config(e: ft.ControlEvent):
        try:
            device_load_map = build_device_load_map()
            config_loader.apply_device_load_map(device_load_map, _current_version[0])
            config_loader.update_device_load_map(device_load_map, _current_version[0])
            _log_message(log, t("components:config.当前配置已应用并保存_960e", version=t("components:config.旧版_6b10") if _current_version[0] == 'old' else t("components:config.新版_1f09")))
        except Exception as ex:
            _log_message(log, t("components:config.应用当前配置失败:_5450", ex=ex), level=logging.ERROR)

    def add_device(e: ft.ControlEvent):
        append_row()

    def _do_remove(e=None):
        page.pop_dialog()
        remove_selected_rows()
        _log_message(log, t("components:config.已删除选中设备配置_a226"))

    confirm_dialog = create_confirm_dialog(
        page, t("components:config.确认删除_631c"),
        t("components:config.确定要删除选中的设备配置吗？此_5bb3"),
        _do_remove, confirm_text=t("components:config.确认删除_631c"),
    )

    def remove_selected(e: ft.ControlEvent):
        selected_count = sum(1 for row in config_state if row["selected"])
        if selected_count == 0:
            _log_message(log, t("components:config.未选中任何设备_1306"), level=logging.WARNING)
            return
        confirm_dialog.content = ft.Text(t("components:config.确定要删除选中的条设备配置吗？_1145", selected_count=selected_count))
        page.show_dialog(confirm_dialog)

    async def import_config(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title=t("components:config.导入配置文件_70bf"),
            allowed_extensions=["json"],
            initial_directory=_last_directory[0] or None,
        )
        if not files:
            return
        path = files[0].path
        _update_last_directory(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            imported = data.get("device_load_map", {})
            if not imported:
                _log_message(log, t("components:config.文件不含device_load_c753"), level=logging.WARNING)
                return
            set_config_state(_device_map_to_rows(imported))
            _log_message(log, t("components:config.已导入条设备装载量配置_7b6e", count=len(imported)))
        except Exception as ex:
            _log_message(log, t("components:config.导入配置失败:_cfd6", ex=ex), level=logging.ERROR)

    _btn_add = theme.primary_btn(t("components:config.添加设备_93d6"), icon=ft.Icons.ADD, on_click=add_device)
    _btn_import = theme.secondary_btn(t("components:config.导入配置_0452"), icon=ft.Icons.FILE_UPLOAD, on_click=import_config)
    _btn_save = theme.secondary_btn(t("components:config.保存配置_ed75"), icon=ft.Icons.SAVE, on_click=save_config)
    _btn_apply = theme.accent_btn(t("components:config.应用当前配置_a495"), icon=ft.Icons.CHECK_CIRCLE, on_click=apply_current_config)
    _btn_reset = theme.secondary_btn(t("components:config.恢复默认_7468"), icon=ft.Icons.RESTART_ALT, on_click=restore_default_config)
    _btn_delete = theme.destructive_btn(t("components:config.删除选中_cd0b"), icon=ft.Icons.DELETE, on_click=remove_selected)

    action_buttons = [_btn_add, _btn_import, _btn_save, _btn_apply, _btn_reset, _btn_delete]
    action_button_rows = [
        ft.Column(
            [
                ft.Row([_btn_add, _btn_import, _btn_save], spacing=8),
                ft.Row([_btn_apply, _btn_reset, _btn_delete], spacing=8),
            ],
            spacing=6,
        ),
    ]

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title(t("components:config.设备装载量配置_c7aa")),
                ft.Row([version_toggle], alignment=ft.MainAxisAlignment.START),
                *action_button_rows,
                ft.Container(
                    content=ft.Stack(
                        [
                            ft.ListView([config_table], expand=True, spacing=5),
                            _config_empty_state,
                        ],
                        expand=True,
                    ),
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
