"""
GUI 组件工厂函数
提供各区域 UI 组件的创建接口
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
import sys
import flet as ft
# 定位到当前项目的根目录
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

import func.equipment_ledger as equipment_ledger
from func.equipment_ledger import LEDGER_COLUMNS


def _log_message(log, message: str, level: int = logging.INFO):
    """兼容仅接收 message 的旧回调，也支持显式日志级别。"""
    try:
        log(message, level=level)
    except TypeError:
        log(message)


# ---------------------------------------------------------------------------
# 台账区域
# ---------------------------------------------------------------------------
def create_ledger_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建设备台账区域，返回 (container, refs)"""
    ledger_records = []
    ledger_path_label = ft.Text("未加载台账", size=12, color=ft.Colors.GREY)
    ledger_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text(c)) for c in LEDGER_COLUMNS
        ],
        rows=[],
    )
    ledger_table_wrapper = ft.Column(
        controls=[
            ft.Row(
                controls=[ledger_table],
                scroll=ft.ScrollMode.AUTO,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        height=220,
    )

    def build_table(records):
        ledger_table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(str(r.get(c, "")))) for c in LEDGER_COLUMNS]
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
            _log_message(log, f"已加载台账: {path}")
        except Exception as ex:
            ledger_path_label.value = f"加载失败: {ex}"
            ledger_path_label.color = ft.Colors.RED
            _log_message(log, f"加载台账失败: {ex}", level=logging.ERROR)
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
            _log_message(log, f"已导出模板: {path}")
        except Exception as ex:
            _log_message(log, f"导出模板失败: {ex}", level=logging.ERROR)
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
                    content=ledger_table_wrapper,
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=5,
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
    from func import config_loader

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
        )
        if not path:
            return
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
        read_only=False,
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
        disabled=False,
    )

    # --- Production ---
    prod_path = ft.TextField(
        label="生产数据处理",
        hint_text="选择 Excel 文件或文件夹...",
        expand=2,
        read_only=False,
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
        disabled=False,
    )

    # --- Electrical ---
    elec_path = ft.TextField(
        label="电力数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=False,
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
        disabled=False,
    )

    # --- Work time ---
    work_path = ft.TextField(
        label="工时数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=False,
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
        disabled=False,
    )

    # --- Excel Merger ---
    merge_path = ft.TextField(
        label="Excel 合并",
        hint_text="选择包含 Excel 文件的文件夹...",
        expand=2,
        read_only=False,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    merge_keyword = ft.TextField(
        label="关键字",
        hint_text="例如: Fuel",
        width=150,
    )
    merge_strip_time = ft.Checkbox(
        label="仅保留日期",
        value=False,
        tooltip="勾选后，时间列将去除时分秒，格式为 YYYY-MM-DD",
    )
    merge_btn = ft.Button(
        "合并",
        icon=ft.icons.Icons.MERGE_TYPE,
        disabled=False,
    )

    # --- 排序配置列表（Excel 合并用） ---
    sort_configs_state: list[dict] = []

    sort_rules_column = ft.Column(
        spacing=4,
        expand=2
    )

    def build_sort_rules():
        controls = []
        for i, cfg in enumerate(sort_configs_state):
            idx = i  # 捕获当前索引

            col_field = ft.TextField(
                value=cfg.get("column", ""),
                text_size=12,
                # border_color="transparent",
                hint_text="列名",
            )
            order_dropdown = ft.Dropdown(
                value="升序" if cfg.get("ascending", True) else "降序",
                options=[ft.dropdown.Option("升序"), ft.dropdown.Option("降序")],
                width=90,
                text_size=12,
            )

            def on_col_change(e, _idx=idx):
                sort_configs_state[_idx]["column"] = e.control.value

            def on_order_select(e, _idx=idx):
                sort_configs_state[_idx]["ascending"] = (e.control.value == "升序")

            col_field.on_change = on_col_change
            order_dropdown.on_select = on_order_select

            def move_up(e, _idx=idx):
                if _idx > 0:
                    sort_configs_state[_idx - 1], sort_configs_state[_idx] = (
                        sort_configs_state[_idx],
                        sort_configs_state[_idx - 1],
                    )
                    build_sort_rules()
                    sort_rules_column.update()

            def move_down(e, _idx=idx):
                if _idx < len(sort_configs_state) - 1:
                    sort_configs_state[_idx + 1], sort_configs_state[_idx] = (
                        sort_configs_state[_idx],
                        sort_configs_state[_idx + 1],
                    )
                    build_sort_rules()
                    sort_rules_column.update()

            def remove_row(e, _idx=idx):
                sort_configs_state.pop(_idx)
                build_sort_rules()
                sort_rules_column.update()

            up_btn = ft.IconButton(
                icon=ft.icons.Icons.ARROW_UPWARD, tooltip="上移", on_click=move_up, icon_size=16
            )
            down_btn = ft.IconButton(
                icon=ft.icons.Icons.ARROW_DOWNWARD, tooltip="下移", on_click=move_down, icon_size=16
            )
            del_btn = ft.IconButton(
                icon=ft.icons.Icons.DELETE, tooltip="删除", on_click=remove_row, icon_size=16
            )

            row_container = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(str(idx + 1), width=30, size=12),
                        col_field,
                        order_dropdown,
                        ft.Row([up_btn, down_btn, del_btn], spacing=2),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=6,
                bgcolor=ft.Colors.SURFACE,
            )

            controls.append(row_container)

        sort_rules_column.controls = controls
        sort_rules_column.update()

    def add_sort_config(e):
        sort_configs_state.append({"column": "", "ascending": True})
        build_sort_rules()

    add_sort_btn = ft.Button(
        "添加排序条件",
        icon=ft.icons.Icons.ADD,
        on_click=add_sort_config,
        height=36,
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

    async def on_merge_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.get_directory_path(dialog_title="选择包含 Excel 文件的文件夹")
        if path:
            merge_path.value = path
            merge_path.update()
            merge_btn.disabled = False
            merge_btn.update()

    # 绑定浏览按钮
    fuel_path.suffix.on_click = on_fuel_browse
    prod_file_btn.on_click = on_prod_pick_file
    prod_folder_btn.on_click = on_prod_pick_folder
    elec_path.suffix.on_click = on_elec_browse
    work_path.suffix.on_click = on_work_browse
    merge_path.suffix.on_click = on_merge_browse

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
                            ft.Column(
                                [
                                    ft.Row([merge_path, merge_keyword, merge_strip_time, merge_btn], spacing=10),
                                    ft.Row(
                                        [
                                            ft.Column(
                                                [
                                                    ft.Text("排序配置（可选，留空则自动按第一个时间列排序）", size=12, color=ft.Colors.GREY),
                                                    ft.Row([sort_rules_column, add_sort_btn], spacing=10, alignment=ft.MainAxisAlignment.START, expand=True),
                                                ],
                                                spacing=4,
                                            )
                                        ],
                                        spacing=10,
                                    ),
                                ],
                                spacing=4,
                            ),
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
        "merge": {
            "path": merge_path,
            "keyword": merge_keyword,
            "strip_time": merge_strip_time,
            "btn": merge_btn,
            "sort_configs_state": sort_configs_state,
        },
    }
    return container, module_refs


