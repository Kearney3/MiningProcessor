"""LLM 标注页面组件

完整工作流：选择文件 → 选择 Sheet → 列映射 → 筛选与导出 → 执行标注。
支持页面关闭时自动取消后台任务。
"""
import asyncio
from dataclasses import dataclass, field
import logging
import threading

import flet as ft

from .common import (
    _log_message,
    _update_last_directory,
    _show_path_confirm,
    _get_initial_directory,
    safe_update,
)

try:
    from . import theme
except ImportError:
    import gui.theme as theme

# ── 列名自动检测 ──────────────────────────────────────────

COLUMN_HINTS: dict[str, list[str]] = {
    "content": ["维修内容", "维修描述", "故障描述", "内容", "维修记录"],
    "category": ["大类", "分类", "故障大类", "系统分类"],
    "minor": ["小类", "子分类", "故障小类", "详细分类"],
    "status": ["分类方式", "标注方式", "分类状态", "标注状态", "分类来源"],
}
OUTPUT_DEFAULTS = {"category": "大类", "minor": "小类", "status": "分类方式"}


def _auto_detect(columns: list[str], field: str) -> str:
    for hint in COLUMN_HINTS.get(field, []):
        if hint in columns:
            return hint
    if field == "content":
        return columns[0] if columns else ""
    return OUTPUT_DEFAULTS.get(field, "")


def _validate_column_mapping(
    content: str,
    category: str,
    minor: str,
    status: str,
) -> str | None:
    values = [content, category, minor, status]
    if any(not value for value in values):
        return "请完整选择维修内容列和三个输出列"
    if len(set(values)) != len(values):
        return "列映射冲突：维修内容、大类、小类和分类方式必须使用不同列"
    return None


def _result_presentation(result: dict) -> dict:
    completed = int(result.get("llm_completed", 0))
    target = int(result.get("target_rows", 0))
    remaining = int(result.get("remaining_rows", 0))
    return {
        "completed": completed,
        "target": target,
        "remaining": remaining,
        "is_partial": remaining > 0,
        "progress": completed / target if target else 1,
        "summary": (
            f"{completed}/{target} 条成功"
            + (f" · {remaining} 条待重试" if remaining else " · 100%")
        ),
    }


@dataclass
class _LLMRunState:
    """单次 LLM 任务的可取消状态，避免相邻任务共享 Event。"""

    cancel_event: threading.Event = field(default_factory=threading.Event)
    finished: bool = False


# ── 组件 ──────────────────────────────────────────────────

