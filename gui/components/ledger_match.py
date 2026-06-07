"""台账匹配工具区域组件"""
import datetime
import asyncio
import logging
import threading
from pathlib import Path

import pandas as pd
import flet as ft

from .common import _log_message, _last_directory as _import_dir, _update_last_directory, _cell_text, PAGE_SIZE, strip_date_only_times, create_confirm_dialog

try:
    from . import theme
except ImportError:
    import gui.theme as theme


# ========================================================================
# 辅助类：共享状态与控件引用
# ========================================================================

class _MatchState:
    """Holds all mutable state shared between the UI closures."""

    def __init__(self):
        self.all_sheets: dict[str, pd.DataFrame] = {}
        self.matched_all_sheets: dict[str, pd.DataFrame] = {}
        self.matched_sheets: dict[str, pd.DataFrame] = {}
        self.unmatched_sheets: dict[str, pd.DataFrame] = {}
        self.filtered_df: pd.DataFrame | None = None
        self.current_sheet: str = ""
        self.page: int = 0
        self.columns: list[str] = []
        self.sort_column: str | None = None
        self.sort_ascending: bool = True
        self.view_mode: str = "all"
        self.import_cancelled = threading.Event()


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
# 提取的大函数
# ========================================================================

async def _do_import(page, log, state: _MatchState, controls: _MatchControls, on_sheet_change_fn):
    """File import action -- extracted from the former on_import closure."""
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

    parsed_sheets: dict[str, pd.DataFrame] = {}

    try:
        from openpyxl import load_workbook

        # 使用 read_only 模式打开，可以获取行数
        wb = load_workbook(path, read_only=True, data_only=True)
        sheet_names = wb.sheetnames
        total_sheets = len(sheet_names)

        if total_sheets == 0:
            _log_message(log, "文件中没有 sheet", level=logging.WARNING)
            _hide_import_progress(state, controls)
            page.update()
            return

        for sheet_idx, sname in enumerate(sheet_names):
            if state.import_cancelled.is_set():
                break

            ws = wb[sname]
            # 获取行数（read_only 模式下 max_row 可用）
            total_rows = ws.max_row or 0
            total_cols = ws.max_column or 0

            if total_rows == 0 or total_cols == 0:
                parsed_sheets[sname] = pd.DataFrame()
                continue

            # 读取表头（第一行）
            headers = []
            for cell in next(ws.iter_rows(min_row=1, max_row=1)):
                val = cell.value
                if val is not None:
                    # strip 空白字符，避免列名匹配失败
                    headers.append(str(val).strip())
                else:
                    headers.append(f"Col{cell.column - 1}")

            # 分批读取数据行
            rows_data = []
            batch_size = 500
            rows_read = 0

            for row in ws.iter_rows(min_row=2, values_only=True):
                if state.import_cancelled.is_set():
                    break

                rows_data.append(list(row))
                rows_read += 1

                # 每 batch_size 行更新一次进度
                if rows_read % batch_size == 0:
                    progress = rows_read / total_rows if total_rows > 0 else 0
                    controls.import_progress_bar.value = progress
                    controls.import_progress_text.value = f"正在导入 {sname}: {rows_read}/{total_rows} 行"
                    page.update()
                    await asyncio.sleep(0)

            # 构建 DataFrame
            if rows_data:
                # 检查数据行长度与表头是否一致
                header_len = len(headers)
                row_lens = set(len(r) for r in rows_data)
                if len(row_lens) > 1 or (row_lens and header_len not in row_lens):
                    logging.getLogger(__name__).debug(
                        "Sheet %r: header_len=%d, row_lengths=%s",
                        sname, header_len, row_lens,
                    )
                df = pd.DataFrame(rows_data, columns=headers)
                df = strip_date_only_times(df)
            else:
                df = pd.DataFrame(columns=headers)

            parsed_sheets[sname] = df
            _log_message(log, f"已导入 {sname}: {len(df)} 行, {len(df.columns)} 列")

        wb.close()

    except Exception as ex:
        controls.file_label.value = f"读取失败: {ex}"
        controls.file_label.color = theme.ERROR
        _log_message(log, f"读取文件失败: {ex}", level=logging.ERROR)
        _hide_import_progress(state, controls)
        page.update()
        return

    _hide_import_progress(state, controls)

    if state.import_cancelled.is_set():
        _log_message(log, f"导入已取消（已解析 {len(parsed_sheets)}/{total_sheets} 个 sheet）")
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
        # 直接调用 _on_sheet_change 确保初始化完整
        on_sheet_change_fn(first)
    else:
        state.current_sheet = ""

    controls.match_btn.disabled = False
    controls.view_segment.disabled = False
    # build_table will be called via on_sheet_change_fn or here
    loaded = len(parsed_sheets)
    _log_message(log, f"已导入: {path} ({loaded}/{total_sheets} 个 sheet)")
    page.update()


