"""GUI 组件共享工具函数与状态"""
import flet as ft
import logging
import math
import threading
import pandas as pd
from pathlib import Path

from func.config_loader import get_user_config, update_user_config, get_anomaly_detection_config
from func.excel_utils import strip_date_only_times
from func.time_utils import local_midnight, local_today
from gui.i18n import t

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


def year_options(start_offset: int = -30, end_offset: int = 30) -> list[ft.dropdown.Option]:
    """生成年份下拉选项列表，基于当前年份动态计算范围（默认前后30年）。"""
    current = local_today().year
    return [ft.dropdown.Option(str(y)) for y in range(current + start_offset, current + end_offset + 1)]


def _log_message(log, message: str, level: int = logging.INFO):
    """兼容仅接收 message 的旧回调，也支持显式日志级别。

    .. deprecated:: 请使用 ``gui.utils._log_message`` 代替。
    """
    from gui.utils import _log_message as _impl
    return _impl(log, message, level=level)


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
    return local_midnight(d)


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
                log_fn(t("components:common.failedToSelect", target=t("components:common.folder") if mode == 'folder' else t("components:common.file"), ex=ex))
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
    confirm_text: str | None = None,
    cancel_text: str | None = None,
) -> ft.AlertDialog:
    """标准确认/取消弹窗，确认按钮使用 ERROR 色。"""
    if confirm_text is None:
        confirm_text = t("components:common.confirm")
    if cancel_text is None:
        cancel_text = t("components:common.cancel")
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
    """工时表头模式切换控件组（Checkbox + ChipToggle）。

    用法：
        hmc = HeaderModeConfig(label="表头修改", tooltip="...")
        # 在布局中使用 hmc.toggle, hmc.mode.row
        # 在 refs 中注册 hmc.toggle, hmc.mode
    """

    def __init__(
        self,
        label: str | None = None,
        tooltip: str | None = None,
        on_toggle_extra=None,
    ):
        if label is None:
            label = t("components:common.headerMapping")
        if tooltip is None:
            tooltip = t("components:common.whenEnabledRenameOutputHeadersUsingTheConfiguredMapping")
        self.toggle = ft.Checkbox(label=label, value=True, tooltip=tooltip)
        self.mode = ChipToggle(
            options=[("position", t("components:common.byPosition")), ("name", t("components:common.byColumnName"))],
        )
        self.mode.row.visible = self.toggle.value
        self._on_toggle_extra = on_toggle_extra
        self.toggle.on_change = self._on_toggle_change

    def _on_toggle_change(self, e):
        enabled = self.toggle.value
        for chip in self.mode._chips:
            chip.disabled = not enabled
        self.mode.row.visible = enabled
        safe_update(self.mode.row)
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


# 异常值明细表：保留高频定位字段，长说明在单元格内截断并可通过表格滚动查看。
_ANOMALY_RESULT_COLUMNS = [
    ("数据类型", "components:common.dataType", 86),
    ("行号", "components:common.row", 52),
    ("日期", "components:common.date", 92),
    ("班次", "components:common.shift", 56),
    ("设备名称", "components:common.equipment", 160),
    ("设备编号", "components:common.equipmentId", 90),
    ("异常列", "components:common.anomalyColumn", 100),
    ("异常值", "components:common.anomalyValue", 86),
    ("检测方法", "components:common.method", 82),
    ("说明", "components:common.note", 320),
]


