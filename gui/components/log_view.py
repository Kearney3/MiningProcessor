"""日志视图组件"""
import flet as ft

from .types import LogViewRefs
from .common import safe_update
from gui.i18n import t

try:
    from . import theme
except ImportError:
    import gui.theme as theme


DEFAULT_LOG_HEIGHT = 350


def create_log_view(height: int = DEFAULT_LOG_HEIGHT) -> tuple[ft.Container, LogViewRefs]:
    """创建适合实时追加的日志视图组件

    使用 ListView（逐行 Text 控件）：
    - 日志控制器批量追加并按需滚动到底部
    - 用户上翻后暂停自动跟随，避免阅读位置被新日志打断
    """
    log_list = ft.ListView(
        controls=[],
        spacing=4,
        auto_scroll=False,
        expand=True,
    )
    level_filter = ft.Dropdown(
        label=t("components:log_view.level"),
        width=130,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        value="INFO",
        options=[
            ft.dropdown.Option(key="DEBUG", text="DEBUG"),
            ft.dropdown.Option(key="INFO", text="INFO"),
            ft.dropdown.Option(key="WARNING", text="WARNING"),
            ft.dropdown.Option(key="ERROR", text="ERROR"),
        ],
    )
    export_button = ft.IconButton(
        icon=ft.Icons.DOWNLOAD,
        tooltip=t("components:log_view.exportLogs"),
        icon_size=18,
    )
    clear_button = ft.IconButton(
        icon=ft.Icons.DELETE_SWEEP,
        tooltip=t("components:log_view.clearLogs"),
        icon_size=18,
    )
    scroll_bottom_button = ft.IconButton(
        icon=ft.Icons.VERTICAL_ALIGN_BOTTOM,
        tooltip=t("components:log_view.scrollToBottom"),
        icon_size=18,
        icon_color=theme.TEXT_SECONDARY,
    )
    follow_status = ft.Text(
        t("components:log_view.logVariant"),
        size=12,
        color=theme.WARNING,
        visible=False,
    )
    count_text = ft.Text(t("components:log_view.0Items"), size=12, color=theme.TEXT_SECONDARY)
    resize_handle = ft.GestureDetector(
        content=ft.Container(
            height=12,
            content=ft.Row(
                [
                    ft.Container(
                        width=40,
                        height=3,
                        border_radius=999,
                        bgcolor=theme.BORDER_STRONG,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=theme.SURFACE_LOW,
            border=ft.Border.only(
                top=ft.BorderSide(1, theme.BORDER),
                bottom=ft.BorderSide(1, theme.BORDER),
            ),
            tooltip=t("components:log_view.log"),
        ),
        mouse_cursor=ft.MouseCursor.RESIZE_UP_DOWN,
    )
    collapse_button = ft.IconButton(
        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
        tooltip=t("components:log_view.collapseLog"),
        icon_size=18,
    )
    toolbar = ft.Row(
        [
            level_filter,
            export_button,
            clear_button,
            scroll_bottom_button,
            follow_status,
            count_text,
            ft.Container(expand=True),
            collapse_button,
        ],
        spacing=4,
        wrap=False,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    list_container = ft.Container(
        content=ft.Column([toolbar, log_list], spacing=4, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        height=height,
        padding=ft.Padding.only(left=10, right=10, top=8, bottom=10),
        bgcolor=theme.SURFACE,
        data={"collapsed": False},
    )
    root = ft.Container(
        content=ft.Column(
            [resize_handle, list_container],
            spacing=0,
        ),
    )

    expanded_height = [height]

    def _toggle_collapsed(_e=None):
        collapsed = log_list.visible is False
        if collapsed:
            log_list.visible = True
            resize_handle.visible = True
            list_container.height = expanded_height[0]
            collapse_button.icon = ft.Icons.KEYBOARD_ARROW_DOWN
            collapse_button.tooltip = t("components:log_view.collapseLog")
            list_container.data["collapsed"] = False
        else:
            expanded_height[0] = int(list_container.height or height)
            log_list.visible = False
            resize_handle.visible = False
            list_container.height = 52
            collapse_button.icon = ft.Icons.KEYBOARD_ARROW_UP
            collapse_button.tooltip = t("components:log_view.expandLog")
            list_container.data["collapsed"] = True
        safe_update(root)

    collapse_button.on_click = _toggle_collapsed
    refs = {
        "toolbar": toolbar,
        "follow_status": follow_status,
        "level_filter": level_filter,
        "export_button": export_button,
        "clear_button": clear_button,
        "scroll_bottom_button": scroll_bottom_button,
        "resize_handle": resize_handle,
        "list_container": list_container,
        "log_list": log_list,
        "count_text": count_text,
        "collapse_button": collapse_button,
    }
    return root, refs