async def _do_batch_match(
    page, log, state: _MatchState,
    df: pd.DataFrame,
    source_col: str,
    match_fn,
    result_keys: list[str],
    batch_size: int,
    total_work: int,
    progress_label: str,
    controls: _MatchControls,
    id_col: str | None = None,
) -> dict[str, list]:
    """通用批量匹配循环，返回 {result_key: [values...]}。"""
    results = {k: [] for k in result_keys}
    total_rows = len(df)
    for start in range(0, total_rows, batch_size):
        if state.import_cancelled.is_set():
            _log_message(log, "匹配已取消")
            break

        batch = df.iloc[start:start + batch_size]
        for _, row in batch.iterrows():
            n = str(row[source_col]) if source_col and source_col in df.columns and not pd.isna(row.get(source_col)) else None
            i_val = str(row[id_col]) if id_col and id_col in df.columns and not pd.isna(row.get(id_col)) else None
            if id_col:
                r = match_fn(name=n, device_id=i_val)
            else:
                r = match_fn(n) if n else None
            if r:
                for k in result_keys:
                    results[k].append(r.get(k, ""))
            else:
                for k in result_keys:
                    results[k].append("")

        # 更新进度
        processed = min(start + batch_size, total_rows)
        progress = processed / total_work
        controls.import_progress_bar.value = progress
        controls.import_progress_text.value = f"{progress_label}: {processed}/{total_work}"
        page.update()
        await asyncio.sleep(0)

    return results


