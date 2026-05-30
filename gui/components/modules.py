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
        color=theme.TEXT_PRIMARY,
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
        color=theme.TEXT_PRIMARY,
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
        color=theme.TEXT_PRIMARY,
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
        color=theme.TEXT_PRIMARY,
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
        color=theme.TEXT_PRIMARY,
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
    work_header_toggle = ft.Checkbox(
        label="表头修改",
        value=True,
        tooltip="开启后按配置的映射关系重命名输出表头",
    )
    # ── 匹配模式芯片切换 ──
    _work_mode_state = ["position"]  # "position" | "name"

    _work_chip_position = ft.Container(
        content=ft.Text("按位置", size=12, weight=ft.FontWeight.W_500, color="#FFFFFF"),
        bgcolor=theme.PRIMARY,
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        on_click=None,
        ink=True,
    )
    _work_chip_name = ft.Container(
        content=ft.Text("按列名", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        bgcolor=theme.SURFACE_HIGH,
        border_radius=theme.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        on_click=None,
        ink=True,
    )
    work_header_mode_row = ft.Row(
        [_work_chip_position, _work_chip_name],
        spacing=0,
        tight=True,
        visible=work_header_toggle.value,
    )

    class _ModeSelector:
        """带 .value 属性的芯片切换控件组，兼容 logic.py 的 .value 读取。"""
        def __init__(self, state: list, row: ft.Row):
            self._state = state
            self._row = row
        @property
        def value(self) -> str:
            return self._state[0]
        def update(self):
            self._row.update()

    work_header_mode = _ModeSelector(_work_mode_state, work_header_mode_row)

    work_header_fuzzy = ft.Checkbox(
        label="模糊匹配",
        value=False,
        visible=False,
        tooltip="按列名匹配时启用模糊匹配（容错错别字）",
    )

    def _update_work_chips():
        is_pos = _work_mode_state[0] == "position"
        _work_chip_position.bgcolor = theme.PRIMARY if is_pos else theme.SURFACE_HIGH
        _work_chip_position.content.color = "#FFFFFF" if is_pos else theme.TEXT_SECONDARY
        _work_chip_name.bgcolor = theme.PRIMARY if not is_pos else theme.SURFACE_HIGH
        _work_chip_name.content.color = "#FFFFFF" if not is_pos else theme.TEXT_SECONDARY
        work_header_fuzzy.visible = not is_pos
        try:
            work_header_mode_row.update()
            work_header_fuzzy.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_work_chip_position(e):
        _work_mode_state[0] = "position"
        _update_work_chips()

    def _on_work_chip_name(e):
        _work_mode_state[0] = "name"
        _update_work_chips()

    _work_chip_position.on_click = _on_work_chip_position
    _work_chip_name.on_click = _on_work_chip_name
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
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(
            icon=ft.icons.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )
    merge_keyword = ft.TextField(
        label="关键字",
        hint_text="例如: Fuel",
        width=150,
        color=theme.TEXT_PRIMARY,
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

    header_hint = ft.Row(
        [
            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=theme.TEXT_SECONDARY),
            ft.Text("映射规则可在「用户配置 → 工作效率表头映射配置」中编辑", size=11, color=theme.TEXT_SECONDARY),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=work_header_toggle.value,
    )

    def _on_header_toggle_change(e):
        visible = work_header_toggle.value
        _work_chip_position.disabled = not visible
        _work_chip_name.disabled = not visible
        work_header_mode_row.visible = visible
        if not visible:
            work_header_fuzzy.visible = False
        else:
            work_header_fuzzy.visible = (_work_mode_state[0] == "name")
        header_hint.visible = visible
        try:
            work_header_mode_row.update()
            work_header_fuzzy.update()
            header_hint.update()
        except (RuntimeError, AttributeError):
            pass

    work_header_toggle.on_change = _on_header_toggle_change

    def _module_card(content_controls: list, spacing: int = 6) -> ft.Container:
        return ft.Container(
            content=ft.Column(content_controls, spacing=spacing),
            padding=10,
            border=ft.Border.all(1, theme.BORDER),
            border_radius=theme.RADIUS_SM,
            bgcolor=theme.SURFACE,
        )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("数据处理模块"),
                ft.Text(
                    "选择数据文件或文件夹后点击处理按钮，各模块独立运行。",
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),
                _module_card([
                    ft.Row([fuel_path, fuel_year, fuel_btn], spacing=8),
                ]),
                _module_card([
                    ft.Row([prod_path, prod_file_btn, prod_folder_btn, prod_raw_start, prod_btn], spacing=8),
                ]),
                _module_card([
                    ft.Row([elec_path, elec_year, elec_btn], spacing=8),
                ]),
                _module_card([
                    ft.Row([work_path, work_year, work_month, work_btn], spacing=6),
                    ft.Row(
                        [work_header_toggle, work_header_mode_row, work_header_fuzzy],
                        spacing=theme.SPACING_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    header_hint,
                ]),
                _module_card([
                    ft.Row([merge_path, merge_keyword, merge_strip_time, merge_btn], spacing=8),
                    ft.Text("排序配置（可选，留空则自动按第一个时间列排序）", size=12,
                            color=theme.TEXT_SECONDARY),
                    ft.Row([sort_rules_column, add_sort_btn], spacing=8,
                           alignment=ft.MainAxisAlignment.START),
                ], spacing=4),
                ft.Row([match_toggle], spacing=8),
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
        "work": {"path": work_path, "year": work_year, "month": work_month, "header_toggle": work_header_toggle, "header_mode": work_header_mode, "header_fuzzy": work_header_fuzzy, "btn": work_btn},
        "merge": {
            "path": merge_path,
            "keyword": merge_keyword,
            "strip_time": merge_strip_time,
            "btn": merge_btn,
            "sort_configs_state": sort_configs_state,
        },
    }
    return container, module_refs
