"""台账匹配工具区域组件 — 纯 GUI 编排层"""
import asyncio
import logging
from pathlib import Path

import pandas as pd
import flet as ft

from func.ledger_match import (
    MatchState,
    import_excel,
    match_sheet,
    export_to_excel,
    get_current_df,
    get_view_df,
    apply_sort,
    build_match_count_text,
    DEVICE_RESULT_KEYS,
    OIL_RESULT_KEY,
)
from .common import (
    _log_message,
    _last_directory as _import_dir,
    _update_last_directory,
    _cell_text,
    PAGE_SIZE,
    create_confirm_dialog,
)

try:
    from . import theme
except ImportError:
    import gui.theme as theme


# ========================================================================
# 辅助类：控件引用（仅 UI 控件，不包含数据状态）
# ========================================================================

class _MatchControls:
    """Holds UI control references needed by the extracted action functions."""

    def __init__(
        self,
        file_label,
        sheet_dropdown,
        name_dropdown,
        id_dropdown,
        oil_dropdown,
        name_match_switch,
        id_match_switch,
        oil_match_switch,
        match_btn,
        export_btn,
        view_segment,
        status_label,
        match_count_label,
        import_progress_bar,
        import_progress_text,
        cancel_btn,
        data_table,
        empty_state,
    ):
        self.file_label = file_label
        self.sheet_dropdown = sheet_dropdown
        self.name_dropdown = name_dropdown
        self.id_dropdown = id_dropdown
        self.oil_dropdown = oil_dropdown
        self.name_match_switch = name_match_switch
        self.id_match_switch = id_match_switch
        self.oil_match_switch = oil_match_switch
        self.match_btn = match_btn
        self.export_btn = export_btn
        self.view_segment = view_segment
        self.status_label = status_label
        self.match_count_label = match_count_label
        self.import_progress_bar = import_progress_bar
        self.import_progress_text = import_progress_text
        self.cancel_btn = cancel_btn
        self.data_table = data_table
        self.empty_state = empty_state


# ========================================================================
# 模块级辅助函数（仅操作 UI 控件）
# ========================================================================

def _hide_import_progress(controls: _MatchControls):
    """隐藏导入进度 UI"""
    controls.import_progress_bar.visible = False
    controls.import_progress_text.visible = False
    controls.cancel_btn.visible = False
    controls.import_progress_bar.value = 0


def _update_match_status(state: MatchState, controls: _MatchControls, sheet_name: str = None):
    """更新匹配计数显示"""
    sheet = sheet_name or state.current_sheet
    controls.match_count_label.value = build_match_count_text(
        state.matched_sheets, state.unmatched_sheets, sheet,
    )


# ========================================================================
# 提取的大函数（UI 包装）
# ========================================================================

