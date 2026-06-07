"""GUI 组件共享工具函数与状态"""
from datetime import datetime

import flet as ft
import logging
import math
import threading
import pandas as pd
from pathlib import Path

from func.config_loader import get_user_config, update_user_config

# 共享的文件选择器上次目录，所有模块复用同一份
# 使用列表以便在各模块内原地更新，保证跨模块可见
_last_directory: list[str] = [get_user_config("last_directory", "")]


def _get_initial_directory() -> str | None:
    """返回上次使用的目录路径（仅当目录仍然存在时），否则返回 None。"""
    d = _last_directory[0]
    if d and Path(d).is_dir():
        return d
    return None


def year_options(start_offset: int = -5, end_offset: int = 10) -> list[ft.dropdown.Option]:
    """生成年份下拉选项列表，基于当前年份动态计算范围。"""
    current = datetime.now().year
    return [ft.dropdown.Option(str(y)) for y in range(current + start_offset, current + end_offset + 1)]


def _log_message(log, message: str, level: int = logging.INFO):
    """兼容仅接收 message 的旧回调，也支持显式日志级别。"""
    try:
        log(message, level=level)
    except TypeError:
        log(message)


def _update_last_directory(path: str, *, is_dir: bool = False) -> None:
    """统一更新共享的文件选择器目录，并持久化到 config.user.json。

    Args:
        path: 文件或目录路径。
        is_dir: 若为 True 则 path 本身即目录，否则取其父目录。
    """
    directory = path if is_dir else str(Path(path).parent)
    _last_directory[0] = directory
    try:
        update_user_config({"last_directory": directory})
    except Exception:
        logging.getLogger(__name__).debug("持久化 last_directory 失败", exc_info=True)


class SortState:
    """排序状态管理"""
    def __init__(self):
        self.column: str | None = None
        self.ascending: bool = True

    def toggle(self, column: str):
        """切换排序列或方向"""
        if self.column == column:
            self.ascending = not self.ascending
        else:
            self.column = column
            self.ascending = True

    def reset(self):
        """重置排序状态"""
        self.column = None
        self.ascending = True

    def apply_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """对 DataFrame 应用排序"""
        if self.column and self.column in df.columns:
            try:
                return df.sort_values(by=self.column, ascending=self.ascending, kind="stable")
            except Exception:
                pass
        return df

    def get_column_index(self, columns: list[str]) -> int | None:
        """获取排序列的索引"""
        if self.column and self.column in columns:
            return columns.index(self.column)
        return None


def create_sortable_columns(
    columns: list[str],
    sort_state: SortState,
    on_sort_callback,
    text_size: int = 13,
) -> list[ft.DataColumn]:
    """创建可排序的列"""
    def on_sort_handler(col_idx):
        def handler(e):
            sort_state.toggle(columns[e.column_index])
            on_sort_callback()
        return handler

    return [
        ft.DataColumn(
            ft.Text(c, size=text_size, no_wrap=True),
            on_sort=on_sort_handler(c),
        )
        for c in columns
    ]


def _cell_text(value) -> str:
    """将单元格值转为显示文本，NaN/None 显示为空字符串。"""
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _show_path_confirm(text_field: ft.TextField):
    """在路径输入框右侧显示绿色确认勾，1.5 秒后恢复为原图标。"""
    try:
        from . import theme
    except ImportError:
        import gui.theme as theme

    suffix = text_field.suffix
    if isinstance(suffix, ft.IconButton):
        _original_icon = suffix.icon
        _original_tooltip = suffix.tooltip
        suffix.icon = ft.Icons.CHECK_CIRCLE
        suffix.icon_color = theme.SUCCESS
        suffix.tooltip = "已选择"
        try:
            text_field.update()
        except (RuntimeError, AttributeError):
            pass

        def _restore():
            suffix.icon = _original_icon
            suffix.icon_color = None
            suffix.tooltip = _original_tooltip
            try:
                text_field.update()
            except (RuntimeError, AttributeError):
                pass
        threading.Timer(1.5, _restore).start()
    else:
        try:
            text_field.update()
        except (RuntimeError, AttributeError):
            pass


