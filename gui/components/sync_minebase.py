"""MineBase 数据同步区域组件"""
import flet as ft

from .common import (
    _get_initial_directory,
    _last_directory,
    _show_path_confirm,
    _update_last_directory,
    ChipToggle,
)

try:
    from . import theme
except ImportError:
    import gui.theme as theme


# 数据类型定义
DATA_TYPES = [
    ("fuel", "油耗数据"),
    ("electrical", "电耗数据"),
    ("operation", "设备运行"),
    ("production", "生产数据"),
    ("work_efficiency", "工作效率"),
]


def create_sync_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建 MineBase 数据同步区域，返回 (container, refs_dict)"""

    # --- 目录路径 ---
    sync_path = ft.TextField(
        label="输出目录",
        hint_text="选择 MiningProcessor 输出目录...",
        expand=True,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        value=_get_initial_directory(),
        suffix=ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
        ),
    )

    _browse_picker = ft.FilePicker()
    page.services.append(_browse_picker)

    async def on_browse(e):
        result = await _browse_picker.get_directory_path_async(dialog_title="选择输出目录")
        if result.path:
            sync_path.value = result.path
            _update_last_directory(result.path, is_dir=True)
            _show_path_confirm(sync_path)
            sync_path.update()

    sync_path.suffix.on_click = on_browse

    # --- 同步模式 ---
    mode_toggle = ChipToggle(
        options=[("api", "API 模式"), ("database", "直连数据库")],
        initial="api",
    )

    # --- 数据类型选择 ---
    type_checks = {}
    for key, label in DATA_TYPES:
        type_checks[key] = ft.Checkbox(
            label=label,
            value=True,
            active_color=theme.PRIMARY,
        )

    select_all = ft.Checkbox(
        label="全选",
        value=True,
        active_color=theme.PRIMARY,
    )

    def on_select_all(e):
        for cb in type_checks.values():
            cb.value = select_all.value
            cb.update()

    select_all.on_change = on_select_all

    def on_type_change(e):
        all_checked = all(cb.value for cb in type_checks.values())
        select_all.value = all_checked
        select_all.update()

    for cb in type_checks.values():
        cb.on_change = on_type_change

    # --- 预览模式 ---
    dry_run_check = ft.Checkbox(
        label="预览模式（不实际推送）",
        value=False,
        active_color=theme.PRIMARY,
    )

    # --- 同步按钮 ---
    sync_btn = theme.primary_btn("同步到 MineBase", icon=ft.Icons.CLOUD_UPLOAD)

    # --- 结果显示 ---
    result_text = ft.Text(
        "",
        size=13,
        color=theme.TEXT_SECONDARY,
        visible=False,
    )

    # --- 布局 ---
    type_row = ft.ResponsiveRow(
        [ft.Container(select_all, col={"xs": 12, "md": 6})]
        + [ft.Container(cb, col={"xs": 12, "md": 6}) for cb in type_checks.values()],
        run_spacing=4,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("MineBase 数据同步"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("输出目录", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            sync_path,
                            ft.Divider(height=1, color=theme.BORDER),
                            ft.Text("同步模式", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            mode_toggle.row,
                            ft.Divider(height=1, color=theme.BORDER),
                            ft.Text("数据类型", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                            type_row,
                            ft.Divider(height=1, color=theme.BORDER),
                            dry_run_check,
                            ft.Row(
                                [sync_btn, result_text],
                                alignment=ft.MainAxisAlignment.START,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=12,
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=theme.SURFACE,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_LG,
                    padding=theme.SPACING_LG,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding.symmetric(horizontal=0, vertical=8),
    )

    refs = {
        "path": sync_path,
        "mode": mode_toggle,
        "types": type_checks,
        "dry_run": dry_run_check,
        "btn": sync_btn,
        "result_text": result_text,
    }

    return container, refs