async def _do_match(
    page, log, state: _MatchState, controls: _MatchControls,
    eq_ledger, oil_ledger, name_col, id_col, oil_col, build_table_fn,
):
    """Match action -- extracted from the former on_match closure."""
    def _get_current_df_for_match() -> pd.DataFrame | None:
        name = state.current_sheet
        if not name:
            return None
        if name in state.matched_all_sheets:
            return state.matched_all_sheets[name]
        if name in state.all_sheets:
            return state.all_sheets[name]
        return None

    df = _get_current_df_for_match()
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

    batch_size = 100
    total_rows = len(df)
    processed = 0

    try:
        result_df = df.copy()
        matched_count = 0

        # 设备匹配
        DEVICE_KEYS = ["标准设备名称", "标准设备编号", "标准公司名称"]
        has_truck_col = False
        has_excavator_col = False

        if eq_ledger and (name_col or id_col):
            # 检测是否同时存在矿卡名称和挖机名称（生产数据场景）
            has_truck_col = "矿卡名称" in result_df.columns
            has_excavator_col = "挖机名称" in result_df.columns

            if has_truck_col and has_excavator_col:
                # 生产数据场景：分别匹配矿卡和挖机，添加后缀
                total_work = total_rows * 2

                truck_r = await _do_batch_match(
                    page, log, state, df, "矿卡名称", eq_ledger.match_device, DEVICE_KEYS,
                    batch_size, total_work, "正在匹配矿卡", controls, id_col=id_col,
                )
                for k, suffix in zip(DEVICE_KEYS, ["（矿卡）", "（矿卡）", "（矿卡）"]):
                    result_df[k + suffix] = truck_r[k]
                matched_count += sum(1 for v in truck_r[DEVICE_KEYS[0]] if v)

                excav_r = await _do_batch_match(
                    page, log, state, df, "挖机名称",
                    lambda name, device_id=None: eq_ledger.match_device(name=name, device_id=device_id),
                    DEVICE_KEYS, batch_size, total_work, "正在匹配挖机", controls,
                )
                for k, suffix in zip(DEVICE_KEYS, ["（挖机）", "（挖机）", "（挖机）"]):
                    result_df[k + suffix] = excav_r[k]
            else:
                # 原有逻辑：单列匹配（非生产数据场景）
                equip_r = await _do_batch_match(
                    page, log, state, df, name_col, eq_ledger.match_device, DEVICE_KEYS,
                    batch_size, total_rows, "正在匹配设备", controls, id_col=id_col,
                )
                for k in DEVICE_KEYS:
                    result_df[k] = equip_r[k]
                matched_count += sum(1 for v in equip_r[DEVICE_KEYS[0]] if v)

        # 油品匹配
        OIL_KEY = "标准名称"
        oil_matched = 0
        if oil_ledger and oil_col and oil_col in result_df.columns:
            oil_r = await _do_batch_match(
                page, log, state, df, oil_col, lambda v: oil_ledger.match(v), [OIL_KEY],
                batch_size, total_rows, "正在匹配油品", controls,
            )
            result_df["标准油品名称"] = oil_r[OIL_KEY]
        # 保存匹配结果到单独的字典，不覆盖原始数据
        state.matched_all_sheets[state.current_sheet] = result_df
        state.page = 0
        build_table_fn()

        # 记录日志
        logging.getLogger(__name__).debug(
            "on_match: updated _matched_all_sheets[%r], columns=%s",
            state.current_sheet, list(result_df.columns),
        )

        # 拆分匹配成功/失败的行
        sheet = state.current_sheet
        if eq_ledger and (name_col or id_col):
            if has_truck_col and has_excavator_col:
                # 生产数据：合并两个匹配列的匹配状态
                mask_truck = result_df["标准设备名称（矿卡）"].astype(str).str.len() > 0
                mask_ex = result_df["标准设备名称（挖机）"].astype(str).str.len() > 0
                mask = mask_truck | mask_ex
            else:
                mask = result_df["标准设备名称"].astype(str).str.len() > 0
            state.matched_sheets[sheet] = result_df[mask].copy()
            state.unmatched_sheets[sheet] = result_df[~mask].copy()
        elif oil_ledger and oil_col:
            mask = result_df["标准油品名称"].astype(str).str.len() > 0
            state.matched_sheets[sheet] = result_df[mask].copy()
            state.unmatched_sheets[sheet] = result_df[~mask].copy()

        parts = []
        if eq_ledger and (name_col or id_col):
            total = len(result_df)
            parts.append(f"设备匹配: {matched_count}/{total}")
        if oil_ledger and oil_col:
            total = len(result_df)
            parts.append(f"油品匹配: {oil_matched}/{total}")
        controls.status_label.value = "  |  ".join(parts)
        _update_match_status(state, controls)
        _log_message(log, f"匹配完成: {controls.status_label.value}")
    except Exception as ex:
        _log_message(log, f"匹配失败: {ex}", level=logging.ERROR)
    finally:
        # 恢复 UI
        controls.import_progress_bar.visible = False
        controls.import_progress_text.visible = False
        controls.cancel_btn.visible = False
        controls.match_btn.disabled = False
        controls.match_btn.text = "执行匹配"
        controls.match_btn.icon = ft.Icons.SEARCH
        controls.export_btn.disabled = not bool(state.all_sheets)
        page.update()


