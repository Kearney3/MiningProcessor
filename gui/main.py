"""
GUI 主窗口 - Flet 实现 (Flet 0.84.0)
"""
import flet as ft
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_loader
import equipment_ledger
from excel_fuel import process_diesel_data
from excel_production_enhanced import MiningDataProcessor as ProdProcessor
from excel_electrical import parse_excel_data


def main(page: ft.Page):
    page.title = "矿山数据处理工具"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1020
    page.window_height = 850
    page.padding = 20

    # ---- 共享日志 ----
    log_lines: list[str] = []

    def log(msg: str):
        log_lines.append(msg)
        if len(log_lines) > 500:
            log_lines.pop(0)
        log_view.value = "\n".join(log_lines)
        log_view.update()

    # ---- 页面级 FilePicker ----
    fp = ft.FilePicker()
    fp.visible = False
    page.overlay.append(fp)
    page.update()

    # ============================================================
    # 台账区域
    # ============================================================
    ledger_records: list[dict] = []
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
        expand=True,
    )

    def build_ledger_table(records: list[dict]):
        ledger_table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(str(r.get(c, "")))) for c in
                       ["设备编号", "标准设备名称", "设备类型", "额定装载量", "所属公司"]]
            )
            for r in records
        ]
        page.update()

    async def on_load_ledger(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        path = e.files[0].path
        try:
            ledger = equipment_ledger.EquipmentLedger(path)
            nonlocal ledger_records
            ledger_records = ledger.to_dict()
            ledger_path_label.value = os.path.basename(path)
            ledger_path_label.color = ft.Colors.GREEN
            build_ledger_table(ledger_records)
            log(f"已加载台账: {path}")
        except Exception as ex:
            ledger_path_label.value = f"加载失败: {ex}"
            ledger_path_label.color = ft.Colors.RED
            log(f"加载台账失败: {ex}")
        page.update()

    async def on_export_template(e: ft.FilePickerResultEvent):
        if not e.path:
            return
        try:
            ledger = equipment_ledger.EquipmentLedger()
            ledger.export_template(e.path)
            log(f"已导出模板: {e.path}")
        except Exception as ex:
            log(f"导出模板失败: {ex}")
        page.update()

    ledger_section = ft.Container(
        content=ft.Column(
            [
                ft.Text("设备台账", size=18, weight=ft.FontWeight.W_600),
                ft.Row(
                    [
                        ft.Button(
                            "导入台账",
                            icon=ft.icons.Icons.UPLOAD,
                            on_click=lambda _: fp.pick_files(
                                dialog_title="导入设备台账",
                                allowed_extensions=["xlsx", "xls"],
                            ),
                        ),
                        ft.Button(
                            "导出模板",
                            icon=ft.icons.Icons.DOWNLOAD,
                            on_click=lambda _: fp.save_file(
                                dialog_title="导出模板",
                                file_name="设备台账模板.xlsx",
                                allowed_extensions=["xlsx"],
                            ),
                        ),
                        ledger_path_label,
                    ],
                    spacing=10,
                ),
                ft.Container(
                    content=ft.ListView([ledger_table], expand=True),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=5,
                    expand=True,
                    height=180,
                ),
            ],
            spacing=10,
        ),
        padding=15,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
    )

    fp.on_result = on_load_ledger

    # ---- FilePicker 副本用于保存 ----
    fp_save = ft.FilePicker()
    fp_save.visible = False
    fp_save.on_result = on_export_template
    page.overlay.append(fp_save)

    # ============================================================
    # 配置区域
    # ============================================================
    config_device_map: dict[str, int] = {}
    config_rows: list[ft.DataRow] = []

    config_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("设备型号")),
            ft.DataColumn(ft.Text("装载量 (吨)")),
        ],
        rows=[],
        show_checkbox_column=True,
        expand=True,
    )

    def build_config_table():
        config_table.rows = config_rows
        page.update()

    def load_config():
        nonlocal config_device_map, config_rows
        try:
            config_device_map = config_loader.get_device_load_map()
        except Exception:
            config_device_map = {}
        config_rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(device)),
                    ft.DataCell(ft.Text(str(cap))),
                ]
            )
            for device, cap in sorted(config_device_map.items())
        ]
        build_config_table()

    def save_config(e: ft.ControlEvent):
        new_map = {}
        for row in config_rows:
            device = row.cells[0].content.value
            cap_text = row.cells[1].content.value
            if device:
                try:
                    new_map[device] = int(cap_text) if cap_text else 0
                except ValueError:
                    pass
        config_loader.update_device_load_map(new_map)
        nonlocal config_device_map
        config_device_map = new_map
        log("配置已保存")

    def add_device(e: ft.ControlEvent):
        config_rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("0")),
                ]
            )
        )
        build_config_table()

    def remove_selected(e: ft.ControlEvent):
        checked = [row for row in config_rows if row.selected]
        for row in checked:
            config_rows.remove(row)
        build_config_table()

    config_section = ft.Container(
        content=ft.Column(
            [
                ft.Text("设备装载量配置", size=18, weight=ft.FontWeight.W_600),
                ft.Row(
                    [
                        ft.Button("添加设备", icon=ft.icons.Icons.ADD, on_click=add_device),
                        ft.Button("删除选中", icon=ft.icons.Icons.DELETE, on_click=remove_selected),
                        ft.Button("保存配置", icon=ft.icons.Icons.SAVE, on_click=save_config),
                    ],
                    spacing=10,
                ),
                ft.Container(
                    content=ft.ListView([config_table], expand=True),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=5,
                    expand=True,
                    height=200,
                ),
            ],
            spacing=10,
        ),
        padding=15,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
    )

    # ============================================================
    # 处理模块
    # ============================================================

    # File pickers for each module
    fp_fuel = ft.FilePicker()
    fp_fuel.visible = False
    fp_prod = ft.FilePicker()
    fp_prod.visible = False
    fp_elec = ft.FilePicker()
    fp_elec.visible = False
    fp_work = ft.FilePicker()
    fp_work.visible = False
    page.overlay.extend([fp_fuel, fp_prod, fp_elec, fp_work])

    # --- 燃油 ---
    fuel_path = ft.TextField(
        label="燃油数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: fp_fuel.pick_files(
                dialog_title="选择燃油数据文件",
                allowed_extensions=["xlsx", "xls"],
            ),
        ),
    )
    fuel_year = ft.Dropdown(
        label="年份",
        width=100,
        options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
        value="2025",
    )
    fuel_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    # --- 生产 ---
    prod_path = ft.TextField(
        label="生产数据处理",
        hint_text="选择文件夹...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: fp_prod.get_directory_path(dialog_title="选择生产数据文件夹"),
        ),
    )
    prod_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    # --- 电力 ---
    elec_path = ft.TextField(
        label="电力数据处理",
        hint_text="选择 Excel 文件...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: fp_elec.pick_files(
                dialog_title="选择电力数据文件",
                allowed_extensions=["xlsx", "xls"],
            ),
        ),
    )
    elec_year = ft.Dropdown(
        label="年份",
        width=100,
        options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
        value="2025",
    )
    elec_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    # --- 工时 ---
    work_path = ft.TextField(
        label="工时数据处理",
        hint_text="选择文件或文件夹...",
        expand=2,
        read_only=True,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: fp_work.get_directory_path(dialog_title="选择工时数据"),
        ),
    )
    work_btn = ft.Button(
        "处理",
        icon=ft.icons.Icons.PLAY_ARROW,
        disabled=True,
    )

    def set_btn_state(btn: ft.Button, enabled: bool, label: str = "处理"):
        btn.disabled = not enabled
        btn.text = label
        page.update()

    # File picker result handlers
    def on_fuel_file(e: ft.FilePickerResultEvent):
        if e.files:
            fuel_path.value = e.files[0].path
            fuel_path.update()
            set_btn_state(fuel_btn, True)

    def on_prod_folder(e: ft.FilePickerResultEvent):
        if e.path:
            prod_path.value = e.path
            prod_path.update()
            set_btn_state(prod_btn, True)

    def on_elec_file(e: ft.FilePickerResultEvent):
        if e.files:
            elec_path.value = e.files[0].path
            elec_path.update()
            set_btn_state(elec_btn, True)

    def on_work_folder(e: ft.FilePickerResultEvent):
        if e.path:
            work_path.value = e.path
            work_path.update()
            set_btn_state(work_btn, True)

    fp_fuel.on_result = on_fuel_file
    fp_prod.on_result = on_prod_folder
    fp_elec.on_result = on_elec_file
    fp_work.on_result = on_work_folder

    # ---- 处理逻辑 ----
    def run_task(module_type: str, path: str, btn: ft.Button, **kwargs):
        def do():
            try:
                log(f"[{module_type}] 开始处理...")
                if module_type == "fuel":
                    process_diesel_data(path, kwargs.get("year"))
                elif module_type == "production":
                    output_file = os.path.join(
                        os.path.dirname(path) or ".", "工作效率表_合并.xlsx"
                    )
                    processor = ProdProcessor()
                    processor.process_folder(path, output_file)
                elif module_type == "electrical":
                    parse_excel_data(path, kwargs.get("year"))
                elif module_type == "worktime":
                    processor = ProdProcessor()
                    if os.path.isdir(path):
                        output_file = os.path.join(path, "合并产量.xlsx")
                        processor.process_folder(path, output_file)
                    else:
                        output_file = os.path.join(os.path.dirname(path) or ".", "合并产量.xlsx")
                        processor.process_single_file(path, output_file)
                log(f"[{module_type}] 处理成功")
            except Exception as ex:
                log(f"[{module_type}] 处理失败: {ex}")
            finally:
                page.add(ft.Text(""))  # trigger update
                page.update()

        t = threading.Thread(target=do, daemon=True)
        t.start()

    def on_fuel_process(e: ft.ControlEvent):
        path = fuel_path.value
        if not path:
            log("请先选择文件")
            return
        set_btn_state(fuel_btn, False, "处理中...")
        run_task("fuel", path, fuel_btn, year=fuel_year.value)

    def on_prod_process(e: ft.ControlEvent):
        path = prod_path.value
        if not path:
            log("请先选择文件夹")
            return
        set_btn_state(prod_btn, False, "处理中...")
        run_task("production", path, prod_btn)

    def on_elec_process(e: ft.ControlEvent):
        path = elec_path.value
        if not path:
            log("请先选择文件")
            return
        set_btn_state(elec_btn, False, "处理中...")
        run_task("electrical", path, elec_btn, year=elec_year.value)

    def on_work_process(e: ft.ControlEvent):
        path = work_path.value
        if not path:
            log("请先选择文件或文件夹")
            return
        set_btn_state(work_btn, False, "处理中...")
        run_task("worktime", path, work_btn)

    fuel_btn.on_click = on_fuel_process
    prod_btn.on_click = on_prod_process
    elec_btn.on_click = on_elec_process
    work_btn.on_click = on_work_process

    # 模块区域
    modules_section = ft.Container(
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

    # ---- 日志区域 ----
    log_view = ft.TextField(
        label="处理日志",
        multiline=True,
        read_only=True,
        min_lines=6,
        max_lines=8,
        expand=True,
        text_size=11,
    )

    # ---- 进度条 ----
    progress_bar = ft.ProgressBar(value=0, width=page.window_width - 40)

    # ============================================================
    # 组装页面
    # ============================================================
    page.add(
        ft.Text("矿山数据处理工具", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        ledger_section,
        ft.Divider(),
        config_section,
        ft.Divider(),
        modules_section,
        ft.Divider(),
        log_view,
        progress_bar,
    )

    # 初始化
    load_config()
    log("已就绪")


ft.run(main)
