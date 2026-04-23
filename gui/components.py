"""
GUI 组件工厂函数
提供各区域 UI 组件的创建接口
"""
import flet as ft
import os
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
            ft.DataColumn(ft.Text("额定装载量")),
            ft.DataColumn(ft.Text("所属公司")),
        ],
        rows=[],
    )

    def build_table(records):
        ledger_table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(str(r.get(c, "")))) for c in
                       ["设备编号", "标准设备名称", "设备类型", "额定装载量", "所属公司"]]
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
            spacing=10,
        ),
        padding=15,
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
    import config_loader

    config_rows = []

    config_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("设备型号")),
            ft.DataColumn(ft.Text("装载量 (吨)")),
        ],
        rows=[],
        show_checkbox_column=True,
    )

    def build_table():
        config_table.rows = config_rows[:]
        page.update()

    def load_config():
        nonlocal config_rows
        try:
            device_map = config_loader.get_device_load_map()
        except Exception:
            device_map = {}
        config_rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.TextField(value=device, text_size=13, border_color="transparent")),
                    ft.DataCell(ft.TextField(value=str(cap), text_size=13, width=80, border_color="transparent")),
                ]
            )
            for device, cap in sorted(device_map.items())
        ]
        build_table()

    def save_config(e: ft.ControlEvent):
        new_map = {}
        for row in config_rows:
            device = row.cells[0].content.value
            cap_text = row.cells[1].content.value
            if device and cap_text:
                try:
                    new_map[device] = int(cap_text)
                except ValueError:
                    log(f"警告: '{cap_text}' 不是有效数字，跳过 {device}")
                    continue
        try:
            config_loader.update_device_load_map(new_map)
            log("配置已保存")
        except Exception as ex:
            log(f"保存配置失败: {ex}")

    def add_device(e: ft.ControlEvent):
        config_rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.TextField(value="", text_size=13, hint_text="设备型号", border_color="transparent")),
                    ft.DataCell(ft.TextField(value="0", text_size=13, width=80, hint_text="吨", border_color="transparent")),
                ]
            )
        )
        build_table()

    def remove_selected(e: ft.ControlEvent):
        checked = [row for row in config_rows if row.selected]
        for row in checked:
            config_rows.remove(row)
        build_table()

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
                config_rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.TextField(value=device, text_size=13, border_color="transparent")),
                            ft.DataCell(ft.TextField(value=str(cap), text_size=13, width=80, border_color="transparent")),
                        ]
                    )
                )
            build_table()
            log(f"已导入 {len(imported)} 条设备装载量配置")
        except Exception as ex:
            log(f"导入配置失败: {ex}")

    container = ft.Container(
        content=ft.Column(
            [
                ft.Text("设备装载量配置", size=18, weight=ft.FontWeight.W_600),
                ft.Row(
                    [
                        ft.Button("添加设备", icon=ft.icons.Icons.ADD, on_click=add_device),
                        ft.Button("删除选中", icon=ft.icons.Icons.DELETE, on_click=remove_selected),
                        ft.Button("导入配置", icon=ft.icons.Icons.FILE_UPLOAD, on_click=import_config),
                        ft.Button("保存配置", icon=ft.icons.Icons.SAVE, on_click=save_config),
                    ],
                    spacing=10,
                ),
                ft.Container(
                    content=ft.ListView([config_table], height=200, spacing=5),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=5,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        padding=15,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
    )

    refs = {
        "config_table": config_table,
        "config_rows": config_rows,
        "load_config": load_config,
    }
    return container, refs


# ---------------------------------------------------------------------------
# 处理模块区域
# ---------------------------------------------------------------------------
def create_modules_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建数据处理模块区域，返回 (container, module_refs)"""

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
        options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
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
        hint_text="选择文件夹...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
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
        options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
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
        hint_text="选择文件或文件夹...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
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

    async def on_prod_browse(e: ft.ControlEvent):
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
        path = await picker.get_directory_path(dialog_title="选择工时数据")
        if path:
            work_path.value = path
            work_path.update()
            work_btn.disabled = False
            work_btn.update()

    # 绑定浏览按钮
    fuel_path.suffix.on_click = on_fuel_browse
    prod_path.suffix.on_click = on_prod_browse
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
                            ft.Row([prod_path, prod_btn], spacing=10),
                            ft.Row([elec_path, elec_year, elec_btn], spacing=10),
                            ft.Row([work_path, work_btn], spacing=10),
                        ],
                        spacing=8,
                    ),
                    padding=10,
                ),
            ],
            spacing=10,
        ),
        padding=15,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
    )

    module_refs = {
        "fuel": {"path": fuel_path, "year": fuel_year, "btn": fuel_btn},
        "prod": {"path": prod_path, "btn": prod_btn},
        "elec": {"path": elec_path, "year": elec_year, "btn": elec_btn},
        "work": {"path": work_path, "btn": work_btn},
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