async def _do_import(page, log, state: MatchState, controls: _MatchControls, on_sheet_change_fn):
    """File import action — thin UI wrapper around func/ledger_match.import_excel."""
    picker = ft.FilePicker()
    files = await picker.pick_files(
        dialog_title="导入 Excel 文件",
        allowed_extensions=["xlsx", "xls"],
        initial_directory=_import_dir[0] or None,
    )
    if not files:
        return
    path = files[0].path

    # 显示进度条
    controls.import_progress_bar.visible = True
    controls.import_progress_text.visible = True
    controls.cancel_btn.visible = True
    state.import_cancelled.clear()
    controls.match_btn.disabled = True
    page.update()

    def _on_progress(progress: float, message: str):
        controls.import_progress_bar.value = progress
        controls.import_progress_text.value = message
        page.update()

    try:
        parsed_sheets, sheet_names = await asyncio.to_thread(
            import_excel, path, _on_progress, state.import_cancelled,
        )
    except Exception as ex:
        controls.file_label.value = f"读取失败: {ex}"
        controls.file_label.color = theme.ERROR
        _log_message(log, f"读取文件失败: {ex}", level=logging.ERROR)
        _hide_import_progress(controls)
        page.update()
        return

    _hide_import_progress(controls)

    if state.import_cancelled.is_set():
        _log_message(log, f"导入已取消（已解析 {len(parsed_sheets)}/{len(sheet_names)} 个 sheet）")
        if not parsed_sheets:
            page.update()
            return

    # 使用已解析的数据
    state.all_sheets.clear()
    state.all_sheets.update(parsed_sheets)
    logging.getLogger(__name__).debug(
        "on_import: _all_sheets keys=%s", list(state.all_sheets.keys())
    )

    _update_last_directory(path)
    controls.file_label.value = Path(path).name
    controls.file_label.color = ft.Colors.GREEN

    controls.sheet_dropdown.options = [ft.dropdown.Option(s) for s in sheet_names]
    if sheet_names:
        first = sheet_names[0]
        controls.sheet_dropdown.value = first
        on_sheet_change_fn(first)
    else:
        state.current_sheet = ""

    controls.match_btn.disabled = False
    controls.view_segment.disabled = False
    loaded = len(parsed_sheets)
    _log_message(log, f"已导入: {path} ({loaded}/{len(sheet_names)} 个 sheet)")
    page.update()


async def _do_match(
    page, log, state: MatchState, controls: _MatchControls,
    eq_ledger, oil_ledger, name_col, id_col, oil_col, build_table_fn,
):
    """Match action — thin UI wrapper around func/ledger_match.match_sheet."""
    df = get_current_df(state)
    if df is None or df.empty:
        _log_message(log, "没有数据可匹配", level=logging.WARNING)
        return

    if not eq_ledger and not oil_ledger:
        _log_message(log, "请先在设备台账或油品台账页导入台账", level=logging.WARNING)
        return

    if not name_col and not id_col and not oil_col:
        _log_message(log, "未启用任何匹配，跳过匹配")
        return

    # 初始化进度条
    controls.import_progress_bar.visible = True
    controls.import_progress_text.visible = True
    controls.cancel_btn.visible = True
    state.import_cancelled.clear()

    # Loading 状态
    controls.match_btn.disabled = True
    controls.match_btn.text = "匹配中..."
    controls.match_btn.icon = ft.Icons.HOURGLASS_TOP
    controls.export_btn.disabled = True
    page.update()

    def _on_progress(progress: float, message: str):
        controls.import_progress_bar.value = progress
        controls.import_progress_text.value = message
        page.update()

    try:
        result_df, matched_df, unmatched_df, matched_count = await asyncio.to_thread(
            match_sheet, df, eq_ledger, oil_ledger,
            name_col, id_col, oil_col,
            state.import_cancelled, _on_progress,
        )

        state.matched_all_sheets[state.current_sheet] = result_df
        state.matched_sheets[state.current_sheet] = matched_df
        state.unmatched_sheets[state.current_sheet] = unmatched_df
        state.page = 0
        build_table_fn()

        logging.getLogger(__name__).debug(
            "on_match: updated _matched_all_sheets[%r], columns=%s",
            state.current_sheet, list(result_df.columns),
        )

        # Build status text
        total = len(result_df)
        oil_matched = sum(1 for v in result_df.get(OIL_RESULT_KEY, pd.Series(dtype=str)) if v)
        parts = []
        if eq_ledger and (name_col or id_col):
            parts.append(f"设备匹配: {matched_count}/{total}")
        if oil_ledger and oil_col:
            parts.append(f"油品匹配: {oil_matched}/{total}")
        status_text = "  |  ".join(parts)
        controls.status_label.value = status_text
        _update_match_status(state, controls)
        _log_message(log, f"匹配完成: {status_text}")
    except Exception as ex:
        _log_message(log, f"匹配失败: {ex}", level=logging.ERROR)
    finally:
        controls.import_progress_bar.visible = False
        controls.import_progress_text.visible = False
        controls.cancel_btn.visible = False
        controls.match_btn.disabled = False
        controls.match_btn.text = "执行匹配"
        controls.match_btn.icon = ft.Icons.SEARCH
        controls.export_btn.disabled = not bool(state.all_sheets)
        page.update()