class ChipToggle:
    """芯片切换控件组，提供 .value 属性和 .row / .update() 方法。

    Args:
        options: [(value, label), ...] 选项列表，至少 2 项。
        initial: 初始选中的 value，默认取第一项。
        on_change: 可选回调 fn(new_value)，切换时触发。
    """

    def __init__(
        self,
        options: list[tuple[str, str]],
        initial: str | None = None,
        on_change=None,
    ):
        try:
            from . import theme
        except ImportError:
            import gui.theme as theme

        self._options = options
        self._value = initial if initial is not None else options[0][0]
        self._on_change = on_change

        self._chips: list[ft.Container] = []
        for val, label in options:
            chip = ft.Container(
                content=ft.Text(label, size=12, weight=ft.FontWeight.W_500, color="#FFFFFF"),
                bgcolor=theme.PRIMARY,
                border_radius=theme.RADIUS_SM,
                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                on_click=lambda e, v=val: self._select(v),
                ink=True,
            )
            self._chips.append(chip)

        self.row = ft.Row(self._chips, spacing=0, tight=True)
        self._update_appearance()

    @property
    def value(self) -> str:
        return self._value

    def _select(self, val: str):
        self._value = val
        self._update_appearance()
        if self._on_change:
            self._on_change(val)

    def _update_appearance(self):
        try:
            from . import theme
        except ImportError:
            import gui.theme as theme

        for i, (val, _) in enumerate(self._options):
            chip = self._chips[i]
            is_selected = val == self._value
            chip.bgcolor = theme.PRIMARY if is_selected else theme.SURFACE_HIGH
            chip.content.color = "#FFFFFF" if is_selected else theme.TEXT_SECONDARY
        try:
            self.row.update()
        except (RuntimeError, AttributeError):
            pass

    def update(self):
        """兼容外部直接调用 .update()。"""
        self._update_appearance()


def create_column_mapping_dialog(
    page: ft.Page,
    file_columns: list[str],
    standard_cols: list[tuple[str, str]],
    on_confirm,
    *,
    height: int = 400,
) -> ft.AlertDialog:
    """创建列映射对话框的通用工厂。

    Args:
        page: Flet 页面对象。
        file_columns: Excel 文件中的列名列表。
        standard_cols: [(标准列名, 提示文本), ...] 标准列定义。
        on_confirm: 回调 fn(mapping: dict, skip_header: bool)。
        height: 对话框内容高度，默认 400。
    """
    mapping_controls = []
    dropdowns = {}

    for col_name, hint in standard_cols:
        default_value = col_name if col_name in file_columns else None
        dd = ft.Dropdown(
            label=col_name,
            hint_text=hint,
            options=[ft.dropdown.Option(c) for c in file_columns],
            value=default_value,
            width=280,
            dense=True,
        )
        dropdowns[col_name] = dd
        mapping_controls.append(dd)

    skip_header_checkbox = ft.Checkbox(
        label="第一行为标题行（排除）",
        value=True,
    )

    def on_cancel(e):
        page.pop_dialog()
        page.update()

    def on_ok(e):
        mapping = {}
        for std_col, dd in dropdowns.items():
            val = dd.value
            if val:
                mapping[std_col] = val
        page.pop_dialog()
        page.update()
        on_confirm(mapping, skip_header_checkbox.value)

    return ft.AlertDialog(
        title=ft.Text("列映射配置"),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text("请将 Excel 文件的列映射到标准列：", size=13),
                    *mapping_controls,
                    ft.Divider(),
                    skip_header_checkbox,
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=320,
            height=height,
        ),
        actions=[
            ft.TextButton("取消", on_click=on_cancel),
            ft.TextButton(
                "确认导入",
                on_click=on_ok,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color="#FFFFFF"),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
