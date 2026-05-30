"""日志视图组件"""
import flet as ft

from .types import LogViewRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme

# 滚动到底部的判定阈值（像素）
_SCROLL_BOTTOM_THRESHOLD = 50


def create_log_view(height: int = 300) -> tuple[ft.Container, "LogViewRefs"]:
    """创建适合实时追加的日志视图组件

    auto_scroll 由调用方在每次 flush 时根据 _is_at_bottom 动态设置，
    从而实现"视图在底部时自动跟随，手动上翻后不被打扰"的效果。
    """
    # 用 list 包装以便 on_scroll 回调和 flush 函数共享可变状态
    _is_at_bottom: list[bool] = [True]

    def _on_scroll(e: ft.OnScrollEvent):
        _is_at_bottom[0] = e.extent_after < _SCROLL_BOTTOM_THRESHOLD

    log_list = ft.Column(
        controls=[],
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=False,
        expand=True,
        on_scroll=_on_scroll,
    )
    level_filter = ft.Dropdown(
        label="级别",
        width=200,
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
    export_button = ft.IconButton(
        icon=ft.icons.Icons.DOWNLOAD,
        tooltip="导出日志",
        icon_size=18,
    )
    resize_handle = ft.GestureDetector(
        content=ft.Container(
            height=10,
            content=ft.Row(
                [
                    ft.Container(
                        width=48,
                        height=4,
                        border_radius=999,
                        bgcolor=theme.BORDER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=theme.SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, theme.BORDER)),
            tooltip="上下拖拽调整日志区域高度",
        ),
        mouse_cursor=ft.MouseCursor.RESIZE_UP_DOWN,
    )
    toolbar = ft.Row(
        [level_filter, export_button],
        spacing=4,
        wrap=False,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    list_container = ft.Container(
        content=ft.Column([toolbar, log_list], spacing=4, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        height=height,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_MD,
        padding=8,
        bgcolor=theme.SURFACE_HIGH,
    )
    root = ft.Container(
        content=ft.Column(
            [resize_handle, list_container],
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
        "_is_at_bottom": _is_at_bottom,
    }
    return root, refs
