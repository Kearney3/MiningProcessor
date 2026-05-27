"""数据处理模块区域组件"""
from datetime import datetime
from pathlib import Path

import flet as ft

from .types import ModuleRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def create_modules_section(page: ft.Page) -> tuple[ft.Container, "ModuleRefs"]:
    """创建数据处理模块区域，返回 (container, module_refs)"""

    current_date = datetime.now()
    current_year = str(current_date.year)
    current_month = str(current_date.month)
    _last_directory = [""]  # 记住上次文件选择器的目录

    # --- Fuel ---
    fuel_path = ft.TextField(
        label="燃油数据处理",
        hint_text="输入路径或点击按钮选择...",
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
        style=ft.ButtonStyle(bgcolor=theme.PRIMARY, color="#FFFFFF"),
    )

    # --- Production ---
    prod_path = ft.TextField(
        label="生产数据处理",
        hint_text="输入路径或点击按钮选择...",
        expand=2,
        read_only=False,
    )
    prod_file_btn = ft.Button(
        "选文件",
        icon=ft.icons.Icons.UPLOAD_FILE,
        style=ft.ButtonStyle(bgcolor=theme.SURFACE_HIGH, color=theme.TEXT_PRIMARY),
    )
    prod_folder_btn = ft.Button(
        "选文件夹",
        icon=ft.icons.Icons.FOLDER_OPEN,
        style=ft.ButtonStyle(bgcolor=theme.SURFACE_HIGH, color=theme.TEXT_PRIMARY),
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
        style=ft.ButtonStyle(bgcolor=theme.PRIMARY, color="#FFFFFF"),
    )

    # --- Electrical ---
    elec_path = ft.TextField(
        label="电力数据处理",
        hint_text="输入路径或点击按钮选择...",
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
        style=ft.ButtonStyle(bgcolor=theme.PRIMARY, color="#FFFFFF"),
    )

    # --- Work time ---
    work_path = ft.TextField(
        label="工时数据处理",
        hint_text="输入路径或点击按钮选择...",
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
        style=ft.ButtonStyle(bgcolor=theme.PRIMARY, color="#FFFFFF"),
    )

    # --- Excel Merger ---
    merge_path = ft.TextField(
        label="Excel 合并",
        hint_text="输入路径或点击按钮选择...",
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
        style=ft.ButtonStyle(bgcolor=theme.PRIMARY, color="#FFFFFF"),
    )

    # --- 排序配置列表（Excel 合并用） ---
    sort_configs_state: list[dict] = []

    sort_rules_column = ft.Column(
        spacing=4,
        expand=True,
    )

    def build_sort_rules():
        controls = []
        for i, cfg in enumerate(sort_configs_state):
            idx = i  # 捕获当前索引

            col_field = ft.TextField(
                value=cfg.get("column", ""),
                text_size=12,
                hint_text="列名",
                expand=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
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
                        ft.Text(str(idx + 1), width=30, size=12, color=theme.TEXT_SECONDARY),
                        col_field,
                        order_dropdown,
                        ft.Row([up_btn, down_btn, del_btn], spacing=2),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border=ft.Border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_SM,
                bgcolor=theme.SURFACE_HIGH,
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
        style=ft.ButtonStyle(bgcolor=theme.SURFACE_HIGH, color=theme.TEXT_PRIMARY),
    )

    async def on_fuel_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择燃油数据文件",
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] or None,
        )
        if files:
            fuel_path.value = files[0].path
            _last_directory[0] = str(Path(files[0].path).parent)
            fuel_path.update()
            fuel_btn.disabled = False
            fuel_btn.update()

    async def on_prod_pick_file(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择生产数据文件",
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] or None,
        )
        if files:
            prod_path.value = files[0].path
            _last_directory[0] = str(Path(files[0].path).parent)
            prod_path.update()
            prod_btn.disabled = False
            prod_btn.update()

    async def on_prod_pick_folder(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.get_directory_path(
            dialog_title="选择生产数据文件夹",
            initial_directory=_last_directory[0] or None,
        )
        if path:
            prod_path.value = path
            _last_directory[0] = path
            prod_path.update()
            prod_btn.disabled = False
            prod_btn.update()

    async def on_elec_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择电力数据文件",
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] or None,
        )
        if files:
            elec_path.value = files[0].path
            _last_directory[0] = str(Path(files[0].path).parent)
            elec_path.update()
            elec_btn.disabled = False
            elec_btn.update()

    async def on_work_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title="选择工时数据文件",
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] or None,
        )
        if files:
            work_path.value = files[0].path
            _last_directory[0] = str(Path(files[0].path).parent)
            work_path.update()
            work_btn.disabled = False
            work_btn.update()

    async def on_merge_browse(e: ft.ControlEvent):
        picker = ft.FilePicker()
        path = await picker.get_directory_path(
            dialog_title="选择包含 Excel 文件的文件夹",
            initial_directory=_last_directory[0] or None,
        )
        if path:
            merge_path.value = path
            _last_directory[0] = path
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

    # --- 台账匹配开关 ---
    match_toggle = ft.Checkbox(
        label="启用台账匹配（设备+油品）",
        value=False,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("数据处理模块"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([match_toggle], spacing=8),
                            ft.Row([fuel_path, fuel_year, fuel_btn], spacing=8),
                            ft.Row([prod_path, prod_file_btn, prod_folder_btn, prod_raw_start, prod_btn], spacing=8),
                            ft.Row([elec_path, elec_year, elec_btn], spacing=8),
                            ft.Row([work_path, work_year, work_month, work_btn], spacing=8),
                            ft.Column(
                                [
                                    ft.Row([merge_path, merge_keyword, merge_strip_time, merge_btn], spacing=8),
                                    ft.Column(
                                        [
                                            ft.Text("排序配置（可选，留空则自动按第一个时间列排序）", size=12,
                                                    color=theme.TEXT_SECONDARY),
                                            ft.Row([sort_rules_column, add_sort_btn], spacing=8,
                                                   alignment=ft.MainAxisAlignment.START),
                                        ],
                                        spacing=4,
                                    ),
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=12,
                ),
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

    module_refs = {
        "_match_toggle": match_toggle,
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