async def _do_export(page, log, state: _MatchState, controls: _MatchControls):
    """Export action -- extracted from the former on_export closure."""
    if not state.all_sheets and not state.matched_sheets and not state.unmatched_sheets:
        _log_message(log, "没有数据可导出", level=logging.WARNING)
        return

    # 选择保存路径
    picker = ft.FilePicker()
    path = await picker.save_file(
        dialog_title="导出结果",
        file_name="匹配结果.xlsx",
        allowed_extensions=["xlsx"],
        initial_directory=_import_dir[0] or None,
    )
    if not path:
        return

    # 初始化进度条
    controls.import_progress_bar.visible = True
    controls.import_progress_text.visible = True
    controls.cancel_btn.visible = True
    state.import_cancelled.clear()
    controls.export_btn.disabled = True
    page.update()

    try:
        import xlsxwriter

        # 根据视图模式选择数据
        mode = state.view_mode
        if mode == "matched" and state.matched_sheets:
            df_to_export = pd.concat(state.matched_sheets.values(), ignore_index=True)
            sheet_name = "已匹配"
        elif mode == "unmatched" and state.unmatched_sheets:
            df_to_export = pd.concat(state.unmatched_sheets.values(), ignore_index=True)
            sheet_name = "未匹配"
        else:
            # 优先使用匹配后的完整数据，如果没有则使用原始数据
            export_data = state.matched_all_sheets if state.matched_all_sheets else state.all_sheets
            df_to_export = pd.concat(export_data.values(), ignore_index=True)
            sheet_name = "全部"

        # 创建 xlsxwriter 对象
        workbook = xlsxwriter.Workbook(path)
        try:
            worksheet = workbook.add_worksheet(sheet_name)

            # 定义日期格式
            date_fmt = workbook.add_format({'num_format': 'yyyy-mm-dd'})

            # 写入表头
            headers = list(df_to_export.columns)
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)

            # 识别日期列（包括 datetime64 和 date/datetime 对象）
            date_columns = set()
            for col in headers:
                if pd.api.types.is_datetime64_any_dtype(df_to_export[col]):
                    date_columns.add(col)
                else:
                    # 检查是否有 date/datetime 对象
                    sample = df_to_export[col].dropna().head(10)
                    if not sample.empty and sample.apply(
                        lambda v: isinstance(v, (datetime.date, datetime.datetime))
                    ).any():
                        date_columns.add(col)

            # 分批写入数据
            batch_size = 1000
            total_rows = len(df_to_export)

            for i in range(0, total_rows, batch_size):
                if state.import_cancelled.is_set():
                    _log_message(log, "导出已取消")
                    break

                batch = df_to_export.iloc[i:i+batch_size]
                for row_idx, (_, row) in enumerate(batch.iterrows(), start=i+1):
                    for col_idx, col_name in enumerate(headers):
                        value = row[col_name]
                        # 处理 NaN 值
                        if pd.isna(value):
                            worksheet.write(row_idx, col_idx, "")
                        elif col_name in date_columns:
                            # 日期列使用日期格式
                            try:
                                if isinstance(value, pd.Timestamp):
                                    worksheet.write_datetime(row_idx, col_idx, value.to_pydatetime(), date_fmt)
                                elif isinstance(value, (datetime.date, datetime.datetime)):
                                    worksheet.write_datetime(row_idx, col_idx, value, date_fmt)
                                else:
                                    worksheet.write(row_idx, col_idx, value)
                            except Exception:
                                worksheet.write(row_idx, col_idx, str(value))
                        else:
                            worksheet.write(row_idx, col_idx, value)

                # 更新进度
                processed = min(i + batch_size, total_rows)
                progress = processed / total_rows
                controls.import_progress_bar.value = progress
                controls.import_progress_text.value = f"正在导出第 {processed}/{total_rows} 行..."
                page.update()

                await asyncio.sleep(0)

        finally:
            # 确保 workbook 始终关闭，避免文件损坏和句柄泄漏
            workbook.close()

        if not state.import_cancelled.is_set():
            _log_message(log, f"已导出: {path}")
            _update_last_directory(path)
        else:
            # 取消时删除不完整的文件
            try:
                import os
                os.remove(path)
                _log_message(log, "已删除不完整的导出文件")
            except OSError:
                pass

    except Exception as ex:
        _log_message(log, f"导出失败: {ex}", level=logging.ERROR)
    finally:
        # 恢复 UI
        controls.import_progress_bar.visible = False
        controls.import_progress_text.visible = False
        controls.cancel_btn.visible = False
        controls.export_btn.disabled = False
        page.update()


# ========================================================================
# 模块级辅助函数（操作共享状态/控件，由闭包调用）
# ========================================================================

def _hide_import_progress(state: _MatchState, controls: _MatchControls):
    """隐藏导入进度 UI"""
    controls.import_progress_bar.visible = False
    controls.import_progress_text.visible = False
    controls.cancel_btn.visible = False
    controls.import_progress_bar.value = 0


def _update_match_status(state: _MatchState, controls: _MatchControls, sheet_name: str = None):
    """更新匹配计数显示"""
    sheet = sheet_name or state.current_sheet
    matched = state.matched_sheets.get(sheet)
    unmatched = state.unmatched_sheets.get(sheet)
    if matched is not None and unmatched is not None:
        m = len(matched)
        u = len(unmatched)
        controls.match_count_label.value = f"已匹配: {m}  |  未匹配: {u}"
    else:
        controls.match_count_label.value = ""


# ========================================================================
# 主入口
# ========================================================================