def create_llm_labeling_section(page: ft.Page) -> tuple[ft.Container, dict]:
    """创建 LLM 标注页面，返回 (container, refs)。"""

    # ── Step 1: 文件 & Sheet ──
    path_field = ft.TextField(
        label="维修明细文件",
        hint_text="选择已处理的维修明细 Excel...",
        expand=True,
        read_only=False,
        color=theme.TEXT_PRIMARY,
        suffix=ft.IconButton(icon=ft.Icons.FOLDER_OPEN, tooltip="浏览"),
    )
    sheet_dropdown = ft.Dropdown(
        label="Sheet",
        width=200,
        options=[],
        hint_text="选择文件后加载",
    )

    # ── Step 2: 列映射 ──
    columns_list: list[str] = []
    col_content = ft.Dropdown(label="维修内容列", width=200, options=[])
    col_category = ft.Dropdown(label="大类列", width=200, options=[])
    col_minor = ft.Dropdown(label="小类列", width=200, options=[])
    col_status = ft.Dropdown(label="分类方式列", width=200, options=[])
    preview_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(""))],
        rows=[],
        column_spacing=12,
        data_row_min_height=28,
        heading_row_height=32,
        visible=False,
    )
    preview_info = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    mapping_error = ft.Text("", size=12, color=ft.Colors.RED_700, visible=False)
    mapping_section = ft.Container(visible=False)

    # ── Step 3: 筛选 & 导出 ──
    filter_chips: list[str] = []
    filter_chip_row = ft.Row(wrap=True, spacing=6)
    filter_input = ft.TextField(
        label="筛选分类方式值",
        hint_text='输入值（如"待确认"），逗号分隔，回车添加',
        expand=True,
        dense=True,
        color=theme.TEXT_PRIMARY,
    )
    status_suggestions = ft.Row(wrap=True, spacing=6)
    filter_notice = ft.Text("", size=12, color=ft.Colors.AMBER_700, visible=False)
    add_filter_btn = ft.Button("添加")
    export_details = ft.Radio(value="statistics", label="汇总统计（明细 + 统计表）")
    export_stats = ft.Radio(value="details", label="仅标注明细")
    export_group = ft.RadioGroup(
        value="statistics",
        content=ft.Row([export_stats, export_details], spacing=16),
    )
    filter_section = ft.Container(visible=False)

    # ── Step 4: 执行 ──
    btn = theme.primary_btn("开始标注", icon=ft.Icons.SMART_TOY, disabled=True)
    cancel_btn = ft.Button(
        "取消", icon=ft.Icons.STOP, visible=False,
        style=ft.ButtonStyle(color=ft.Colors.RED),
    )
    status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    result_text = ft.Text("", size=13, color=theme.TEXT_PRIMARY)
    progress_bar = ft.ProgressBar(value=0, visible=False, height=8)
    progress_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY, visible=False)
    progress_summary = ft.Text("", size=13, weight=ft.FontWeight.W_500, visible=False)
    progress_metrics = ft.Text("", size=12, color=theme.TEXT_SECONDARY, visible=False)
    task_panel = ft.Container(
        visible=False,
        padding=12,
        border_radius=8,
        bgcolor=theme.SURFACE_LOW,
        border=ft.Border.all(1, theme.BORDER),
    )

    # ── 内部状态 ──
    sample_data: list[dict] = []
    value_options: dict[str, list[tuple[str, int]]] = {}
    run_state_lock = threading.Lock()
    current_run: _LLMRunState | None = None
    progress_lock = threading.Lock()

    def _is_current_run(run_state: _LLMRunState) -> bool:
        with run_state_lock:
            return current_run is run_state

    def _is_active_run(run_state: _LLMRunState) -> bool:
        with run_state_lock:
            return current_run is run_state and not run_state.finished

    def _mark_run_finished(run_state: _LLMRunState) -> None:
        with run_state_lock:
            run_state.finished = True

    # ── FilePicker ──
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    # ── 工具函数 ──

    def _set_col_options(columns: list[str]):
        col_content.options = [ft.dropdown.Option(c) for c in columns]
        for dropdown, default in (
            (col_category, "大类"),
            (col_minor, "小类"),
            (col_status, "分类方式"),
        ):
            choices = list(columns)
            if default not in choices:
                choices.append(default)
            dropdown.options = [
                ft.dropdown.Option(
                    key=column,
                    text=column if column in columns else f"新建输出列：{column}",
                )
                for column in choices
            ]

    def _build_preview_table(columns: list[str], rows: list[dict]):
        preview_table.columns = [
            ft.DataColumn(ft.Text(c, size=12, weight=ft.FontWeight.W_500))
            for c in columns
        ]
        preview_table.rows = []
        for row in rows[:5]:
            cells = []
            for c in columns:
                val = str(row.get(c, ""))[:60]
                cells.append(ft.DataCell(ft.Text(val, size=11, color=theme.TEXT_PRIMARY)))
            preview_table.rows.append(ft.DataRow(cells=cells))
        preview_table.visible = bool(columns)

    def _build_filter_chips():
        filter_chip_row.controls.clear()
        for val in filter_chips:
            chip = ft.Container(
                content=ft.Row([
                    ft.Text(val, size=12, color=ft.Colors.BLUE_700),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE, icon_size=14,
                        icon_color=ft.Colors.BLUE_400,
                        on_click=lambda _, v=val: _remove_filter(v),
                        style=ft.ButtonStyle(padding=ft.Padding(0, 0, 0, 0)),
                    ),
                ], spacing=2, tight=True),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            )
            filter_chip_row.controls.append(chip)

    def _remove_filter(val: str):
        if val in filter_chips:
            filter_chips.remove(val)
            _build_filter_chips()
            filter_chip_row.update()

    def _add_filter_from_input(_e=None):
        if filter_input.disabled:
            return
        text = (filter_input.value or "").strip()
        if not text:
            return
        for part in text.split(","):
            v = part.strip()
            if v and v not in filter_chips:
                filter_chips.append(v)
        filter_input.value = ""
        _build_filter_chips()
        filter_chip_row.update()
        filter_input.update()

    filter_input.on_submit = _add_filter_from_input

    def _build_status_suggestions(status_col: str):
        status_suggestions.controls.clear()
        for value, count in value_options.get(status_col, []):
            status_suggestions.controls.append(
                ft.Container(
                    content=ft.Text(f"{value} · {count}", size=12, color=ft.Colors.GREY_700),
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    on_click=lambda _, val=value: _toggle_filter(val),
                    ink=True,
                )
            )

    def _toggle_filter(val: str):
        if val in filter_chips:
            filter_chips.remove(val)
        else:
            filter_chips.append(val)
        _build_filter_chips()
        filter_chip_row.update()

    def _check_ready(_e=None):
        error = _validate_column_mapping(
            col_content.value or "",
            col_category.value or "",
            col_minor.value or "",
            col_status.value or "",
        )
        mapping_error.value = error or ""
        mapping_error.visible = bool(error)
        ready = bool(path_field.value and sheet_dropdown.value and not error)
        btn.disabled = not ready
        safe_update(btn, mapping_error)

    # ── Sheet 加载 + 列预览 ──

    def _load_sheets_and_preview(path: str):
        def _fetch():
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                names = list(wb.sheetnames)
                wb.close()
            except Exception:
                names = []

            async def _update_ui():
                sheet_dropdown.options = [ft.dropdown.Option(s) for s in names]
                if "维修明细" in names:
                    sheet_dropdown.value = "维修明细"
                elif names:
                    sheet_dropdown.value = names[0]
                safe_update(sheet_dropdown)
                if sheet_dropdown.value:
                    _load_columns(path, sheet_dropdown.value)

            try:
                page.run_task(_update_ui)
            except (RuntimeError, AttributeError):
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _load_columns(path: str, sheet: str):
        def _fetch():
            nonlocal columns_list, sample_data, value_options
            try:
                from func.label_maintenance_with_llm import preview_excel_columns

                preview = preview_excel_columns(path, sheet)
                cols = preview["columns"]
                sample = preview["sample"]
                options = {
                    column: [
                        (str(item["value"]), int(item["count"]))
                        for item in items
                    ]
                    for column, items in preview.get("value_options", {}).items()
                }
            except Exception:
                cols, sample, options = [], [], {}

            columns_list[:] = cols
            sample_data[:] = sample
            value_options = options

            async def _update_ui():
                _set_col_options(columns_list)
                if columns_list:
                    col_content.value = _auto_detect(columns_list, "content")
                    col_category.value = _auto_detect(columns_list, "category")
                    col_minor.value = _auto_detect(columns_list, "minor")
                    col_status.value = _auto_detect(columns_list, "status")
                _build_preview_table(columns_list, sample_data)
                preview_info.value = f"共 {len(columns_list)} 列，前 5 行预览" if columns_list else "无法读取列"
                mapping_section.visible = True
                filter_section.visible = True if columns_list else False
                if col_status.value:
                    _build_status_suggestions(col_status.value)
                _sync_filter_availability()
                _check_ready()
                safe_update(
                    col_content, col_category, col_minor, col_status,
                    preview_table, preview_info, mapping_section, filter_section,
                    btn, status_suggestions, filter_input, add_filter_btn,
                    filter_notice, filter_chip_row, mapping_error,
                )

            try:
                page.run_task(_update_ui)
            except (RuntimeError, AttributeError):
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_sheet_change(_e):
        if path_field.value and sheet_dropdown.value:
            _load_columns(path_field.value, sheet_dropdown.value)

    sheet_dropdown.on_change = _on_sheet_change

    # ── 列映射变更时重新检测筛选建议 ──
    def _sync_filter_availability():
        available = bool(col_status.value in columns_list)
        filter_input.disabled = not available
        add_filter_btn.disabled = not available
        filter_notice.visible = not available
        filter_notice.value = (
            f"当前将新建“{col_status.value or '分类方式'}”列，"
            "不能按该列筛选；本次会标注全部记录。"
            if not available else ""
        )
        if not available:
            filter_chips.clear()
            _build_filter_chips()

    def _on_status_col_change(_e):
        _build_status_suggestions(col_status.value or "")
        _sync_filter_availability()
        _check_ready()
        safe_update(
            status_suggestions,
            filter_input,
            add_filter_btn,
            filter_notice,
            filter_chip_row,
        )

    col_status.on_change = _on_status_col_change
    col_content.on_change = _check_ready
    col_category.on_change = _check_ready
    col_minor.on_change = _check_ready

    # ── 文件选择 ──

    async def _on_browse(_e):
        try:
            result = await file_picker.pick_files(
                dialog_title="选择维修明细文件",
                allowed_extensions=["xlsx", "xls"],
                initial_directory=_get_initial_directory(),
            )
        except Exception as ex:
            _log_message(page.logger.error, f"选择文件失败: {ex}")
            return
        if result and result[0]:
            picked = result[0]
            path_field.value = picked.path
            _update_last_directory(picked.path, is_dir=False)
            _show_path_confirm(path_field)
            safe_update(path_field)
            _load_sheets_and_preview(picked.path)

    path_field.suffix.on_click = lambda e: page.run_task(_on_browse, e)

    # ── 执行标注 ──

    async def _on_process(_e):
        from func import config_loader

        path = path_field.value
        if not path:
            _log_message(page.logger, "请先选择维修明细文件", level=logging.WARNING)
            return
        llm_config = config_loader.get_llm_config()
        if not llm_config.get("url") or not llm_config.get("api_key"):
            _log_message(page.logger.error, "请先在用户配置中填写 LLM 接口 URL 和 API Key")
            return
        if not llm_config.get("model"):
            _log_message(page.logger.error, "请先在用户配置中选择 LLM 模型")
            return

        nonlocal current_run
        with run_state_lock:
            if current_run is not None and not current_run.finished:
                return
            run_state = _LLMRunState()
            current_run = run_state

        from gui.logic import register_cancel_event
        register_cancel_event(run_state.cancel_event)

        sheet_name = sheet_dropdown.value or "维修明细"
        content_col = col_content.value or "维修内容"
        category_col = col_category.value or "大类"
        minor_col = col_minor.value or "小类"
        status_col = col_status.value or "分类方式"
        export_mode = export_group.value or "statistics"
        filters = list(filter_chips) if filter_chips else None

        btn.disabled = True
        btn.text = "标注中..."
        cancel_btn.visible = True
        result_text.value = ""
        progress_bar.value = 0
        progress_bar.visible = True
        progress_text.value = ""
        progress_text.visible = True
        progress_summary.value = "准备发送标注任务…"
        progress_summary.visible = True
        progress_metrics.value = "成功 0  ·  跳过 0  ·  失败 0  ·  重试 0"
        progress_metrics.visible = True
        task_panel.visible = True
        status_text.value = f"正在标注（Sheet: {sheet_name}）..."
        safe_update(
            btn, cancel_btn, result_text, status_text, progress_bar,
            progress_text, progress_summary, progress_metrics, task_panel,
        )

        def _run():
            progress_delivery: dict = {"latest": None, "scheduled": False}

            try:
                from func.label_maintenance_with_llm import process_maintenance_llm

                def _on_progress(text: str, data: dict):
                    if not _is_active_run(run_state):
                        return
                    with progress_lock:
                        progress_delivery["latest"] = (text, data)
                        if progress_delivery["scheduled"]:
                            return
                        progress_delivery["scheduled"] = True

                    async def _flush_progress():
                        await asyncio.sleep(0.1)
                        if not _is_active_run(run_state):
                            return
                        with progress_lock:
                            latest = progress_delivery["latest"]
                            progress_delivery["scheduled"] = False
                        if latest is None:
                            return
                        latest_text, latest_data = latest
                        pct_val = latest_data.get("percent", 0) / 100
                        progress_bar.value = pct_val
                        progress_text.value = latest_text
                        current = latest_data.get("current", 0)
                        total = latest_data.get("total", 0)
                        eta = latest_data.get("eta_seconds")
                        eta_text = (
                            f" · 预计剩余 {max(1, round(float(eta) / 60))} 分钟"
                            if eta else ""
                        )
                        progress_summary.value = (
                            f"{current}/{total} 条 · "
                            f"{latest_data.get('percent', 0):.0f}%{eta_text}"
                        )
                        progress_metrics.value = (
                            f"成功 {latest_data.get('succeeded', 0)}  ·  "
                            f"跳过 {latest_data.get('skipped', 0)}  ·  "
                            f"失败 {latest_data.get('failed', 0)}  ·  "
                            f"重试 {latest_data.get('retried', 0)}  ·  "
                            f"{latest_data.get('rate', 0):.1f} 条/秒"
                        )
                        safe_update(
                            progress_bar,
                            progress_text,
                            progress_summary,
                            progress_metrics,
                        )

                    try:
                        page.run_task(_flush_progress)
                    except (RuntimeError, AttributeError):
                        pass

                result = process_maintenance_llm(
                    path,
                    llm_config=llm_config,
                    sheet_name=sheet_name,
                    content_column=content_col,
                    category_column=category_col,
                    minor_column=minor_col,
                    status_column=status_col,
                    filter_values=filters,
                    export_mode=export_mode,
                    cancel_event=run_state.cancel_event,
                    progress_fn=_on_progress,
                    concurrency=int(llm_config.get("concurrency", 10)),
                    batch_size=int(llm_config.get("batch_size", 50)),
                )
                _mark_run_finished(run_state)

                if run_state.cancel_event.is_set() or result.get("cancelled"):
                    partial = result.get("llm_completed", 0)
                    remaining = result.get("remaining_rows", 0)

                    async def _cancelled():
                        if not _is_current_run(run_state):
                            return
                        status_text.value = "任务已取消，当前进度已保留"
                        result_text.value = (
                            f"已完成 {partial} 条，剩余 {remaining} 条；"
                            "再次开始可从断点继续。"
                        )
                        result_text.color = ft.Colors.AMBER
                        btn.disabled = False
                        btn.text = "开始标注"
                        cancel_btn.visible = False
                        safe_update(
                            status_text, result_text, btn, cancel_btn,
                            progress_bar, progress_text, progress_summary,
                            progress_metrics, task_panel,
                        )

                    page.run_task(_cancelled)
                    return

                output = result.get("output", "")
                presentation = _result_presentation(result)
                completed = presentation["completed"]
                target = presentation["target"]
                remaining = presentation["remaining"]
                from_checkpoint = result.get("from_checkpoint", 0)
                mode_label = "汇总统计" if result.get("export_mode") == "statistics" else "标注明细"

                async def _ok():
                    if not _is_current_run(run_state):
                        return
                    status_text.value = (
                        "部分完成，当前进度已保留"
                        if presentation["is_partial"] else "标注完成"
                    )
                    result_text.value = (
                        f"成功标注: {completed}/{target} 条\n"
                        + (f"待重试: {remaining} 条\n" if remaining else "")
                        + f"断点复用: {from_checkpoint} 条\n"
                        + f"导出方式: {mode_label}\n"
                        + f"输出: {output}"
                    )
                    result_text.color = (
                        ft.Colors.AMBER
                        if presentation["is_partial"]
                        else theme.TEXT_PRIMARY
                    )
                    btn.disabled = False
                    btn.text = "开始标注"
                    cancel_btn.visible = False
                    progress_bar.value = presentation["progress"]
                    progress_summary.value = presentation["summary"]
                    safe_update(
                        status_text, result_text, btn, cancel_btn,
                        progress_bar, progress_text, progress_summary,
                        progress_metrics, task_panel,
                    )

                page.run_task(_ok)
            except Exception as exc:
                _mark_run_finished(run_state)
                err_msg = str(exc)

                async def _fail():
                    if not _is_current_run(run_state):
                        return
                    if run_state.cancel_event.is_set():
                        status_text.value = "任务已取消，当前进度已保留"
                        result_text.value = "再次开始可从断点继续未完成记录。"
                        result_text.color = ft.Colors.AMBER
                    else:
                        status_text.value = "标注失败，断点进度已保留"
                        result_text.value = f"标注失败: {err_msg}"
                        result_text.color = ft.Colors.RED
                    btn.disabled = False
                    btn.text = "开始标注"
                    cancel_btn.visible = False
                    safe_update(
                        status_text, result_text, btn, cancel_btn,
                        progress_bar, progress_text, progress_summary,
                        progress_metrics, task_panel,
                    )

                page.run_task(_fail)
            finally:
                from gui.logic import unregister_cancel_event
                _mark_run_finished(run_state)
                unregister_cancel_event(run_state.cancel_event)

        threading.Thread(target=_run, daemon=True).start()

    async def _on_cancel(_e):
        with run_state_lock:
            run_state = current_run
        if run_state is None:
            return
        run_state.cancel_event.set()
        status_text.value = "正在停止新批次，等待已发出的请求完成…"
        cancel_btn.visible = False
        safe_update(status_text, cancel_btn)

    btn.on_click = _on_process
    cancel_btn.on_click = _on_cancel

    # ── 布局 ──

    hints = ft.Text(
        "对已处理的维修明细文件进行大模型智能分类标注。\n"
        "请先在「用户配置 → LLM 标注配置」中配置接口信息。",
        size=12, color=theme.TEXT_SECONDARY,
    )

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("LLM 标注"),
                hints,
                # Step 1
                theme.module_card([
                    ft.Text("选择文件与 Sheet", size=13, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                    ft.Row([path_field, sheet_dropdown], spacing=8),
                ]),
                # Step 2
                mapping_section,
                # Step 3
                filter_section,
                # Step 4: 执行
                theme.module_card([
                    btn,
                    task_panel,
                ]),
            ],
            spacing=8,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    # ── 填充 mapping_section 和 filter_section ──

    mapping_section.content = theme.module_card([
        ft.Text("列映射", size=13, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        ft.Text("系统已自动识别常见列名，请确认或手动调整", size=12, color=theme.TEXT_SECONDARY),
        ft.Row([col_content, col_category], spacing=8),
        ft.Row([col_minor, col_status], spacing=8),
        mapping_error,
        preview_info,
        ft.Container(
            content=ft.Column([preview_table], scroll=ft.ScrollMode.AUTO),
            height=180,
            border=ft.Border.all(1, ft.Colors.GREY_200),
            border_radius=6,
            padding=8,
        ),
    ])

    filter_section.content = theme.module_card([
        ft.Text("筛选与导出", size=13, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        ft.Text("选择要进行 LLM 标注的分类方式值", size=12, color=theme.TEXT_SECONDARY),
        status_suggestions,
        filter_notice,
        ft.Row([filter_input, add_filter_btn], spacing=8),
        filter_chip_row,
        ft.Text("留空则标注所有记录", size=11, color=theme.TEXT_SECONDARY),
        ft.Divider(),
        ft.Text("导出方式", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        export_group,
    ])
    add_filter_btn.on_click = _add_filter_from_input
    task_panel.content = ft.Column(
        [
            ft.Row(
                [status_text, ft.Container(expand=True), cancel_btn],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            progress_summary,
            progress_bar,
            progress_metrics,
            progress_text,
            result_text,
        ],
        spacing=8,
    )

    refs = {
        "path": path_field,
        "sheet": sheet_dropdown,
        "btn": btn,
        "status": status_text,
        "progress": progress_bar,
        "progress_summary": progress_summary,
        "mapping_error": mapping_error,
    }
    return container, refs
