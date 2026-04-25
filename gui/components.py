"""
GUI 组件工厂函数
提供各区域 UI 组件的创建接口
"""
import json
import os
from datetime import datetime
from pathlib import Path

import flet as ft
import equipment_ledger


# ---------------------------------------------------------------------------
# 台账区域
# ---------------------------------------------------------------------------
def create_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建设备台账区域，返回 (container, refs)"""
    ledger_records = []
    ledger_path_label = ft.Text("未加载台账", size=12, color=ft.Colors.GREY)
    ledger_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("设备编号")),
            ft.DataColumn(ft.Text("标准设备名称")),
            ft.DataColumn(ft.Text("设备类型")),
            ft.DataColumn(ft.Text("所属公司")),
        ],
        rows=[],
    )

    def build_table(records):
        ledger_table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(str(r.get(c, "")))) for c in
                       ["设备编号", "标准设备名称", "设备类型", "所属公司"]]
            )
            for r in records
        ]
        page.update()

    async def on_load(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="导入设备台账",
            allowed_extensions=["xlsx", "xls"],
        )
        if not files:
            return
        path = files[0].path
        try:
            ledger = equipment_ledger.EquipmentLedger(path)
            nonlocal ledger_records
            ledger_records = ledger.to_dict()
            ledger_path_label.value = os.path.basename(path)
            ledger_path_label.color = ft.Colors.GREEN
            build_table(ledger_records)
            log(f"已加载台账: {path}")
        except Exception as ex:
            ledger_path_label.value = f"加载失败: {ex}"
            ledger_path_label.color = ft.Colors.RED
            log(f"加载台账失败: {ex}")
        page.update()

    async def on_export_template(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.save_file(
            dialog_title="导出模板",
            file_name="设备台账模板.xlsx",
            allowed_extensions=["xlsx"],
        )
        if not path:
            return
        try:
            ledger = equipment_ledger.EquipmentLedger()
            ledger.export_template(path)
            log(f"已导出模板: {path}")
        except Exception as ex:
            log(f"导出模板失败: {ex}")
        page.update()

    container = ft.Container(
        content=ft.Column(
            [
                ft.Text("设备台账", size=18, weight=ft.FontWeight.W_600),
                ft.Row(
                    [
                        ft.Button(
                            "导入台账",
                            icon=ft.icons.Icons.UPLOAD,
                            on_click=on_load,
                        ),
                        ft.Button(
                            "导出模板",
                            icon=ft.icons.Icons.DOWNLOAD,
                            on_click=on_export_template,
                        ),
                        ledger_path_label,
                    ],
                    spacing=10,
                ),
                ft.Container(
                    content=ft.ListView([ledger_table], height=180, spacing=5),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=5,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
    )

    refs = {
        "ledger_table": ledger_table,
        "ledger_path_label": ledger_path_label,
        "ledger_records": ledger_records,
    }
    return container, refs


# ---------------------------------------------------------------------------
# 配置区域
# ---------------------------------------------------------------------------
def create_config_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建设备装载量配置区域，返回 (container, refs)"""
    import asyncio
    import config_loader

    config_state: list[dict] = []
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

    def build_table():
        rows = []
        for index, row_state in enumerate(config_state):
            checkbox = ft.Checkbox(value=row_state["selected"])
            device_field = ft.TextField(
                value=row_state["device"],
                text_size=13,
                hint_text="设备型号" if not row_state["device"] else None,
                border_color="transparent",
            )
            capacity_field = ft.TextField(
                value=str(row_state["capacity"]),
                text_size=13,
                width=80,
                hint_text="吨" if not str(row_state["capacity"]).strip() else None,
                border_color="transparent",
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
        page.update()

    def set_config_state(rows: list[dict]):
        nonlocal config_state
        config_state = [normalize_row(row) for row in rows]
        refs["config_state"] = config_state
        build_table()

    def append_row(device: str = "", capacity: int | str = 0):
        config_state.append(normalize_row({"selected": False, "device": device, "capacity": capacity}))
        build_table()

    def remove_selected_rows():
        nonlocal config_state
        config_state = [row for row in config_state if not row["selected"]]
        refs["config_state"] = config_state
        build_table()

    def load_config():
        try:
            device_map = config_loader.get_device_load_map()
        except Exception:
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
                log(f"警告: '{cap_text}' 不是有效数字，跳过 {device}")
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
        )
        if not path:
            return
        try:
            save_config_to_path(path)
            log(f"配置已另存为: {path}")
        except Exception as ex:
            log(f"保存配置失败: {ex}")

    def restore_default_config(e: ft.ControlEvent):
        try:
            load_default_config_file(config_loader.get_config_file_path())
            log("已恢复默认配置")
        except Exception as ex:
            log(f"恢复默认配置失败: {ex}")

    def apply_current_config(e: ft.ControlEvent):
        try:
            config_loader.apply_device_load_map(build_device_load_map())
            log("当前配置已应用")
        except Exception as ex:
            log(f"应用当前配置失败: {ex}")

    def add_device(e: ft.ControlEvent):
        append_row()

    def remove_selected(e: ft.ControlEvent):
        remove_selected_rows()

    async def import_config(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="导入配置文件",
            allowed_extensions=["json"],
        )
        if not files:
            return
        path = files[0].path
        try:
            import json as _json
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            imported = data.get("device_load_map", {})
            if not imported:
                log("文件不含 device_load_map")
                return
            for device, cap in imported.items():
                append_row(device, cap)
            log(f"已导入 {len(imported)} 条设备装载量配置")
        except Exception as ex:
            log(f"导入配置失败: {ex}")

    action_buttons = [
        ft.Button("添加设备", icon=ft.icons.Icons.ADD, on_click=add_device, width=160),
        ft.Button("删除选中", icon=ft.icons.Icons.DELETE, on_click=remove_selected, width=160),
        ft.Button("导入配置", icon=ft.icons.Icons.FILE_UPLOAD, on_click=import_config, width=160),
        ft.Button("恢复默认配置", icon=ft.icons.Icons.RESTART_ALT, on_click=restore_default_config, width=160),
        ft.Button("应用当前配置", icon=ft.icons.Icons.CHECK_CIRCLE, on_click=apply_current_config, width=160),
        ft.Button("保存配置", icon=ft.icons.Icons.SAVE, on_click=save_config, width=160),
    ]
    action_button_rows = [
        ft.Row(action_buttons[:3], spacing=10, wrap=False, alignment=ft.MainAxisAlignment.START),
        ft.Row(action_buttons[3:], spacing=10, wrap=False, alignment=ft.MainAxisAlignment.START),
    ]

    container = ft.Container(
        content=ft.Column(
            [
                ft.Text("设备装载量配置", size=18, weight=ft.FontWeight.W_600),
                *action_button_rows,
                ft.Container(
                    content=ft.ListView([config_table], height=200, spacing=5),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=5,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
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


# ---------------------------------------------------------------------------
# 处理模块区域
# ---------------------------------------------------------------------------
def create_modules_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建数据处理模块区域，返回 (container, module_refs)"""

    current_date = datetime.now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)

    # --- Fuel ---
    fuel_path = ft.TextField(
        label="燃油数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    fuel_year = ft.Dropdown(
        label="年份",
        width=125,
        options=[ft.dropdown.Option(str(y)) for y in range(2015, 2040)],
        value="2025",
    )
    fuel_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    # --- Production ---
    prod_path = ft.TextField(
        label="生产数据处理",
        hint_text="选择 Excel 文件或文件夹...",
        expand=2,
        read_only=True,
    )
    prod_file_btn = ft.Button(
        "选文件",
        icon=ft.icons.Icons.UPLOAD_FILE,
    )
    prod_folder_btn = ft.Button(
        "选文件夹",
        icon=ft.icons.Icons.FOLDER_OPEN,
    )
    prod_raw_start = ft.TextField(
        label="表头起始行",
        width=100,
        value="6",
        hint_text="6",
    )
    prod_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    # --- Electrical ---
    elec_path = ft.TextField(
        label="电力数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    elec_year = ft.Dropdown(
        label="年份",
        width=125,
        options=[ft.dropdown.Option(str(y)) for y in range(2015, 2040)],
        value="2025",
    )
    elec_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    # --- Work time ---
    work_path = ft.TextField(
        label="工时数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    work_year = ft.Dropdown(
        label="年份",
        width=125,
        options=[ft.dropdown.Option(str(y)) for y in range(2015, 2040)],
        value=current_year,
    )
    work_month = ft.Dropdown(
        label="月份",
        width=125,
        options=[ft.dropdown.Option(str(month)) for month in range(1, 13)],
        value=current_month,
    )
    work_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    async def on_fuel_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择燃油数据文件",
            allowed_extensions=["xlsx", "xls"],
        )
        if files:
            fuel_path.value = files[0].path
            fuel_path.update()
            fuel_btn.disabled = False
            fuel_btn.update()

    async def on_prod_pick_file(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择生产数据文件",
            allowed_extensions=["xlsx", "xls"],
        )
        if files:
            prod_path.value = files[0].path
            prod_path.update()
            prod_btn.disabled = False
            prod_btn.update()

    async def on_prod_pick_folder(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.get_directory_path(dialog_title="选择生产数据文件夹")
        if path:
            prod_path.value = path
            prod_path.update()
            prod_btn.disabled = False
            prod_btn.update()

    async def on_elec_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择电力数据文件",
            allowed_extensions=["xlsx", "xls"],
        )
        if files:
            elec_path.value = files[0].path
            elec_path.update()
            elec_btn.disabled = False
            elec_btn.update()

    async def on_work_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择工时数据文件",
            allowed_extensions=["xlsx", "xls"],
        )
        if files:
            work_path.value = files[0].path
            work_path.update()
            work_btn.disabled = False
            work_btn.update()

    # 绑定浏览按钮
    fuel_path.suffix.on_click = on_fuel_browse
    prod_file_btn.on_click = on_prod_pick_file
    prod_folder_btn.on_click = on_prod_pick_folder
    elec_path.suffix.on_click = on_elec_browse
    work_path.suffix.on_click = on_work_browse

    container = ft.Container(
        content=ft.Column(
            [
                ft.Text("数据处理模块", size=18, weight=ft.FontWeight.W_600),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([fuel_path, fuel_year, fuel_btn], spacing=10),
                            ft.Row([prod_path, prod_file_btn, prod_folder_btn, prod_raw_start, prod_btn], spacing=10),
                            ft.Row([elec_path, elec_year, elec_btn], spacing=10),
                            ft.Row([work_path, work_year, work_month, work_btn], spacing=10),
                        ],
                        spacing=8,
                    ),
                    padding=10,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
    )

    module_refs = {
        "fuel": {"path": fuel_path, "year": fuel_year, "btn": fuel_btn},
        "prod": {"path": prod_path, "raw_start": prod_raw_start, "btn": prod_btn},
        "elec": {"path": elec_path, "year": elec_year, "btn": elec_btn},
        "work": {"path": work_path, "year": work_year, "month": work_month, "btn": work_btn},
    }
    return container, module_refs


# ---------------------------------------------------------------------------
# 日志视图
# ---------------------------------------------------------------------------
def create_log_view() -> ft.TextField:
    """创建日志视图组件"""
    return ft.TextField(
        label="处理日志",
        multiline=True,
        read_only=True,
        min_lines=6,
        max_lines=8,
        expand=True,
        text_size=11,
    )