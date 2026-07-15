"""
GUI 业务逻辑层
处理各模块的后台任务、线程管理
"""
import asyncio
import logging
import traceback
from datetime import datetime
import flet as ft
import os
import pandas as pd
from func import config_loader
from func.excel_utils import get_output_filename
from func.excel_fuel import process_diesel_data as process_fuel_data
from func.excel_production_enhanced import MiningDataProcessor as ProdProcessor
from func.excel_electrical import parse_excel_data as process_electrical_data
from func.excel_worktime import process_excel_data as process_worktime_data
from func.excel_merger import merge_excel_files
from func.excel_batch import scan_files, process_files, MODULE_LABELS
from func.excel_maintenance import process_maintenance_data
from func.sync_to_minebase import sync as sync_to_minebase
from func.sync_to_minebase import test_db_connection
from func.sync_to_minebase import test_api_connection
from func.ledger_postprocess import apply_ledger_matching


from gui.utils import _log_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
# 保存按钮原始样式，以便恢复
_btn_original_styles: dict[int, ft.ButtonStyle] = {}

_LOADING_STYLE = ft.ButtonStyle(bgcolor="#CBD5E1", color="#64748B")

# 模块类型中文标签（扩展自 func.excel_batch 的公共标签）
_MODULE_LABELS = {
    **MODULE_LABELS,
    "merge": "文件合并",
    "maint": "维修记录",
    "batch": "批量处理",
}


class _SnackbarManager:
    """Encapsulates snackbar state to avoid mutable global."""

    def __init__(self) -> None:
        self._active: ft.SnackBar | None = None

    def show(self, page: ft.Page, message: str, is_error: bool = False) -> None:
        """Display a snackbar notification (thread-safe, single active instance)."""
        # Remove previous undismissed snackbar
        if self._active is not None:
            try:
                page.overlay.remove(self._active)
            except ValueError:
                pass
            self._active = None

        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
            duration=3000,
        )
        self._active = snackbar
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

        async def _cleanup() -> None:
            await asyncio.sleep(3.5)
            if self._active is snackbar:
                try:
                    page.overlay.remove(snackbar)
                    page.update()
                except (ValueError, RuntimeError):
                    pass
                self._active = None

        try:
            page.run_task(_cleanup)
        except (AttributeError, RuntimeError):
            import threading

            def _fallback_cleanup() -> None:
                try:
                    page.overlay.remove(snackbar)
                    page.update()
                except (ValueError, RuntimeError):
                    pass
                if self._active is snackbar:
                    self._active = None

            threading.Timer(3.5, _fallback_cleanup).start()

    def hide(self) -> None:
        """Dismiss the current snackbar if any."""
        self._active = None


_snackbar_mgr = _SnackbarManager()


def _show_snackbar(page: ft.Page, message: str, is_error: bool = False) -> None:
    _snackbar_mgr.show(page, message, is_error)


def _hide_snackbar() -> None:
    _snackbar_mgr.hide()


def set_btn_state(btn: ft.Button, enabled: bool, label: str = "处理"):
    """设置按钮状态：禁用时置灰并显示加载态文字，恢复时还原原始样式"""
    btn.disabled = not enabled
    btn.text = label
    if not enabled:
        # 保存原始样式，切换为置灰样式
        if id(btn) not in _btn_original_styles:
            _btn_original_styles[id(btn)] = btn.style
        btn.style = _LOADING_STYLE
    else:
        # 恢复原始样式
        original = _btn_original_styles.pop(id(btn), None)
        if original:
            btn.style = original
    btn.update()


# ---------------------------------------------------------------------------
# 台账匹配后处理（委托给 func/ledger_postprocess.py 共享模块）
# ---------------------------------------------------------------------------


def _apply_ledger_matching(output_file: str, equipment_ledger=None, oil_ledger=None, preloaded_sheets=None):
    """对已写入的 Excel 文件进行台账匹配后处理。"""
    apply_ledger_matching(output_file, equipment_ledger, oil_ledger, preloaded_sheets)


def _get_output_file(module_type: str, path: str, **kwargs) -> str | None:
    """根据模块类型和输入路径，推断输出文件路径"""
    if module_type == "batch":
        return None  # 台账匹配已在 batch_process 内部处理
    if module_type == "merge":
        keyword = kwargs.get("keyword", "")
        return os.path.join(path, f"{keyword}_合并.xlsx")

    year = kwargs.get("year", datetime.now().year)
    month = kwargs.get("month", 1)

    # 工时文件夹模式：输出文件名不同
    if module_type == "worktime" and os.path.isdir(path):
        return os.path.join(path, f"{year}{month:02d}_多文件合并_工作效率表.xlsx")

    filename = get_output_filename(module_type, year=year, month=month)
    if not filename:
        return None

    base = path if os.path.isdir(path) else os.path.dirname(path)
    return os.path.join(base, filename)