def create_anomaly_results_table() -> dict:
    """创建异常值结果表及其更新函数。

    返回的 ``update(records)`` 可由处理完成回调调用；空列表会隐藏整个结果区，
    有数据时在页面底部显示可纵向、横向滚动的 DataTable。
    """
    try:
        from . import theme
    except ImportError:
        import gui.theme as theme

    columns = [name for name, _, _ in _ANOMALY_RESULT_COLUMNS]
    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text(t(label_key), size=12, no_wrap=True))
            for _, label_key, _ in _ANOMALY_RESULT_COLUMNS
        ],
        rows=[],
        column_spacing=12,
        heading_row_height=32,
        data_row_min_height=30,
        data_row_max_height=44,
    )
    count_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    table_view = ft.Container(
        content=ft.Column(
            [ft.Row([table], scroll=ft.ScrollMode.ALWAYS)],
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        height=250,
    )
    container = ft.Container(
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=theme.WARNING, size=17),
                        ft.Text(
                            t("components:common.anomalyDetails"),
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=theme.WARNING,
                        ),
                        count_text,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                table_view,
            ],
            spacing=6,
        ),
        bgcolor=theme.SURFACE,
        border=ft.Border.all(1, theme.WARNING),
        border_radius=theme.RADIUS_SM,
        padding=theme.SPACING_SM,
    )

    def update(records: list[dict] | None) -> None:
        rows = list(records or [])
        table.rows = []
        for record in rows:
            cells = []
            for column, _, width in _ANOMALY_RESULT_COLUMNS:
                color = theme.ERROR if column == "异常值" else theme.TEXT_PRIMARY
                if column == "说明":
                    color = theme.TEXT_SECONDARY
                cells.append(
                    ft.DataCell(
                        ft.Text(
                            _cell_text(record.get(column)),
                            width=width,
                            size=11,
                            color=color,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        )
                    )
                )
            table.rows.append(ft.DataRow(cells=cells))

        count_text.value = t("components:common.total", count=len(rows))
        container.visible = bool(rows)
        safe_update(container)

    return {
        "container": container,
        "table": table,
        "update": update,
    }


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
        suffix.tooltip = t("components:common.selected")
        safe_update(text_field)

        def _restore():
            suffix.icon = _original_icon
            suffix.icon_color = None
            suffix.tooltip = _original_tooltip
            safe_update(text_field)
        threading.Timer(1.5, _restore).start()
    else:
        safe_update(text_field)


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
        safe_update(self.row)

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
        label=t("components:common.theFirstRowIsTheHeaderExclude"),
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
        title=ft.Text(t("components:common.columnMappingConfig")),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("components:common.mapExcelColumnsToStandardColumns"), size=13),
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
            ft.TextButton(t("components:common.cancel"), on_click=on_cancel),
            ft.TextButton(
                t("components:common.confirmImport"),
                on_click=on_ok,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color="#FFFFFF"),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )


def create_anomaly_controls() -> dict:
    """创建异常值检测控件集，返回 refs dict。

    返回的 dict 包含:
    - "container": ft.Container（可嵌入布局）
    - "_anomaly_enabled": ft.Checkbox
    - "_anomaly_report": ft.Checkbox
    - "_anomaly_mode": callable → "flag" | "filter" | "handle"
    """
    try:
        from . import theme
    except ImportError:
        import gui.theme as theme

    _mode = ["flag"]

    anomaly_enabled = ft.Checkbox(
        label=t("components:common.enableAnomalyDetection"),
        value=False,
        tooltip=t("components:common.whenEnabledDetectAnomaliesInProcessedData"),
    )
    anomaly_report = ft.Checkbox(
        label=t("components:common.exportAnomalyReport"),
        value=False,
        tooltip=t("components:common.generateAnAnomalyReportExcelFile"),
    )
    anomaly_flag = ft.Checkbox(label=t("components:common.flagAnomalies"), value=True, tooltip=t("components:common.flagWithoutDeleting"))
    anomaly_filter = ft.Checkbox(label=t("components:common.filterAnomalies"), value=False, tooltip=t("components:common.removeAnomalousRowsMutuallyExclusiveWithFlagging"))
    anomaly_handle = ft.Checkbox(label=t("components:common.handleAnomalies"), value=False, tooltip=t("components:common.replaceWithConfiguredDefaultsMutuallyExclusiveWithFlagging"))

    def _set_mode(mode: str):
        _mode[0] = mode
        anomaly_flag.value = (mode == "flag")
        anomaly_filter.value = (mode == "filter")
        anomaly_handle.value = (mode == "handle")
        safe_update(anomaly_flag, anomaly_filter, anomaly_handle)

    def _on_enabled_change(e):
        enabled = anomaly_enabled.value
        for c in (anomaly_report, anomaly_flag, anomaly_filter, anomaly_handle):
            c.disabled = not enabled
        safe_update(anomaly_report, anomaly_flag, anomaly_filter, anomaly_handle)

    def _on_flag_change(e):
        if anomaly_flag.value:
            _set_mode("flag")
        elif _mode[0] == "flag":
            anomaly_flag.value = True
            safe_update(anomaly_flag)

    def _on_filter_change(e):
        if anomaly_filter.value:
            _set_mode("filter")
        elif _mode[0] == "filter":
            anomaly_filter.value = True
            safe_update(anomaly_filter)

    def _on_handle_change(e):
        if anomaly_handle.value:
            _set_mode("handle")
        elif _mode[0] == "handle":
            anomaly_handle.value = True
            safe_update(anomaly_handle)

    anomaly_enabled.on_change = _on_enabled_change
    anomaly_flag.on_change = _on_flag_change
    anomaly_filter.on_change = _on_filter_change
    anomaly_handle.on_change = _on_handle_change

    for c in (anomaly_report, anomaly_flag, anomaly_filter, anomaly_handle):
        c.disabled = not anomaly_enabled.value

    container = ft.Container(
        content=ft.Column([
            ft.Row([anomaly_enabled], spacing=8),
            ft.Container(
                content=ft.Column([
                    ft.Row([anomaly_report], spacing=8),
                    ft.Row([anomaly_flag, anomaly_filter, anomaly_handle], spacing=16),
                ], spacing=4),
                padding=ft.Padding.only(left=24),
            ),
        ], spacing=4),
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_SM,
        bgcolor=theme.SURFACE_HIGH,
    )

    return {
        "container": container,
        "_anomaly_enabled": anomaly_enabled,
        "_anomaly_report": anomaly_report,
        "_anomaly_mode": lambda: _mode[0],
    }