async def _do_export(page, log, state: MatchState, controls: _MatchControls):
    """Export action — thin UI wrapper around func/ledger_match.export_to_excel."""
    if not state.all_sheets and not state.matched_sheets and not state.unmatched_sheets:
        _log_message(log, "没有数据可导出", level=logging.WARNING)
        return

    picker = ft.FilePicker()
    save_path = await picker.save_file(
        dialog_title="导出结果",
        file_name="匹配结果.xlsx",
        allowed_extensions=["xlsx"],
        initial_directory=_import_dir[0] or None,
    )
    if not save_path:
        return

    # 初始化进度条
    controls.import_progress_bar.visible = True
    controls.import_progress_text.visible = True
    controls.cancel_btn.visible = True
    state.import_cancelled.clear()
    controls.export_btn.disabled = True
    page.update()

    def _on_progress(progress: float, message: str):
        controls.import_progress_bar.value = progress
        controls.import_progress_text.value = message
        page.update()

    # 选择导出数据
    mode = state.view_mode
    if mode == "matched" and state.matched_sheets:
        export_sheets = state.matched_sheets
        sheet_name = "已匹配"
    elif mode == "unmatched" and state.unmatched_sheets:
        export_sheets = state.unmatched_sheets
        sheet_name = "未匹配"
    else:
        export_sheets = state.matched_all_sheets if state.matched_all_sheets else state.all_sheets
        sheet_name = "全部"

    try:
        success = await asyncio.to_thread(
            export_to_excel, export_sheets, save_path, sheet_name,
            state.import_cancelled, _on_progress,
        )
        if success:
            _log_message(log, f"已导出: {save_path}")
            _update_last_directory(save_path)
        else:
            _log_message(log, "导出已取消")
    except Exception as ex:
        _log_message(log, f"导出失败: {ex}", level=logging.ERROR)
    finally:
        controls.import_progress_bar.visible = False
        controls.import_progress_text.visible = False
        controls.cancel_btn.visible = False
        controls.export_btn.disabled = False
        page.update()


# ========================================================================
# 主入口
# ========================================================================