def create_ledger_match_section(
    page: ft.Page, log, ledger_refs: dict, oil_ledger_refs: dict
) -> tuple[ft.Container, dict]:
    """创建台账匹配工具区域，返回 (container, refs)"""

    state = _MatchState()

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
        disabled=True,  # 初始禁用，导入后启用
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
    def _get_current_df() -> pd.DataFrame | None:
        name = state.current_sheet
        if not name:
            return None
        # 优先返回匹配后的数据，如果没有则返回原始数据
        if name in state.matched_all_sheets:
            return state.matched_all_sheets[name]
        if name in state.all_sheets:
            return state.all_sheets[name]
        return None

    def _apply_filter_and_sort():
        """对当前 sheet 的 DataFrame 应用排序，更新 filtered_df"""
        df = _get_current_df()
        if df is None:
            state.filtered_df = None
            return

        result = df.copy()

        # 排序
        col = state.sort_column
        if col and col in result.columns:
            ascending = state.sort_ascending
            try:
                result = result.sort_values(by=col, ascending=ascending, kind="stable")
            except Exception:
                logging.getLogger(__name__).debug("排序失败: col=%s", col)

        state.filtered_df = result

    def _total_pages():
        df = _get_view_df()
        if df is None or df.empty:
            return 1
        return max(1, (len(df) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_page_controls():
        total = _total_pages()
        cur = state.page
        page_label.value = f"{cur + 1} / {total}"
        prev_btn.disabled = cur <= 0
        next_btn.disabled = cur >= total - 1

    def _show_import_progress(total: int):
        """显示导入进度 UI"""
        state.import_cancelled.clear()
        import_progress_bar.value = 0
        import_progress_bar.visible = True
        import_progress_text.value = f"正在解析 0/{total} 个 sheet..."
        import_progress_text.visible = True
        cancel_btn.visible = True
        match_btn.disabled = True

    def _update_import_progress(current: int, total: int, sheet_name: str):
        """更新导入进度"""
        import_progress_bar.value = current / total if total > 0 else 0
        import_progress_text.value = f"正在解析 {current}/{total}: {sheet_name}"

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
        enabled = oil_match_switch.value
        oil_dropdown.disabled = not enabled
        oil_dropdown.update()

    def _on_view_change(tab_index: int):
        modes = ["all", "matched", "unmatched"]
        state.view_mode = modes[tab_index]
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
                _apply_filter_and_sort()
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

    def _get_view_df() -> pd.DataFrame | None:
        """根据当前视图模式返回对应的 DataFrame"""
        mode = state.view_mode
        sheet = state.current_sheet
        if mode == "matched":
            return state.matched_sheets.get(sheet)
        elif mode == "unmatched":
            return state.unmatched_sheets.get(sheet)
        return state.filtered_df

    def build_table():
        _apply_filter_and_sort()
        df = _get_view_df()
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
        # 重置视图模式为"全部"，避免切换 sheet 后显示不一致
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
    # Wire action callbacks to extracted module-level functions
    # ========================================================================
    async def on_import(e):
        await _do_import(page, log, state, controls, _on_sheet_change)
        build_table()

    def _do_clear_impl():
        """清空的实际逻辑"""
        _hide_import_progress(state, controls)
        state.matched_sheets.clear()
        state.unmatched_sheets.clear()
        state.matched_all_sheets.clear()
        state.view_mode = "all"
        view_segment.selected = ["all"]
        view_segment.disabled = True
        state.all_sheets.clear()
        state.filtered_df = None
        state.current_sheet = ""
        state.page = 0
        state.sort_column = None
        state.columns.clear()
        state.sort_ascending = True
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

    # ── 文件操作栏 ──
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

    # ── 进度条 ──
    progress_row = ft.Row(
        [import_progress_bar, import_progress_text, cancel_btn],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ── 匹配配置（可折叠，2 列网格） ──
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

    # ── 操作栏（2 行） ──
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

                # ── 文件操作 ──
                theme.module_card([file_row, progress_row], spacing=6),

                # ── 匹配配置（折叠） ──
                match_config_collapsible,

                # ── 操作栏 ──
                action_rows,

                # ── 视图切换 ──
                view_segment,

                # ── 数据表格 ──
                ft.Container(
                    content=table_wrapper,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    bgcolor=theme.SURFACE_HIGH,
                    expand=True,
                ),

                # ── 分页 ──
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