def build_anomaly_config_from_refs(refs: dict):
    """从 refs dict 构建 AnomalyConfig 实例。

    逐列检测阈值从用户配置中读取（持久化设置），不再从 GUI 运行时控件合并。
    """
    from func.anomaly.rules import AnomalyConfig

    enabled_ref = refs.get("_anomaly_enabled")
    if not enabled_ref or not enabled_ref.value:
        return AnomalyConfig(enabled=False)

    report_ref = refs.get("_anomaly_report")
    mode_fn = refs.get("_anomaly_mode")
    mode = mode_fn() if callable(mode_fn) else "flag"

    return AnomalyConfig.build_from_ui(
        enabled=True,
        generate_report=report_ref.value if report_ref else False,
        mode=mode,
    )


def create_sheet_selection_dialog(
    page: ft.Page,
    sheet_names: list[str],
    on_confirm,
) -> ft.AlertDialog:
    """创建 Sheet 选择对话框。

    Args:
        page: Flet 页面对象。
        sheet_names: Excel 文件中的 sheet 名列表。
        on_confirm: 回调 fn(sheet_name: str)，用户确认后触发。
    """
    selected = [sheet_names[0] if sheet_names else ""]

    def _on_radio_change(e):
        selected[0] = e.control.value

    radio_group = ft.RadioGroup(
        value=selected[0],
        content=ft.Column(
            [ft.Radio(value=s, label=s) for s in sheet_names],
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
        ),
        on_change=_on_radio_change,
    )

    def on_cancel(e):
        page.pop_dialog()
        page.update()

    def on_ok(e):
        page.pop_dialog()
        page.update()
        on_confirm(selected[0])

    return ft.AlertDialog(
        title=ft.Text(t("components:common.selectSheet")),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("components:common.selectASheetToImport"), size=13),
                    ft.Container(
                        content=radio_group,
                        expand=True,
                    ),
                ],
                spacing=8,
                expand=True,
            ),
            width=320,
            height=min(len(sheet_names) * 36 + 80, 400),
        ),
        actions=[
            ft.TextButton(t("components:common.cancel"), on_click=on_cancel),
            ft.TextButton(
                t("components:common.next"),
                on_click=on_ok,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color="#FFFFFF"),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