def create_ledger_match_section(
    page: ft.Page, log, ledger_refs: dict, oil_ledger_refs: dict
) -> tuple[ft.Container, dict]:
    """创建台账匹配工具区域，返回 (container, refs)"""

    state = MatchState()

    # --- 控件 ---
    file_label = ft.Text("未导入文件", size=12, color=ft.Colors.GREY)

    sheet_dropdown = ft.Dropdown(
        label="Sheet",
        width=200,
        dense=True,
        options=[],
    )

    name_dropdown = ft.Dropdown(
        label="设备名称列",
        hint_text="（可选）",
        width=180,
        dense=True,
        options=[],
        disabled=True,
    )
    id_dropdown = ft.Dropdown(
        label="设备编号列",
        hint_text="（可选）",
        width=180,
        dense=True,
        options=[],
        disabled=True,
    )
    oil_dropdown = ft.Dropdown(
        label="油品列",
        hint_text="（可选）",
        width=180,
        dense=True,
        options=[],
        disabled=True,
    )

    name_match_switch = ft.Switch(
        label="名称匹配", value=False,
    )
    id_match_switch = ft.Switch(
        label="编号匹配", value=False,
    )
    oil_match_switch = ft.Switch(
        label="油品匹配", value=False,
    )

    match_btn = theme.primary_btn("执行匹配", icon=ft.Icons.SEARCH, disabled=True)
    export_btn = theme.secondary_btn("导出结果", icon=ft.Icons.DOWNLOAD, disabled=True)

    _VIEW_LABELS = ["全部", "已匹配", "未匹配"]
    _VIEW_MODES = ["all", "matched", "unmatched"]

    def _on_view_segment_change(e):
        sel = e.control.selected  # set of selected values
        if not sel:
            return
        val = next(iter(sel))
        idx = _VIEW_MODES.index(val) if val in _VIEW_MODES else 0
        _on_view_change(idx)

    from flet.controls.material.segmented_button import Segment

    view_segment = ft.SegmentedButton(
        selected=["all"],
        allow_empty_selection=False,
        segments=[
            Segment(label=ft.Text("全部"), value="all"),
            Segment(label=ft.Text("已匹配"), value="matched"),
            Segment(label=ft.Text("未匹配"), value="unmatched"),
        ],
        on_change=_on_view_segment_change,
        disabled=True,
    )

    status_label = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    match_count_label = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    import_progress_bar = ft.ProgressBar(
        value=0, height=6, visible=False, expand=True,
    )
    import_progress_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY, visible=False)
    cancel_btn = ft.Button(
        "取消导入",
        icon=ft.Icons.CANCEL,
        visible=False,
        style=ft.ButtonStyle(bgcolor=theme.ERROR, color="#FFFFFF"),
        height=36,
    )

    # --- 表格 ---
    data_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("等待导入数据..."))],
        rows=[],
        expand=True,
        sort_column_index=None,
        sort_ascending=True,
    )

    empty_state = theme.empty_state(
        ft.Icons.TABLE_CHART_OUTLINED,
        "暂无数据",
        "点击上方「导入文件」开始",
    )

    page_label = ft.Text("0 / 0", size=12, color=theme.TEXT_SECONDARY)
    prev_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT, tooltip="上一页", icon_size=18, disabled=True,
    )
    next_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT, tooltip="下一页", icon_size=18, disabled=True,
    )

    # --- Pack controls into a reference object ---
    controls = _MatchControls(
        file_label=file_label,
        sheet_dropdown=sheet_dropdown,
        name_dropdown=name_dropdown,
        id_dropdown=id_dropdown,
        oil_dropdown=oil_dropdown,
        name_match_switch=name_match_switch,
        id_match_switch=id_match_switch,
        oil_match_switch=oil_match_switch,
        match_btn=match_btn,
        export_btn=export_btn,
        view_segment=view_segment,
        status_label=status_label,
        match_count_label=match_count_label,
        import_progress_bar=import_progress_bar,
        import_progress_text=import_progress_text,
        cancel_btn=cancel_btn,
        data_table=data_table,
        empty_state=empty_state,
    )

    # ========================================================================
    # 内部工具函数（短闭包保留在主函数内）
    # ========================================================================

    def _total_pages():
        df = get_view_df(state)
        if df is None or df.empty:
            return 1
        return max(1, (len(df) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_page_controls():
        total = _total_pages()
        cur = state.page
        page_label.value = f"{cur + 1} / {total}"
        prev_btn.disabled = cur <= 0
        next_btn.disabled = cur >= total - 1

    def _on_cancel_import(e):
        state.import_cancelled.set()
        _log_message(log, "正在取消导入...")

    cancel_btn.on_click = _on_cancel_import

    def _on_name_toggle(e):
        name_dropdown.disabled = not name_match_switch.value
        name_dropdown.update()

    def _on_id_toggle(e):
        id_dropdown.disabled = not id_match_switch.value
        id_dropdown.update()

    def _on_oil_toggle(e):
        oil_dropdown.disabled = not oil_match_switch.value
        oil_dropdown.update()

    def _on_view_change(tab_index: int):
        state.view_mode = _VIEW_MODES[tab_index]
        state.page = 0
        build_table()

    name_match_switch.on_change = _on_name_toggle
    id_match_switch.on_change = _on_id_toggle
    oil_match_switch.on_change = _on_oil_toggle

    def _rebuild_columns(cols: list[str]):
        state.columns = cols

        def on_sort_handler(col_idx):
            def handler(e):
                state.sort_column = cols[e.column_index]
                state.sort_ascending = e.ascending
                apply_sort(state)
                state.page = 0
                build_table()
            return handler

        if cols:
            data_table.columns = [
                ft.DataColumn(
                    ft.Text(c, size=13, no_wrap=True),
                    on_sort=on_sort_handler(c),
                )
                for c in cols
            ]
            if state.sort_column and state.sort_column in cols:
                data_table.sort_column_index = cols.index(state.sort_column)
                data_table.sort_ascending = state.sort_ascending
            else:
                data_table.sort_column_index = None
        else:
            data_table.columns = [ft.DataColumn(ft.Text("等待导入数据..."))]

    def build_table():
        apply_sort(state)
        df = get_view_df(state)
        if df is None or df.empty:
            data_table.rows = []
            data_table.columns = [ft.DataColumn(ft.Text("等待导入数据..."))]
            empty_state.visible = True
            _update_page_controls()
            page.update()
            return
        empty_state.visible = False

        cols = list(df.columns)
        _rebuild_columns(cols)

        start = state.page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_df = df.iloc[start:end]

        rows = []
        for row_idx, row in page_df.iterrows():
            cells = []
            for c in cols:
                cell_value = _cell_text(row[c])
                cells.append(ft.DataCell(ft.Text(cell_value, size=13, selectable=True)))
            rows.append(ft.DataRow(cells=cells))

        data_table.rows = rows
        _update_page_controls()
        page.update()

    def _prev(e):
        if state.page > 0:
            state.page -= 1
            build_table()

    def _next(e):
        if state.page < _total_pages() - 1:
            state.page += 1
            build_table()

    prev_btn.on_click = _prev
    next_btn.on_click = _next

    # ========================================================================
    # Sheet 切换 & 列名自动匹配
    # ========================================================================
    def _update_column_dropdowns(cols: list[str]):
        options = [ft.dropdown.Option(c) for c in cols]
        for dd in [name_dropdown, id_dropdown, oil_dropdown]:
            old_val = dd.value
            dd.options = options
            if old_val and old_val in cols:
                dd.value = old_val
            else:
                dd.value = None
        if not name_dropdown.value:
            for c in cols:
                if c.strip() in ("设备名称", "矿卡名称"):
                    name_dropdown.value = c
                    break
        if not id_dropdown.value:
            for c in cols:
                if c.strip() == "设备编号":
                    id_dropdown.value = c
                    break
        if not oil_dropdown.value:
            for c in cols:
                if c.strip() in ("油品种类", "油品名称"):
                    oil_dropdown.value = c
                    break

    def _on_sheet_change(sheet_name: str):
        logging.getLogger(__name__).debug(
            "_on_sheet_change called: sheet_name=%r, _all_sheets.keys()=%s",
            sheet_name, list(state.all_sheets.keys())[:5],
        )
        if not sheet_name or sheet_name not in state.all_sheets:
            return
        state.current_sheet = sheet_name
        state.page = 0
        state.sort_column = None
        state.columns.clear()
        state.sort_ascending = True
        state.view_mode = "all"
        view_segment.selected = ["all"]
        df = state.all_sheets[sheet_name]
        _update_column_dropdowns(list(df.columns))
        _update_match_status(state, controls, sheet_name)
        build_table()

    def _on_sheet_dropdown_change(e):
        logging.getLogger(__name__).debug(
            "sheet_dropdown.on_select fired: value=%r", e.control.value
        )
        _on_sheet_change(e.control.value)

    sheet_dropdown.on_select = _on_sheet_dropdown_change

    # ========================================================================
    # Wire action callbacks
    # ========================================================================
    async def on_import(e):
        await _do_import(page, log, state, controls, _on_sheet_change)
        build_table()

    def _do_clear_impl():
        """清空的实际逻辑"""
        _hide_import_progress(controls)
        state.clear()
        state.import_cancelled.clear()  # clear() already calls this but be explicit
        view_segment.selected = ["all"]
        view_segment.disabled = True
        file_label.value = "未导入文件"
        file_label.color = ft.Colors.GREY
        sheet_dropdown.options = []
        sheet_dropdown.value = None
        name_dropdown.options = []
        name_dropdown.value = None
        id_dropdown.options = []
        id_dropdown.value = None
        oil_dropdown.options = []
        oil_dropdown.value = None
        match_btn.disabled = True
        export_btn.disabled = True
        status_label.value = ""
        data_table.columns = [ft.DataColumn(ft.Text("等待导入数据..."))]
        data_table.rows = []
        _log_message(log, "已清空")
        page.update()

    def _do_clear_confirmed(e):
        page.pop_dialog()
        _do_clear_impl()

    _clear_confirm_dialog = create_confirm_dialog(
        page, "确认清空",
        "确定要清空所有已导入数据和匹配结果吗？此操作不可撤销。",
        _do_clear_confirmed, confirm_text="确认清空",
    )

    def on_clear(e):
        if not state.all_sheets:
            return
        page.show_dialog(_clear_confirm_dialog)

    async def on_match(e):
        eq_ledger = ledger_refs.get("get_ledger", lambda: None)()
        oil_ledger = oil_ledger_refs.get("get_oil", lambda: None)()
        name_col = name_dropdown.value if name_match_switch.value else None
        id_col = id_dropdown.value if id_match_switch.value else None
        oil_col = oil_dropdown.value if oil_match_switch.value else None
        await _do_match(
            page, log, state, controls,
            eq_ledger, oil_ledger, name_col, id_col, oil_col, build_table,
        )

    async def on_export(e):
        await _do_export(page, log, state, controls)

    match_btn.on_click = on_match
    export_btn.on_click = on_export

    # ========================================================================
    # 布局
    # ========================================================================
    table_wrapper = ft.Column(
        controls=[
            ft.Row(
                controls=[data_table],
                scroll=ft.ScrollMode.AUTO,
            ),
            empty_state,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    file_row = ft.Row(
        [
            ft.Row(
                [
                    theme.secondary_btn("导入文件", icon=ft.Icons.UPLOAD, on_click=on_import),
                    theme.destructive_btn("清空", icon=ft.Icons.DELETE_SWEEP, on_click=on_clear),
                    file_label,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            sheet_dropdown,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    progress_row = ft.Row(
        [import_progress_bar, import_progress_text, cancel_btn],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    match_config_grid = ft.ResponsiveRow(
        [
            ft.Container(
                ft.Row([name_match_switch, name_dropdown], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                col={"xs": 12, "md": 6},
            ),
            ft.Container(
                ft.Row([id_match_switch, id_dropdown], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                col={"xs": 12, "md": 6},
            ),
            ft.Container(
                ft.Row([oil_match_switch, oil_dropdown], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                col={"xs": 12, "md": 6},
            ),
        ],
        run_spacing=4,
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    match_config_collapsible = theme.make_collapsible(
        title="匹配配置",
        subtitle="选择设备名称/编号/油品列进行匹配",
        icon=ft.Icons.TUNE,
        initially_expanded=True,
        content_controls=[match_config_grid],
    )

    action_rows = ft.Column(
        [
            ft.Row([match_btn, export_btn], spacing=8),
            ft.Row([status_label, match_count_label], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        spacing=6,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("台账匹配"),
                ft.Text(
                    "导入 Excel 文件后选择匹配列，执行匹配并导出结果。",
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),
                theme.module_card([file_row, progress_row], spacing=6),
                match_config_collapsible,
                action_rows,
                view_segment,
                ft.Container(
                    content=table_wrapper,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    bgcolor=theme.SURFACE_HIGH,
                    expand=True,
                ),
                ft.Row(
                    [prev_btn, page_label, next_btn],
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=theme.SPACING_MD,
            expand=True,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    refs = {"build_table": build_table}
    return container, refs
