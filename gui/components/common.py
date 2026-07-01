"""GUI 组件共享工具函数与状态"""
from datetime import datetime

import flet as ft
import logging
import math
import threading
import pandas as pd
from pathlib import Path

from func.config_loader import get_user_config, update_user_config
from func.excel_utils import strip_date_only_times

logger = logging.getLogger(__name__)

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


def safe_update(*controls):
    """安全调用控件的 update()，忽略未挂载时的异常。"""
    for ctrl in controls:
        try:
            ctrl.update()
        except (RuntimeError, AttributeError):
            pass


def to_local_dt(d):
    """将 date 转为带本地时区的 datetime，修复 Flet DatePicker 时区偏移问题。

    Flet 序列化协议会将 naive datetime 转为 UTC 再传给 Flutter，
    导致 UTC+时区的用户选中的日期往前偏移一天。
    传入带本地时区的 datetime 可避免二次转换。
    """
    naive = datetime.combine(d, datetime.min.time())
    return naive.replace(tzinfo=datetime.now().astimezone().tzinfo)


PAGE_SIZE = 20


def month_options() -> list[ft.dropdown.Option]:
    """生成 1-12 月下拉选项列表。"""
    return [ft.dropdown.Option(str(m)) for m in range(1, 13)]


def make_browse_handler(
    picker: ft.FilePicker,
    target_field: ft.TextField,
    target_btn,
    dialog_title: str,
    mode: str = "file",
    extensions: list[str] | None = None,
    log_fn=None,
):
    """创建文件/目录浏览处理函数。

    Args:
        picker: 已注册到 page.services 的 FilePicker 实例。
        target_field: 显示路径的 TextField。
        target_btn: 浏览成功后启用的按钮。
        dialog_title: 对话框标题。
        mode: "file" 使用 pick_files，"folder" 使用 get_directory_path。
        extensions: 文件模式下的允许扩展名（如 ["xlsx", "xls"]）。
        log_fn: 日志函数（可选）。
    """
    async def _browse(e: ft.ControlEvent):
        try:
            if mode == "folder":
                result = await picker.get_directory_path(
                    dialog_title=dialog_title,
                    initial_directory=_get_initial_directory(),
                )
                path = result
            else:
                files = await picker.pick_files(
                    dialog_title=dialog_title,
                    allowed_extensions=extensions,
                    initial_directory=_get_initial_directory(),
                )
                path = files[0].path if files else None
        except Exception as ex:
            if log_fn:
                log_fn(f"选择{'文件夹' if mode == 'folder' else '文件'}失败: {ex}")
            return
        if path:
            target_field.value = path
            _update_last_directory(path, is_dir=(mode == "folder"))
            _show_path_confirm(target_field)
            target_btn.disabled = False
            target_btn.update()

    return _browse


def create_confirm_dialog(
    page: ft.Page,
    title: str,
    message: str,
    on_confirm,
    confirm_text: str = "确认",
    cancel_text: str = "取消",
) -> ft.AlertDialog:
    """标准确认/取消弹窗，确认按钮使用 ERROR 色。"""
    try:
        from . import theme
    except ImportError:
        import gui.theme as theme

    def _on_cancel(e):
        page.pop_dialog()

    def _on_ok(e):
        page.pop_dialog()
        on_confirm(e)

    return ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text(message),
        actions=[
            ft.TextButton(cancel_text, on_click=_on_cancel),
            ft.TextButton(confirm_text, on_click=_on_ok,
                          style=ft.ButtonStyle(color=theme.ERROR)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )


class HeaderModeConfig:
    """工时表头模式切换控件组（Checkbox + ChipToggle + 模糊匹配 Checkbox）。

    用法：
        hmc = HeaderModeConfig(label="表头修改", tooltip="...")
        # 在布局中使用 hmc.toggle, hmc.mode.row, hmc.fuzzy
        # 在 refs 中注册 hmc.toggle, hmc.mode, hmc.fuzzy
    """

    def __init__(
        self,
        label: str = "表头修改",
        tooltip: str = "开启后按配置的映射关系重命名输出表头",
        fuzzy_label: str = "模糊匹配",
        fuzzy_tooltip: str = "按列名匹配时启用模糊匹配（允许列名部分匹配）",
        on_toggle_extra=None,
    ):
        self.toggle = ft.Checkbox(label=label, value=True, tooltip=tooltip)
        self.fuzzy = ft.Checkbox(
            label=fuzzy_label, value=False, tooltip=fuzzy_tooltip, visible=False,
        )
        self.mode = ChipToggle(
            options=[("position", "按位置"), ("name", "按列名")],
            on_change=self._on_mode_change,
        )
        self.mode.row.visible = self.toggle.value
        self._on_toggle_extra = on_toggle_extra
        self.toggle.on_change = self._on_toggle_change

    def _on_mode_change(self, val):
        self.fuzzy.visible = (val != "position")
        safe_update(self.fuzzy)

    def _on_toggle_change(self, e):
        enabled = self.toggle.value
        for chip in self.mode._chips:
            chip.disabled = not enabled
        self.mode.row.visible = enabled
        if not enabled:
            self.fuzzy.visible = False
        else:
            self.fuzzy.visible = (self.mode.value == "name")
        safe_update(self.mode.row, self.fuzzy)
        if self._on_toggle_extra:
            self._on_toggle_extra(enabled)


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
                logger.debug('Sort failed for column %s', self.column, exc_info=True)
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