# ---------------------------------------------------------------------------
# 任务执行
# ---------------------------------------------------------------------------
def _dispatch_module(module_type: str, path: str, **kwargs) -> object | None:
    """Dispatch to the appropriate processor. Returns worktime_sheets or None."""
    skip_hidden_rows = kwargs.get("skip_hidden_rows", False)
    skip_hidden_cols = kwargs.get("skip_hidden_cols", False)
    if module_type == "fuel":
        process_fuel_data(path, kwargs.get("year"),
                          skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)
    elif module_type == "production":
        raw_start = kwargs.get("raw_start", -1)
        device_load_map = config_loader.get_device_load_map()
        processor = ProdProcessor(raw_start=raw_start, device_load_map=device_load_map,
                                  skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)
        logging.info(f"装载量参数：{device_load_map}")
        if os.path.isdir(path):
            output_file = os.path.join(path, "合并产量.xlsx")
            processor.process_folder(path, output_file)
        else:
            output_file = os.path.join(os.path.dirname(path) or ".", "合并产量.xlsx")
            processor.process_single_file(path, output_file)
    elif module_type == "electrical":
        process_electrical_data(path, kwargs.get("year"),
                         add_shift_column=kwargs.get("add_shift_column", False),
                         default_shift=kwargs.get("default_shift", "Day"),
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)
    elif module_type == "worktime":
        year = kwargs.get("year", datetime.now().year)
        month = kwargs.get("month", 1)
        header_mapping = kwargs.get("header_mapping", None)
        if os.path.isdir(path):
            from func.excel_worktime_multifile import process_directory
            output_file = os.path.join(path, f"{year}{month:02d}_多文件合并_工作效率表.xlsx")
            return process_directory(path, year, month, output_file,
                                    return_sheets=True, header_mapping=header_mapping,
                                    skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)
        else:
            file_dir = os.path.dirname(path) or "."
            output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
            return process_worktime_data(path, year, month, output_file,
                                      return_sheets=True, header_mapping=header_mapping,
                                      skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)
    elif module_type == "merge":
        keyword = kwargs.get("keyword", "")
        strip_time = kwargs.get("strip_time", False)
        sort_configs = kwargs.get("sort_configs", None)
        merge_excel_files(path, keyword, strip_time=strip_time, sort_configs=sort_configs,
                          skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)
    elif module_type == "maint":
        eq_ledger = kwargs.get("equipment_ledger")
        classifications = config_loader.get_maintenance_classifications()
        process_maintenance_data(
            path,
            eq_ledger=eq_ledger,
            classifications=classifications,
            skip_hidden_rows=skip_hidden_rows,
            skip_hidden_cols=skip_hidden_cols,
            split_by_year=kwargs.get("split_by_year", False),
            details_only=kwargs.get("details_only", False),
        )
    # batch 模块由 _execute_batch_task 单独处理
    return None


def _execute_task(module_type: str, path: str, **kwargs) -> str | None:
    """在后台线程中执行处理任务，返回错误信息或 None"""
    try:
        worktime_sheets = _dispatch_module(module_type, path, **kwargs)
    except Exception:
        logger.exception("Task execution failed: module=%s path=%s", module_type, path)
        return traceback.format_exc()

    # dispatch 完成后才 pop，确保维护模块等内部需要台账的模块能正常读取
    equipment_ledger = kwargs.pop("equipment_ledger", None)
    oil_ledger = kwargs.pop("oil_ledger", None)

    if not (equipment_ledger or oil_ledger):
        return None

    output_file = _get_output_file(module_type, path, **kwargs)
    if not output_file or not os.path.exists(output_file):
        return None

    sheets_data = worktime_sheets if module_type == "worktime" else None
    _apply_ledger_matching(output_file, equipment_ledger, oil_ledger,
                           preloaded_sheets=sheets_data)
    return None


async def run_task(page: ft.Page, module_type: str, path: str, log, **kwargs) -> None:
    """异步执行处理任务，按钮状态由调用方自行恢复"""

    label = _MODULE_LABELS.get(module_type, module_type)
    _log_message(log, f"[{label}] 开始处理...")
    error_message = await asyncio.to_thread(_execute_task, module_type, path, **kwargs)
    if error_message:
        _log_message(log, f"[{label}] 处理失败: {error_message}", level=logging.ERROR)
        _show_snackbar(page, f"{label}处理失败", is_error=True)
    else:
        _log_message(log, f"[{label}] 处理成功")
        _show_snackbar(page, f"{label}处理完成")