# ---------------------------------------------------------------------------
# 日志视图
# ---------------------------------------------------------------------------
def create_log_view(height: int = 200) -> tuple[ft.Container, dict]:
    """创建适合实时追加的日志视图组件"""
    log_list = ft.ListView(
        controls=[],
        spacing=4,
        auto_scroll=True,
        expand=True,
    )
    level_filter = ft.Dropdown(
        label="等级筛选",
        width=132,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        value="ALL",
        options=[
            ft.dropdown.Option(key="ALL", text="全部"),
            ft.dropdown.Option(key="DEBUG", text="DEBUG"),
            ft.dropdown.Option(key="INFO", text="INFO"),
            ft.dropdown.Option(key="WARNING", text="WARNING"),
            ft.dropdown.Option(key="ERROR", text="ERROR"),
            ft.dropdown.Option(key="CRITICAL", text="CRITICAL"),
        ],
    )
    export_button = ft.Button(
        "导出日志",
        icon=ft.icons.Icons.DOWNLOAD,
        height=32,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )
    resize_handle = ft.GestureDetector(
        content=ft.Container(
            height=12,
            padding=ft.Padding.only(top=2),
            content=ft.Row(
                [
                    ft.Container(
                        width=64,
                        height=4,
                        border_radius=999,
                        bgcolor=ft.Colors.OUTLINE_VARIANT,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            tooltip="拖拽调整日志区域高度",
        ),
        mouse_cursor=ft.MouseCursor.RESIZE_UP_DOWN,
    )
    list_container = ft.Container(
        content=log_list,
        height=height,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        padding=8,
    )
    toolbar = ft.Row(
        [level_filter, export_button],
        spacing=8,
        wrap=False,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    root = ft.Container(
        content=ft.Column(
            [toolbar, resize_handle, list_container],
            spacing=6,
        ),
        padding=ft.Padding.only(top=2),
    )
    refs = {
        "toolbar": toolbar,
        "level_filter": level_filter,
        "export_button": export_button,
        "resize_handle": resize_handle,
        "list_container": list_container,
        "log_list": log_list,
    }
    return root, refs
