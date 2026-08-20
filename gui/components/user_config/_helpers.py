"""共享工具函数：端口字段状态同步、端口文本规范化、关键字 chip 输入组件。"""
import contextlib
import re

import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from gui.components.common import safe_update
from gui.i18n import t


def _sync_port_state(port_field: ft.TextField, is_valid: bool, message: str = ""):
    """统一端口字段的边框和提示状态。"""
    port_field.border_color = ft.Colors.RED if not is_valid else theme.BORDER
    port_field.error_text = message or None
    with contextlib.suppress(RuntimeError, AttributeError):
        port_field.update()


def _normalize_port_text(value: str | None) -> str:
    return re.sub(r"\D+", "", (value or "").strip())


def _create_keyword_input(page: ft.Page, label: str, hint_text: str):
    """创建单个关键字 chip 输入组件，返回 (column, get_keywords, set_keywords)。"""
    _items: list[str] = []
    chips_row = ft.Row(spacing=4, wrap=True, run_spacing=4)
    input_field = ft.TextField(
        hint_text=hint_text,
        expand=True,
        dense=True,
        text_size=13,
        color=theme.TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
        border_color=theme.BORDER,
        focused_border_color=theme.PRIMARY,
    )

    def _rebuild_chips():
        chips_row.controls.clear()
        for i, kw in enumerate(_items):
            idx = i

            def _on_delete(e, _idx=idx):
                _items.pop(_idx)
                _rebuild_chips()
                safe_update(chips_row)

            chip = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(kw, size=12, color=ft.Colors.BLUE_700),
                        ft.Icon(ft.Icons.CLOSE, size=14, color=ft.Colors.BLUE_400),
                    ],
                    spacing=2,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                on_click=_on_delete,
                tooltip=t("components:user_config._helpers.clickToDelete"),
            )
            chips_row.controls.append(chip)
        safe_update(chips_row)

    def _on_add(e=None):
        val = (input_field.value or "").strip()
        if not val:
            return
        _items.append(val)
        input_field.value = ""
        _rebuild_chips()
        safe_update(input_field)

    input_field.on_submit = _on_add
    add_btn = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        tooltip=t("components:user_config._helpers.addKeyword"),
        icon_size=22,
        icon_color=theme.PRIMARY,
        on_click=_on_add,
    )

    column = ft.Column(
        [
            ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            chips_row,
            ft.Row([input_field, add_btn], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        spacing=4,
    )

    def get_keywords() -> list[str]:
        return list(_items)

    def set_keywords(items: list[str]):
        _items.clear()
        _items.extend(items)
        _rebuild_chips()

    return column, get_keywords, set_keywords