# ---------------------------------------------------------------------------
# 按钮点击处理（通用模板）
# ---------------------------------------------------------------------------
async def _safe_run_task(
    page: ft.Page,
    btn: ft.Button,
    label: str,
    path: str,
    log,
    module_type: str,
    **kwargs,
):
    """通用处理回调模板：禁用按钮 → 执行任务 → 恢复按钮 (M4)"""
    set_btn_state(btn, False, "处理中...")
    try:
        await run_task(page, module_type, path, log, **kwargs)
    finally:
        set_btn_state(btn, True, label)


# ---------------------------------------------------------------------------
# 各模块按钮回调
# ---------------------------------------------------------------------------
async def on_fuel_process(page: ft.Page, fuel_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False) -> None:
    """燃油处理按钮回调"""
    btn = fuel_refs["btn"]
    path = fuel_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件", level=logging.WARNING)
        return
    try:
        year = int(fuel_refs["year"].value)
    except (TypeError, ValueError):
        _log_message(log, "请先选择有效的年份", level=logging.WARNING)
        return
    await _safe_run_task(page, btn, "处理", path, log, "fuel",
                         year=year, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)


async def on_prod_process(page: ft.Page, prod_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False) -> None:
    """生产处理按钮回调"""
    btn = prod_refs["btn"]
    path = prod_refs["path"].value
    if not path:
        _log_message(log, "请先选择 Excel 文件或文件夹", level=logging.WARNING)
        return

    raw_start_text = (prod_refs["raw_start"].value or "-1").strip()
    try:
        raw_start = int(raw_start_text)
        if raw_start != -1 and raw_start < 1:
            raise ValueError
    except ValueError:
        _log_message(log, "请输入有效的 raw_start（正整数或-1【自动检测行】）", level=logging.WARNING)
        return

    await _safe_run_task(page, btn, "处理", path, log, "production",
                         raw_start=raw_start, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)


async def on_elec_process(page: ft.Page, elec_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False) -> None:
    """电力处理按钮回调"""
    btn = elec_refs["btn"]
    path = elec_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件", level=logging.WARNING)
        return

    year_text = elec_refs["year"].value
    try:
        year = int(year_text)
    except (TypeError, ValueError):
        _log_message(log, "请输入有效的年份", level=logging.WARNING)
        return

    add_shift = elec_refs.get("add_shift")
    default_shift_ref = elec_refs.get("default_shift")
    await _safe_run_task(page, btn, "处理", path, log, "electrical",
                         year=year,
                         add_shift_column=add_shift.value if add_shift else False,
                         default_shift=default_shift_ref.value if default_shift_ref else "Day",
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)


async def on_work_process(page: ft.Page, work_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False) -> None:
    """工时处理按钮回调"""
    btn = work_refs["btn"]
    path = work_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件", level=logging.WARNING)
        return
    try:
        year = int(work_refs["year"].value)
        month = int(work_refs["month"].value)
    except (TypeError, ValueError):
        _log_message(log, "请先选择有效的年份和月份", level=logging.WARNING)
        return
    # 表头映射：根据开关状态决定是否传入
    header_mapping = None
    header_toggle = work_refs.get("header_toggle")
    if header_toggle and header_toggle.value:
        from func.orchestration import build_worktime_header_mapping
        header_mode = work_refs.get("header_mode")
        header_fuzzy = work_refs.get("header_fuzzy")
        header_mapping = build_worktime_header_mapping(
            mode=header_mode.value if header_mode else None,
            fuzzy=header_fuzzy.value if header_fuzzy else None,
        )
    await _safe_run_task(page, btn, "处理", path, log, "worktime",
                         year=year, month=month,
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         header_mapping=header_mapping,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)


async def on_merge_process(page: ft.Page, merge_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False) -> None:
    """Excel 合并按钮回调"""
    btn = merge_refs["btn"]
    path = merge_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件夹", level=logging.WARNING)
        return
    keyword = (merge_refs["keyword"].value or "").strip()
    if not keyword:
        _log_message(log, "请输入文件名关键字", level=logging.WARNING)
        return
    # 收集排序配置
    sort_configs = []
    for cfg in merge_refs.get("sort_configs_state", []):
        col = (cfg.get("column") or "").strip()
        if col:
            sort_configs.append({"column": col, "ascending": bool(cfg.get("ascending", True))})
    strip_time = bool(merge_refs["strip_time"].value)
    await _safe_run_task(page, btn, "合并", path, log, "merge",
                         keyword=keyword, strip_time=strip_time, sort_configs=sort_configs,
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)


