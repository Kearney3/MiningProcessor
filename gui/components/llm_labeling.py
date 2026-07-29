"""LLM 标注页面组件

完整工作流：选择文件 → 选择 Sheet → 列映射 → 筛选与导出 → 执行标注。
支持页面关闭时自动取消后台任务。
"""
import logging
import threading

import flet as ft
import pandas as pd

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


def _auto_detect(columns: list[str], field: str) -> str:
    for hint in COLUMN_HINTS.get(field, []):
        if hint in columns:
            return hint
    return columns[0] if columns else ""


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
    progress_bar = ft.ProgressBar(value=0, visible=False, height=6)
    progress_text = ft.Text("", size=11, color=theme.TEXT_SECONDARY, visible=False)

    # ── 内部状态 ──
    sample_data: list[dict] = []
    cancel_event = threading.Event()
    active_thread: threading.Thread | None = None

    # ── FilePicker ──
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    # ── 工具函数 ──

    def _set_col_options(columns: list[str]):
        for dd in (col_content, col_category, col_minor, col_status):
            dd.options = [ft.dropdown.Option(c) for c in columns]

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
        if not status_col or not sample_data:
            return
        values = sorted({str(r.get(status_col, "")) for r in sample_data if r.get(status_col)})
        status_suggestions.controls.clear()
        for v in values:
            status_suggestions.controls.append(
                ft.Container(
                    content=ft.Text(v, size=12, color=ft.Colors.GREY_700),
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    on_click=lambda _, val=v: _toggle_filter(val),
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
        ready = bool(
            path_field.value
            and sheet_dropdown.value
            and col_content.value
        )
        btn.disabled = not ready
        try:
            btn.update()
        except (RuntimeError, AttributeError):
            pass

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
            nonlocal columns_list, sample_data
            try:
                df = pd.read_excel(path, sheet_name=sheet, nrows=10)
                cols = list(df.columns)
                sample = df.fillna("").head(5).to_dict(orient="records")
            except Exception:
                cols, sample = [], []

            columns_list[:] = cols
            sample_data[:] = sample

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
                _check_ready()
                safe_update(
                    col_content, col_category, col_minor, col_status,
                    preview_table, preview_info, mapping_section, filter_section,
                    btn, status_suggestions,
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
    def _on_status_col_change(_e):
        _build_status_suggestions(col_status.value or "")
        _check_ready()
        try:
            status_suggestions.update()
        except (RuntimeError, AttributeError):
            pass

    col_status.on_change = _on_status_col_change
    col_content.on_change = _check_ready

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

        cancel_event.clear()
        from gui.logic import register_cancel_event
        register_cancel_event(cancel_event)

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
        status_text.value = f"正在标注（Sheet: {sheet_name}）..."
        safe_update(btn, cancel_btn, result_text, status_text, progress_bar, progress_text)

        nonlocal active_thread

        def _run():
            try:
                from func.label_maintenance_with_llm import process_maintenance_llm

                def _on_progress(text: str, data: dict):
                    pct_val = data.get("percent", 0) / 100

                    async def _update_ui():
                        progress_bar.value = pct_val
                        progress_text.value = text
                        safe_update(progress_bar, progress_text)

                    try:
                        page.run_task(_update_ui)
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
                    cancel_event=cancel_event,
                    progress_fn=_on_progress,
                )

                if cancel_event.is_set():
                    partial = result.get("llm_completed", 0)

                    async def _cancelled():
                        status_text.value = ""
                        result_text.value = f"已取消，已完成 {partial} 条（可断点续跑）"
                        result_text.color = ft.Colors.AMBER
                        btn.disabled = False
                        btn.text = "开始标注"
                        cancel_btn.visible = False
                        progress_bar.visible = False
                        progress_text.visible = False
                        safe_update(status_text, result_text, btn, cancel_btn, progress_bar, progress_text)

                    page.run_task(_cancelled)
                    return

                output = result.get("output", "")
                completed = result.get("llm_completed", 0)
                target = result.get("target_rows", 0)
                mode_label = "汇总统计" if result.get("export_mode") == "statistics" else "标注明细"

                async def _ok():
                    status_text.value = ""
                    result_text.value = (
                        f"标注完成: {completed}/{target} 条成功\n"
                        f"导出方式: {mode_label}\n"
                        f"输出: {output}"
                    )
                    result_text.color = theme.TEXT_PRIMARY
                    btn.disabled = False
                    btn.text = "开始标注"
                    cancel_btn.visible = False
                    progress_bar.visible = False
                    progress_text.visible = False
                    safe_update(status_text, result_text, btn, cancel_btn, progress_bar, progress_text)

                page.run_task(_ok)
            except Exception as exc:
                if cancel_event.is_set():
                    return
                err_msg = str(exc)

                async def _fail():
                    status_text.value = ""
                    result_text.value = f"标注失败: {err_msg}"
                    result_text.color = ft.Colors.RED
                    btn.disabled = False
                    btn.text = "开始标注"
                    cancel_btn.visible = False
                    progress_bar.visible = False
                    progress_text.visible = False
                    safe_update(status_text, result_text, btn, cancel_btn, progress_bar, progress_text)

                page.run_task(_fail)
            finally:
                from gui.logic import unregister_cancel_event
                unregister_cancel_event(cancel_event)
                active_thread = None

        active_thread = threading.Thread(target=_run, daemon=True)
        active_thread.start()

    async def _on_cancel(_e):
        cancel_event.set()
        status_text.value = "正在取消..."
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
                    ft.Row([btn, cancel_btn], spacing=8),
                    progress_bar,
                    progress_text,
                    status_text,
                    result_text,
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
        ft.Row([filter_input, ft.Button("添加", on_click=_add_filter_from_input)], spacing=8),
        filter_chip_row,
        ft.Text("留空则标注所有记录", size=11, color=theme.TEXT_SECONDARY),
        ft.Divider(),
        ft.Text("导出方式", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
        export_group,
    ])

    refs = {
        "path": path_field,
        "sheet": sheet_dropdown,
        "btn": btn,
        "status": status_text,
    }
    return container, refs