async def on_maint_process(page: ft.Page, maint_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False) -> None:
    """维修记录处理按钮回调"""
    btn = maint_refs["btn"]
    path = maint_refs["path"].value
    if not path:
        _log_message(log, "请先选择出勤统计表文件或文件夹", level=logging.WARNING)
        return
    split_by_year = bool(maint_refs.get("split_year") and maint_refs["split_year"].value)
    details_only = bool(maint_refs.get("details_only") and maint_refs["details_only"].value)
    await _safe_run_task(page, btn, "处理", path, log, "maint",
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         split_by_year=split_by_year, details_only=details_only)


def _set_controls_visible(controls: list, visible: bool):
    """安全地设置一组控件的可见性并更新。"""
    for ctrl in controls:
        if ctrl is not None:
            ctrl.visible = visible
            ctrl.update()


def _show_batch_progress(progress_row, progress_bar, progress_text, cancel_btn):
    if progress_bar is not None:
        progress_bar.value = 0.0
    if progress_text is not None:
        progress_text.value = "0%"
    if cancel_btn is not None:
        cancel_btn.disabled = False
    _set_controls_visible([progress_bar, progress_text, cancel_btn, progress_row], True)


def _hide_batch_progress(progress_row, progress_bar, progress_text, cancel_btn):
    _set_controls_visible([progress_bar, progress_text, cancel_btn, progress_row], False)


def _handle_batch_cancel(cancel_event, cancel_btn):
    if cancel_event is not None:
        cancel_event.set()
    if cancel_btn is not None:
        cancel_btn.disabled = True
        cancel_btn.update()


def _drain_batch_progress_queue_once(progress_queue, progress_bar, progress_text) -> float | None:
    """Drain all available items from the queue and update UI once. Returns last percent or None."""
    last_percent = None
    while True:
        try:
            payload = progress_queue.get_nowait()
        except Exception:
            break
        last_percent = payload.get("percent", last_percent)
    if last_percent is not None:
        _apply_progress_update(last_percent, progress_bar, progress_text)
    return last_percent


def _apply_progress_update(percent: float, progress_bar, progress_text) -> None:
    """Update progress bar and text controls with the given percent."""
    if progress_bar is not None:
        progress_bar.value = float(percent)
        progress_bar.update()
    if progress_text is not None:
        progress_text.value = f"{int(percent * 100)}%"
        progress_text.update()


async def _poll_batch_progress_queue(progress_queue, progress_bar, progress_text, done_flag: asyncio.Event):
    """Continuously drain the progress queue while the batch is running.

    Polls every 0.3 seconds. Stops when ``done_flag`` is set and the queue
    has been fully drained (one final sweep after ``done_flag``).
    """
    while not done_flag.is_set():
        try:
            await asyncio.wait_for(done_flag.wait(), timeout=0.3)
        except asyncio.TimeoutError:
            # Timeout expired -> poll the queue
            _drain_batch_progress_queue_once(progress_queue, progress_bar, progress_text)

    # Final drain after the worker thread has finished
    _drain_batch_progress_queue_once(progress_queue, progress_bar, progress_text)


async def on_batch_process(page: ft.Page, batch_refs: dict, log, equipment_ledger=None, oil_ledger=None) -> None:
    """批量处理按钮回调（带文件扫描 + 缺失确认弹窗）"""
    import queue
    import threading

    path = batch_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件夹", level=logging.WARNING)
        return

    btn = batch_refs["btn"]
    set_btn_state(btn, False, "扫描中...")

    try:
        year = int(batch_refs["year"].value)
        month = int(batch_refs["month"].value)
    except (TypeError, ValueError):
        _log_message(log, "请先选择有效的年份和月份", level=logging.WARNING)
        set_btn_state(btn, True, "批量处理")
        return
    if batch_refs["auto_detect"].value:
        raw_start = -1
    else:
        raw_start_text = (batch_refs.get("raw_start_input") and batch_refs["raw_start_input"].value or "-1").strip()
        try:
            raw_start = int(raw_start_text)
            if raw_start != -1 and raw_start < 1:
                raise ValueError
        except ValueError:
            _log_message(log, "请输入有效的 raw_start（正整数或-1【自动检测行】）", level=logging.WARNING)
            set_btn_state(btn, True, "开始处理")
            return
    merge_output = bool(batch_refs["merge"].value)

    # 表内合并选项
    table_merge_config = None
    table_merge_toggle = batch_refs.get("table_merge")
    if table_merge_toggle and table_merge_toggle.value:
        base_table_type = batch_refs.get("base_table")
        base_type = base_table_type.value if base_table_type else "fuel"
        table_merge_config = {"base_type": base_type}

    progress_bar = batch_refs.get("progress_bar")
    progress_text = batch_refs.get("progress_text")
    progress_row = batch_refs.get("progress_row")
    cancel_btn = batch_refs.get("cancel_btn")
    cancel_event = batch_refs.get("cancel_event")
    if cancel_event is None and cancel_btn is not None:
        cancel_event = threading.Event()
        batch_refs["cancel_event"] = cancel_event
    # 每次运行前重置取消状态，避免上次取消影响本次运行
    if cancel_event is not None:
        cancel_event.clear()
    if cancel_btn is not None:
        cancel_btn.on_click = lambda e: _handle_batch_cancel(cancel_event, cancel_btn)
    _show_batch_progress(progress_row, progress_bar, progress_text, cancel_btn)
    progress_queue = queue.Queue()

    try:
        # ── 第一阶段：扫描文件 ──
        try:
            matched, missing = await asyncio.to_thread(scan_files, path)
        except Exception as ex:
            _log_message(log, f"文件扫描失败: {ex}", level=logging.ERROR)
            return

        found_labels = [MODULE_LABELS.get(k, k) for k in matched]
        missing_labels = [MODULE_LABELS.get(k, k) for k in missing]
        _log_message(log, f"扫描完成 — 已找到: {', '.join(found_labels) or '无'}; 未找到: {', '.join(missing_labels) or '无'}")

        # ── 第二阶段：表内合并基准表验证 & 缺失确认弹窗 ──
        if table_merge_config:
            base_type = table_merge_config["base_type"]
            # 燃油基准需要 fuel，工时基准需要 worktime
            required_for_base = "fuel" if base_type == "fuel" else "worktime"
            if required_for_base not in matched:
                base_label = MODULE_LABELS.get(required_for_base, required_for_base)
                _log_message(log, f"表内合并需要{base_label}数据，但未找到对应文件", level=logging.ERROR)
                return

        if missing:
            # 表内合并模式下，只警告非基准表缺失；否则沿用原逻辑
            event = threading.Event()
            should_continue = [True]

            def _on_confirm(e):
                page.pop_dialog()
                should_continue[0] = True
                event.set()

            def _on_cancel(e):
                page.pop_dialog()
                should_continue[0] = False
                event.set()

            missing_text = "、".join(missing_labels)
            if table_merge_config:
                msg = f"以下类型的数据文件未在文件夹中检测到：\n\n{missing_text}\n\n表内合并将跳过缺失部分，是否继续？"
            else:
                msg = f"以下类型的数据文件未在文件夹中检测到：\n\n{missing_text}\n\n是否继续处理已找到的数据？"
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("部分数据文件未找到"),
                content=ft.Text(msg),
                actions=[
                    ft.TextButton("继续处理", on_click=_on_confirm),
                    ft.TextButton("取消", on_click=_on_cancel),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

            # 等待用户操作（带超时防死锁）
            confirmed = await asyncio.to_thread(event.wait, 300)
            if not confirmed or not should_continue[0]:
                _log_message(log, "用户取消了批量处理", level=logging.WARNING)
                return

        # 日期筛选参数
        filter_date = None
        if batch_refs.get("date_filter_toggle") and batch_refs["date_filter_toggle"].value:
            filter_date = batch_refs["selected_date"][0]

        # 表头映射：根据开关状态决定是否传入
        worktime_header_mapping = None
        header_toggle = batch_refs.get("header_toggle")
        if header_toggle and header_toggle.value:
            from func.orchestration import build_worktime_header_mapping
            header_mode = batch_refs.get("header_mode")
            header_fuzzy = batch_refs.get("header_fuzzy")
            worktime_header_mapping = build_worktime_header_mapping(
                mode=header_mode.value if header_mode else None,
                fuzzy=header_fuzzy.value if header_fuzzy else None,
            )

        # ── 第三阶段：执行处理 ──
        # 跳过隐藏行/列
        skip_hidden_rows = False
        skip_hidden_cols = False
        _sh_rows_toggle = batch_refs.get("_skip_hidden_rows_toggle")
        _sh_cols_toggle = batch_refs.get("_skip_hidden_cols_toggle")
        if _sh_rows_toggle:
            skip_hidden_rows = _sh_rows_toggle.value
        if _sh_cols_toggle:
            skip_hidden_cols = _sh_cols_toggle.value

        set_btn_state(btn, False, "处理中...")
        done_flag = asyncio.Event()
        progress_poller = asyncio.create_task(
            _poll_batch_progress_queue(progress_queue, progress_bar, progress_text, done_flag)
        )
        try:
            thread_result = {}
            def _batch_target():
                try:
                    thread_result["value"] = process_files(
                        path, matched, year, month, raw_start, merge_output,
                        equipment_ledger, oil_ledger, filter_date,
                        worktime_header_mapping,
                        table_merge_config,
                        progress_cb=progress_queue.put_nowait,
                        cancel_event=cancel_event,
                        skip_hidden_rows=skip_hidden_rows,
                        skip_hidden_cols=skip_hidden_cols,
                    )
                except Exception as ex:
                    thread_result["error"] = ex

            await asyncio.to_thread(_batch_target)
            # Signal the poller to do its final drain and stop
            done_flag.set()
            await progress_poller
            if "error" in thread_result:
                raise thread_result["error"]
            if cancel_event is not None and cancel_event.is_set():
                _log_message(log, "用户取消了批量处理", level=logging.WARNING)
                _show_snackbar(page, "批量处理已取消")
            else:
                _log_message(log, "批量处理完成")
                _show_snackbar(page, "批量处理完成")
        except Exception as ex:
            # Ensure poller is cancelled on error to prevent task leak
            done_flag.set()
            if not progress_poller.done():
                progress_poller.cancel()
                try:
                    await progress_poller
                except asyncio.CancelledError:
                    pass
            _log_message(log, f"批量处理失败: {ex}", level=logging.ERROR)
            _show_snackbar(page, f"批量处理失败: {ex}", is_error=True)

    finally:
        # 确保所有路径（包括早期返回）都清理进度条和按钮状态
        _hide_batch_progress(progress_row, progress_bar, progress_text, cancel_btn)
        set_btn_state(btn, True, "批量处理")


# ---------------------------------------------------------------------------
# 初始化 & 绑定
# ---------------------------------------------------------------------------
def _get_ledgers_from_refs(
    module_refs: dict,
    ledger_refs: dict,
    oil_ledger_refs: dict,
) -> tuple:
    """根据独立开关状态获取台账实例"""
    eq_toggle = module_refs.get("_match_eq_toggle")
    oil_toggle = module_refs.get("_match_oil_toggle")

    eq = None
    if eq_toggle and eq_toggle.value:
        eq = ledger_refs.get("get_ledger", lambda: None)()
        if eq is None:
            logging.warning("设备台账匹配已启用，但设备台账未加载")

    oil = None
    if oil_toggle and oil_toggle.value:
        oil = oil_ledger_refs.get("get_oil", lambda: None)()
        if oil is None:
            logging.warning("油品台账匹配已启用，但油品台账未加载")

    return eq, oil


def _make_module_handler(
    page: ft.Page,
    module_refs: dict,
    module_key: str,
    log,
    ledger_refs: dict,
    oil_ledger_refs: dict,
    callback,
):
    """Create a click handler that resolves ledgers and invokes *callback*."""

    async def handler(e: ft.ControlEvent) -> None:
        eq, oil = _get_ledgers_from_refs(module_refs, ledger_refs, oil_ledger_refs)
        skip_hidden_rows = False
        skip_hidden_cols = False
        _sh_rows = module_refs.get("_skip_hidden_rows_toggle")
        _sh_cols = module_refs.get("_skip_hidden_cols_toggle")
        if _sh_rows:
            skip_hidden_rows = _sh_rows.value
        if _sh_cols:
            skip_hidden_cols = _sh_cols.value
        await callback(page, module_refs[module_key], log,
                       equipment_ledger=eq, oil_ledger=oil,
                       skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols)

    return handler


def wire_processing_buttons(
    module_refs: dict,
    page: ft.Page,
    log,
    ledger_refs: dict | None = None,
    oil_ledger_refs: dict | None = None,
) -> None:
    """
    将模块 refs 中的按钮绑定到处理回调
    必须在模块区域创建完成后调用
    """
    ledger_refs = ledger_refs or {}
    oil_ledger_refs = oil_ledger_refs or {}

    _MODULE_CALLBACKS = [
        ("fuel", on_fuel_process),
        ("prod", on_prod_process),
        ("elec", on_elec_process),
        ("work", on_work_process),
        ("merge", on_merge_process),
        ("maint", on_maint_process),
    ]

    for key, callback in _MODULE_CALLBACKS:
        module_refs[key]["btn"].on_click = _make_module_handler(
            page, module_refs, key, log, ledger_refs, oil_ledger_refs, callback,
        )

    # Batch
    if "batch" in module_refs:
        async def handle_batch_click(e: ft.ControlEvent) -> None:
            eq_toggle = module_refs["batch"].get("match_eq_toggle")
            oil_toggle = module_refs["batch"].get("match_oil_toggle")
            eq = ledger_refs.get("get_ledger", lambda: None)() if eq_toggle and eq_toggle.value else None
            oil = oil_ledger_refs.get("get_oil", lambda: None)() if oil_toggle and oil_toggle.value else None
            await on_batch_process(page, module_refs["batch"], log, equipment_ledger=eq, oil_ledger=oil)
        module_refs["batch"]["btn"].on_click = handle_batch_click


async def on_sync_process(page: ft.Page, sync_refs: dict, log) -> None:
    """MineBase 同步按钮回调"""
    path = sync_refs["path"].value
    if not path:
        _log_message(log, "[数据同步] 请先选择输出目录", level=logging.WARNING)
        _show_snackbar(page, "请选择输出目录", is_error=True)
        return

    mode_toggle = sync_refs["mode"]
    mode = mode_toggle.value if mode_toggle else "api"

    type_checks = sync_refs["types"]
    selected_types = [k for k, cb in type_checks.items() if cb.value]
    if not selected_types:
        _log_message(log, "[数据同步] 请至少选择一种数据类型", level=logging.WARNING)
        _show_snackbar(page, "请选择数据类型", is_error=True)
        return

    dry_run = sync_refs["dry_run"].value
    btn = sync_refs["btn"]
    result_text = sync_refs["result_text"]

    # 年份/月份
    year_val = sync_refs.get("year")
    month_val = sync_refs.get("month")
    year = int(year_val.value) if year_val and year_val.value else None
    month = int(month_val.value) if month_val and month_val.value else None

    # 日期范围
    date_filter_toggle = sync_refs.get("date_filter_toggle")
    date_filter_on = date_filter_toggle.value if date_filter_toggle else True
    date_start_val = sync_refs.get("date_start")
    date_end_val = sync_refs.get("date_end")
    date_start = date_start_val.value.strip() if date_filter_on and date_start_val and date_start_val.value else None
    date_end = date_end_val.value.strip() if date_filter_on and date_end_val and date_end_val.value else None

    # 工时表头映射 & 台账匹配
    apply_header_val = sync_refs.get("apply_header")
    apply_header = apply_header_val.value if apply_header_val else True
    eq_ledger_val = sync_refs.get("use_equipment_ledger")
    oil_ledger_val = sync_refs.get("use_oil_ledger")
    use_equipment_ledger = eq_ledger_val.value if eq_ledger_val else False
    use_oil_ledger = oil_ledger_val.value if oil_ledger_val else True

    # 跳过隐藏行/列
    skip_hidden_rows_val = sync_refs.get("skip_hidden_rows")
    skip_hidden_cols_val = sync_refs.get("skip_hidden_cols")
    skip_hidden_rows = skip_hidden_rows_val.value if skip_hidden_rows_val else False
    skip_hidden_cols = skip_hidden_cols_val.value if skip_hidden_cols_val else False

    set_btn_state(btn, False, "同步中...")
    result_text.visible = False
    result_text.update()

    try:
        _log_message(log, f"[数据同步] 开始同步 (模式={mode}, 类型={selected_types}, 预览={dry_run}, 年={year}, 月={month}, 日期={date_start}~{date_end})")

        def _do_sync():
            return sync_to_minebase(
                input_dir=path,
                mode=mode,
                data_types=selected_types,
                dry_run=dry_run,
                year=year,
                month=month,
                date_start=date_start,
                date_end=date_end,
                apply_header_mapping=apply_header,
                use_equipment_ledger=use_equipment_ledger,
                use_oil_ledger=use_oil_ledger,
                skip_hidden_rows=skip_hidden_rows,
                skip_hidden_cols=skip_hidden_cols,
            )

        results = await asyncio.to_thread(_do_sync)

        if not results:
            _log_message(log, "[数据同步] 未找到可同步的文件", level=logging.WARNING)
            _show_snackbar(page, "未找到可同步的文件", is_error=True)
            result_text.value = "未找到可同步的文件"
            result_text.color = "#F59E0B"
            result_text.visible = True
            result_text.update()
            return

        total = {"success": 0, "skipped": 0, "failed": 0}
        for r in results.values():
            for k in total:
                total[k] += r.get(k, 0)

        summary = f"成功: {total['success']}  跳过: {total['skipped']}  失败: {total['failed']}"
        _log_message(log, f"[数据同步] 同步完成 — {summary}")

        if total["failed"] > 0:
            result_text.value = summary
            result_text.color = "#EF4444"
            _show_snackbar(page, f"同步完成（有 {total['failed']} 行失败）", is_error=True)
        elif dry_run:
            result_text.value = f"[预览] {summary}"
            result_text.color = "#0891B2"
            _show_snackbar(page, "预览完成")
        else:
            result_text.value = summary
            result_text.color = "#10B981"
            _show_snackbar(page, "同步完成")

        result_text.visible = True
        result_text.update()

    except Exception as ex:
        _log_message(log, f"[数据同步] 同步失败: {ex}", level=logging.ERROR)
        _show_snackbar(page, "同步失败", is_error=True)
        result_text.value = f"失败: {ex}"
        result_text.color = "#EF4444"
        result_text.visible = True
        result_text.update()
    finally:
        set_btn_state(btn, True, "同步到 MineBase")


def wire_sync_button(sync_refs: dict, page: ft.Page, log):
    """绑定 MineBase 同步按钮"""
    async def handle_sync_click(e: ft.ControlEvent):
        await on_sync_process(page, sync_refs, log)
    sync_refs["btn"].on_click = handle_sync_click


async def on_test_db_connection(page: ft.Page, config_refs: dict, log):
    """测试数据库连接

    如果密码字段显示掩码（********），自动从已保存的配置中加载真实密码，
    方便用户无需重新输入密码即可测试连接。加载的密码不会回填到界面。
    """
    from func.config_loader import get_minebase_db_config

    btn = config_refs["mb_test_btn"]
    result = config_refs["mb_test_result"]

    host = (config_refs["mb_db_host"].value or "").strip()
    port_str = (config_refs["mb_db_port"].value or "").strip()
    database = (config_refs["mb_db_name"].value or "").strip()
    user = (config_refs["mb_db_user"].value or "").strip()
    password = config_refs["mb_db_pass"].value or ""

    # 如果密码字段是掩码且有已保存的密码，从配置中加载真实密码
    _MASKED = "********"
    if password == _MASKED:
        saved_cfg = get_minebase_db_config()
        password = saved_cfg.get("password", "")
        if not password:
            _show_snackbar(page, "未找到已保存的密码，请先输入密码并保存", is_error=True)
            return

    if not port_str.isdigit():
        _show_snackbar(page, "端口必须是数字", is_error=True)
        return
    port = int(port_str)

    set_btn_state(btn, False, "测试中...")
    result.visible = False
    result.update()

    try:
        success, msg = await asyncio.to_thread(
            test_db_connection, host, port, database, user, password,
        )
        result.value = msg
        result.color = "#10B981" if success else "#EF4444"
        result.visible = True
        result.update()

        _log_message(log, f"数据库连接测试: {msg}", level=logging.INFO if success else logging.WARNING)
        _show_snackbar(page, "连接成功" if success else "连接失败", is_error=not success)
    except Exception as exc:
        result.value = str(exc)[:200]
        result.color = "#EF4444"
        result.visible = True
        result.update()
        _show_snackbar(page, "测试异常", is_error=True)
    finally:
        set_btn_state(btn, True, "测试连接")


def wire_test_db_button(config_refs: dict, page: ft.Page, log):
    """绑定数据库测试连接按钮"""
    async def handle_test_click(e: ft.ControlEvent):
        await on_test_db_connection(page, config_refs, log)
    config_refs["mb_test_btn"].on_click = handle_test_click


async def on_test_api_connection(page: ft.Page, config_refs: dict, log):
    """测试 API 连接

    如果密码字段显示掩码（********），自动从已保存的配置中加载真实密码，
    方便用户无需重新输入密码即可测试连接。加载的密码不会回填到界面。
    """
    from func.config_loader import get_minebase_api_config

    btn = config_refs["mb_api_test_btn"]
    result = config_refs["mb_api_test_result"]

    url = (config_refs["mb_api_url"].value or "").strip()
    username = (config_refs["mb_api_user"].value or "").strip()
    password = config_refs["mb_api_pass"].value or ""

    # 如果密码字段是掩码且有已保存的密码，从配置中加载真实密码
    _MASKED = "********"
    if password == _MASKED:
        saved_cfg = get_minebase_api_config()
        password = saved_cfg.get("password", "")
        if not password:
            _show_snackbar(page, "未找到已保存的密码，请先输入密码并保存", is_error=True)
            return

    if not url:
        _show_snackbar(page, "请填写 API 地址", is_error=True)
        return

    set_btn_state(btn, False, "测试中...")
    result.visible = False
    result.update()

    try:
        success, msg = await asyncio.to_thread(
            test_api_connection, url, username, password,
        )
        result.value = msg
        result.color = "#10B981" if success else "#EF4444"
        result.visible = True
        result.update()

        _log_message(log, f"API 连接测试: {msg}", level=logging.INFO if success else logging.WARNING)
        _show_snackbar(page, "连接成功" if success else "连接失败", is_error=not success)
    except Exception as exc:
        result.value = str(exc)[:200]
        result.color = "#EF4444"
        result.visible = True
        result.update()
        _show_snackbar(page, "测试异常", is_error=True)
    finally:
        set_btn_state(btn, True, "测试连接")


def wire_test_api_button(config_refs: dict, page: ft.Page, log):
    """绑定 API 测试连接按钮"""
    async def handle_test_click(e: ft.ControlEvent):
        await on_test_api_connection(page, config_refs, log)
    config_refs["mb_api_test_btn"].on_click = handle_test_click


def init(config_section_refs: dict):
    """初始化：加载配置"""
    if "load_config" in config_section_refs:
        config_section_refs["load_config"]()
