"""
GUI 业务逻辑层
处理各模块的后台任务、线程管理
"""
import asyncio
import logging
import sys
import threading
import flet as ft
import os
import pandas as pd
from func import config_loader
from func.excel_batch import scan_files, process_files, MODULE_LABELS
from func.sync_to_minebase import sync as sync_to_minebase
from func.sync_to_minebase import test_db_connection
from func.sync_to_minebase import test_api_connection


from gui.utils import _log_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
# 全局关闭标记：页面关闭时置位，后台任务定期检查以提前终止
_shutdown_event = threading.Event()

# 活跃任务的 cancel_event 集合，页面关闭时统一触发
_active_cancel_events: list[threading.Event] = []


def register_cancel_event(event: threading.Event) -> None:
    """将一个 cancel_event 注册到活跃列表中，关闭时自动触发。"""
    _active_cancel_events.append(event)


def unregister_cancel_event(event: threading.Event) -> None:
    """从活跃列表中移除已完成的 cancel_event。"""
    try:
        _active_cancel_events.remove(event)
    except ValueError:
        pass


def shutdown_tasks() -> None:
    """设置全局关闭标记，并触发所有活跃任务的 cancel_event。"""
    _shutdown_event.set()
    for ev in _active_cancel_events[:]:
        ev.set()


def is_shutdown() -> bool:
    """检查全局关闭标记是否已设置。"""
    return _shutdown_event.is_set()
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
# 任务执行
# ---------------------------------------------------------------------------
def _dispatch_module(module_type: str, path: str, cancel_event: threading.Event | None = None, **kwargs) -> dict:
    """Dispatch to the appropriate processor via orchestration.process_single().

    Returns:
        dict with "output_file" key; production adds "summary".
    """
    if _shutdown_event.is_set() or (cancel_event and cancel_event.is_set()):
        return {"output_file": None}

    from func.orchestration import process_single

    # 将 equipment_ledger/oil_ledger 实例转为 use_*_ledger 布尔值
    eq_ledger = kwargs.pop("equipment_ledger", None)
    oil_ledger = kwargs.pop("oil_ledger", None)
    use_eq = eq_ledger is not None
    use_oil = oil_ledger is not None

    return process_single(
        module_type, path,
        cancel_event=cancel_event,
        use_equipment_ledger=use_eq,
        use_oil_ledger=use_oil,
        equipment_ledger=eq_ledger,
        oil_ledger=oil_ledger,
        **kwargs,
    )


def _execute_task(module_type: str, path: str, cancel_event: threading.Event | None = None, **kwargs) -> tuple[str | None, dict | None]:
    """在后台线程中执行处理任务，返回 (错误信息或None, 额外数据或None)。

    Args:
        cancel_event: 可选的取消事件，页面关闭或用户取消时置位。
    """
    if _shutdown_event.is_set():
        logger.info("页面已关闭，跳过任务: module=%s", module_type)
        return "页面已关闭", None

    extra = None
    try:
        result = _dispatch_module(module_type, path, cancel_event=cancel_event, **kwargs)
        if module_type == "production" and isinstance(result, dict):
            extra = result.get("summary")
    except Exception:
        logger.exception("Task execution failed: module=%s path=%s", module_type, path)
        return str(sys.exc_info()[1]).strip() or sys.exc_info()[0].__name__, None

    return None, extra


async def run_task(page: ft.Page, module_type: str, path: str, log, cancel_event: threading.Event | None = None, **kwargs) -> dict | None:
    """异步执行处理任务，返回额外数据（如 summary）或 None。按钮状态由调用方自行恢复。

    Args:
        cancel_event: 可选的取消事件，页面关闭或用户取消时自动置位。
    """
    label = _MODULE_LABELS.get(module_type, module_type)
    _log_message(log, f"[{label}] 开始处理...")
    error_message, extra = await asyncio.to_thread(_execute_task, module_type, path, cancel_event, **kwargs)
    if error_message:
        if _shutdown_event.is_set():
            _log_message(log, f"[{label}] 任务因页面关闭而中止", level=logging.WARNING)
        else:
            _log_message(log, f"[{label}] 处理失败: {error_message}", level=logging.ERROR)
            _show_snackbar(page, f"{label}处理失败", is_error=True)
    else:
        _log_message(log, f"[{label}] 处理成功")
        _show_snackbar(page, f"{label}处理完成")
    return extra


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
) -> dict | None:
    """通用处理回调模板：禁用按钮 → 执行任务 → 恢复按钮 (M4)"""
    if _shutdown_event.is_set():
        return None
    cancel_event = threading.Event()
    register_cancel_event(cancel_event)
    set_btn_state(btn, False, "处理中...")
    try:
        return await run_task(page, module_type, path, log, cancel_event=cancel_event, **kwargs)
    finally:
        unregister_cancel_event(cancel_event)
        if not _shutdown_event.is_set():
            set_btn_state(btn, True, label)


# ---------------------------------------------------------------------------
# 各模块按钮回调
# ---------------------------------------------------------------------------
async def on_fuel_process(page: ft.Page, fuel_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None, filter_zero_engine_hours=True, filter_zero_work_hours=False) -> None:
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
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         anomaly_config=anomaly_config, filter_zero_engine_hours=filter_zero_engine_hours,
                         filter_zero_work_hours=filter_zero_work_hours)


def _update_prod_summary(container: ft.Column, summary: dict | None) -> None:
    """更新生产模块的汇总显示区域。"""
    container.controls.clear()
    if not summary:
        container.visible = False
        if hasattr(container, 'update'):
            container.update()
        return

    total = summary.get("total_files", 0)
    success = summary.get("success_files", 0)
    failed = summary.get("failed_files", 0)
    warnings = summary.get("warnings", [])

    # 文件统计行
    stats_text = f"共 {total} 个文件，成功 {success}，失败 {failed}"
    stats_color = ft.Colors.RED_700 if failed > 0 else ft.Colors.GREEN_700
    container.controls.append(
        ft.Text(stats_text, size=12, color=stats_color, weight=ft.FontWeight.W_500)
    )

    # 警告列表
    for w in warnings:
        container.controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=ft.Colors.AMBER_600),
                    ft.Text(w, size=11, color=ft.Colors.AMBER_800, expand=True),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        )

    container.visible = True
    if hasattr(container, 'update'):
        container.update()


async def on_prod_process(page: ft.Page, prod_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None, filter_zero_hours_meter=True, filter_zero_km_meter=True, filter_zero_run_hours=False, filter_zero_run_km=False) -> None:
    """生产处理按钮回调"""
    btn = prod_refs["btn"]
    path = prod_refs["path"].value
    if not path:
        _log_message(log, "请先选择 Excel 文件或文件夹", level=logging.WARNING)
        return

    auto_detect_ref = prod_refs.get("auto_detect")
    if auto_detect_ref and auto_detect_ref.value:
        raw_start = -1
    else:
        raw_start_text = (prod_refs["raw_start"].value or "6").strip()
        try:
            raw_start = int(raw_start_text)
            if raw_start < 1:
                raise ValueError
        except ValueError:
            _log_message(log, "请输入有效的表头起始行（正整数）", level=logging.WARNING)
            return

    summary = await _safe_run_task(page, btn, "处理", path, log, "production",
                         raw_start=raw_start, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         anomaly_config=anomaly_config,
                         filter_zero_hours_meter=filter_zero_hours_meter,
                         filter_zero_km_meter=filter_zero_km_meter,
                         filter_zero_run_hours=filter_zero_run_hours,
                         filter_zero_run_km=filter_zero_run_km)

    # 更新汇总显示
    summary_container = prod_refs.get("summary_container")
    if summary_container is not None:
        _update_prod_summary(summary_container, summary)


async def on_elec_process(page: ft.Page, elec_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None) -> None:
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
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         anomaly_config=anomaly_config)


async def on_work_process(page: ft.Page, work_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None) -> None:
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
        header_mapping = build_worktime_header_mapping(
            mode=header_mode.value if header_mode else None,
        )
    await _safe_run_task(page, btn, "处理", path, log, "worktime",
                         year=year, month=month,
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         header_mapping=header_mapping,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         anomaly_config=anomaly_config)


async def on_merge_process(page: ft.Page, merge_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None) -> None:
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
    tolerant_header = bool(merge_refs.get("tolerant_header") and merge_refs["tolerant_header"].value)
    await _safe_run_task(page, btn, "合并", path, log, "merge",
                         keyword=keyword, strip_time=strip_time, sort_configs=sort_configs,
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         tolerant_header=tolerant_header)


async def on_maint_process(page: ft.Page, maint_refs: dict, log, equipment_ledger=None, oil_ledger=None, skip_hidden_rows=False, skip_hidden_cols=False, anomaly_config=None) -> None:
    """维修记录处理按钮回调"""
    btn = maint_refs["btn"]
    path = maint_refs["path"].value
    if not path:
        _log_message(log, "请先选择出勤统计表文件或文件夹", level=logging.WARNING)
        return
    split_by_year = bool(maint_refs.get("split_year") and maint_refs["split_year"].value)
    details_only = bool(maint_refs.get("details_only") and maint_refs["details_only"].value)
    use_ml_fallback = bool(
        maint_refs.get("use_ml") is None or maint_refs["use_ml"].value
    )
    await _safe_run_task(page, btn, "处理", path, log, "maint",
                         equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                         skip_hidden_rows=skip_hidden_rows, skip_hidden_cols=skip_hidden_cols,
                         split_by_year=split_by_year, details_only=details_only,
                         use_ml_fallback=use_ml_fallback,
                         anomaly_config=anomaly_config)


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


async def on_batch_process(page: ft.Page, batch_refs: dict, log, equipment_ledger=None, oil_ledger=None, anomaly_config=None) -> None:
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
    # 注册到全局关闭机制：页面关闭时自动触发取消
    if cancel_event is not None:
        register_cancel_event(cancel_event)
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
            worktime_header_mapping = build_worktime_header_mapping(
                mode=header_mode.value if header_mode else None,
            )

        # ── 第三阶段：执行处理 ──
        params = collect_processing_params(batch_refs)

        set_btn_state(btn, False, "处理中...")
        done_flag = asyncio.Event()
        progress_poller = asyncio.create_task(
            _poll_batch_progress_queue(progress_queue, progress_bar, progress_text, done_flag)
        )
        try:
            thread_result = {}
            def _batch_target():
                try:
                    results, summary = process_files(
                        path, matched, year, month, raw_start, merge_output,
                        equipment_ledger, oil_ledger, filter_date,
                        worktime_header_mapping,
                        table_merge_config,
                        progress_cb=progress_queue.put_nowait,
                        cancel_event=cancel_event,
                        **params,
                    )
                    thread_result["value"] = results
                    thread_result["summary"] = summary
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
                summary = thread_result.get("summary", {})
                warnings = summary.get("warnings", [])
                success_mods = summary.get("success_modules", [])
                failed_mods = summary.get("failed_modules", [])
                msg = f"批量处理完成 — 成功: {', '.join(success_mods) or '无'}"
                if failed_mods:
                    msg += f"; 失败: {', '.join(failed_mods)}"
                _log_message(log, msg)
                for w in warnings:
                    _log_message(log, w, level=logging.WARNING)
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
        if cancel_event is not None:
            unregister_cancel_event(cancel_event)
        _hide_batch_progress(progress_row, progress_bar, progress_text, cancel_btn)
        if not _shutdown_event.is_set():
            set_btn_state(btn, True, "批量处理")


# ---------------------------------------------------------------------------
# 初始化 & 绑定
# ---------------------------------------------------------------------------
def _get_toggle_value(refs: dict, key: str, default=False):
    """从 refs 中安全读取 toggle/checkbox 值。"""
    ref = refs.get(key)
    return ref.value if ref else default


def collect_processing_params(refs: dict) -> dict:
    """从 GUI refs 中提取所有模块共用的处理参数。

    消除 _make_module_handler 和 on_batch_process 中重复的参数提取代码。
    """
    return {
        "skip_hidden_rows": _get_toggle_value(refs, "_skip_hidden_rows_toggle"),
        "skip_hidden_cols": _get_toggle_value(refs, "_skip_hidden_cols_toggle"),
        "anomaly_config": _build_anomaly_config(refs),
        "filter_zero_engine_hours": _get_toggle_value(refs, "_filter_zero_hours_toggle"),
        "filter_zero_work_hours": _get_toggle_value(refs, "_filter_zero_work_hours_toggle"),
        "filter_zero_hours_meter": _get_toggle_value(refs, "_filter_zero_hours_meter_toggle"),
        "filter_zero_km_meter": _get_toggle_value(refs, "_filter_zero_km_meter_toggle"),
        "filter_zero_run_hours": _get_toggle_value(refs, "_filter_zero_run_hours_toggle"),
        "filter_zero_run_km": _get_toggle_value(refs, "_filter_zero_run_km_toggle"),
    }


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

        # 从公共 refs 和模块 refs 中提取处理参数
        params = collect_processing_params(module_refs)
        module_refs_inner = module_refs.get(module_key, {})
        module_params = collect_processing_params(module_refs_inner)

        # 模块级 refs 覆盖公共 refs
        for key in module_params:
            if module_params[key]:
                params[key] = module_params[key]

        await callback(page, module_refs[module_key], log,
                       equipment_ledger=eq, oil_ledger=oil,
                       **params)

    return handler


def _build_anomaly_config(module_refs: dict):
    """从 module_refs 构建 AnomalyConfig 实例（加载用户配置的阈值和处理规则）。"""
    from func.anomaly.rules import AnomalyConfig

    enabled_ref = module_refs.get("_anomaly_enabled")
    if not enabled_ref or not enabled_ref.value:
        return AnomalyConfig(enabled=False)

    try:
        from .components.common import build_anomaly_config_from_refs
    except ImportError:
        from gui.components.common import build_anomaly_config_from_refs
    return build_anomaly_config_from_refs(module_refs)


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
            anomaly_config = _build_anomaly_config(module_refs["batch"])
            await on_batch_process(page, module_refs["batch"], log, equipment_ledger=eq, oil_ledger=oil, anomaly_config=anomaly_config)
        module_refs["batch"]["btn"].on_click = handle_batch_click


async def on_sync_process(page: ft.Page, sync_refs: dict, log, anomaly_config=None,
                          filter_zero_engine_hours=True, filter_zero_work_hours=False,
                          filter_zero_hours_meter=True, filter_zero_km_meter=True,
                          filter_zero_run_hours=False, filter_zero_run_km=False) -> None:
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
    header_mode_val = sync_refs.get("header_mode")
    header_mode = header_mode_val.value if header_mode_val else None
    eq_ledger_val = sync_refs.get("use_equipment_ledger")
    oil_ledger_val = sync_refs.get("use_oil_ledger")
    use_equipment_ledger = eq_ledger_val.value if eq_ledger_val else False
    use_oil_ledger = oil_ledger_val.value if oil_ledger_val else True

    # 跳过隐藏行/列
    skip_hidden_rows_val = sync_refs.get("skip_hidden_rows")
    skip_hidden_cols_val = sync_refs.get("skip_hidden_cols")
    skip_hidden_rows = skip_hidden_rows_val.value if skip_hidden_rows_val else False
    skip_hidden_cols = skip_hidden_cols_val.value if skip_hidden_cols_val else False

    # 冲突策略
    conflict_policy_val = sync_refs.get("conflict_policy")
    conflict_policy = conflict_policy_val.value if conflict_policy_val else "SKIP"

    set_btn_state(btn, False, "同步中...")
    result_text.visible = False
    result_text.update()

    try:
        if _shutdown_event.is_set():
            return

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
                header_mode=header_mode,
                use_equipment_ledger=use_equipment_ledger,
                use_oil_ledger=use_oil_ledger,
                skip_hidden_rows=skip_hidden_rows,
                skip_hidden_cols=skip_hidden_cols,
                anomaly_config=anomaly_config,
                filter_zero_engine_hours=filter_zero_engine_hours,
                filter_zero_work_hours=filter_zero_work_hours,
                filter_zero_hours_meter=filter_zero_hours_meter,
                filter_zero_km_meter=filter_zero_km_meter,
                filter_zero_run_hours=filter_zero_run_hours,
                filter_zero_run_km=filter_zero_run_km,
                conflict_policy=conflict_policy,
            )

        results = await asyncio.to_thread(_do_sync)

        if not results:
            _log_message(log, "[数据同步] 未找到可同步的文件", level=logging.WARNING)
            _show_snackbar(page, "未找到可同步的文件", is_error=True)
            result_text.value = "未找到可同步的文件"
            result_text.color = "#F59E0B"
            result_text.visible = True
            result_text.update()
            # 无结果时隐藏异常表格
            wc = sync_refs.get("warnings_container")
            if wc:
                wc.visible = False
                wc.update()
            return

        # 提取试运行预览文件路径
        dry_run_file = results.pop("_dry_run_file", None) if isinstance(results, dict) else None

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
            preview_msg = f"[预览] {summary}"
            if dry_run_file:
                preview_msg += f"\n预览文件: {dry_run_file}"
            result_text.value = preview_msg
            result_text.color = "#0891B2"
            _show_snackbar(page, "预览完成")
            if dry_run_file:
                _log_message(log, f"[数据同步] 预览文件已保存至: {dry_run_file}")
        else:
            result_text.value = summary
            result_text.color = "#10B981"
            _show_snackbar(page, "同步完成")

        result_text.visible = True
        result_text.update()

        # 收集并展示异常行
        from gui.components.sync_minebase import DATA_TYPES as _DT_NAMES

        _dt_label_map = dict(_DT_NAMES)
        all_warnings: list[tuple[str, dict]] = []
        for dt, r in results.items():
            for w in r.get("warnings", []):
                all_warnings.append((dt, w))

        warnings_container = sync_refs.get("warnings_container")
        warnings_list = sync_refs.get("warnings_list")
        warnings_count_text = sync_refs.get("warnings_count_text")

        if warnings_container and warnings_list:
            if all_warnings:
                warnings_list.controls.clear()
                for dt_key, w in all_warnings:
                    dt_label = _dt_label_map.get(dt_key, dt_key)
                    val = w.get("value")
                    val_str = str(val) if val is not None and str(val).strip() != "" else "（空）"
                    warnings_list.controls.append(
                        ft.Row(
                            [
                                ft.Text(dt_label, size=11, color="#64748B", width=70),
                                ft.Text(f"行{w.get('row', '?')}", size=11, color="#64748B", width=50),
                                ft.Text(w.get("field", ""), size=11, width=100),
                                ft.Text(val_str, size=11, color="#EF4444", width=80),
                                ft.Text(w.get("message", ""), size=11, color="#64748B", expand=True),
                            ],
                            spacing=8,
                        ),
                    )
                if warnings_count_text:
                    warnings_count_text.value = f"共 {len(all_warnings)} 条"

                export_btn = sync_refs.get("export_warnings_btn")
                save_picker = sync_refs.get("save_warnings_picker")
                if export_btn:
                    async def _on_export_click(e):
                        from datetime import datetime
                        from func.sync.export import export_warnings_to_excel
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        target_path = None
                        if save_picker:
                            res = await save_picker.save_file(
                                dialog_title="选择导出异常行保存位置",
                                file_name=f"异常行明细_{ts}.xlsx",
                                allowed_extensions=["xlsx"],
                            )
                            if not res:
                                return
                            target_path = res
                        out_path = export_warnings_to_excel(all_warnings, output_path=target_path, input_dir=path)
                        _log_message(log, f"[数据同步] 异常行已导出至: {out_path}")
                        _show_snackbar(page, f"异常行已导出至: {out_path}")
                    export_btn.on_click = _on_export_click

                warnings_container.visible = True
                _log_message(log, f"[数据同步] 发现 {len(all_warnings)} 条异常记录", level=logging.WARNING)
            else:
                warnings_container.visible = False
            warnings_container.update()

    except Exception as ex:
        _log_message(log, f"[数据同步] 同步失败: {ex}", level=logging.ERROR)
        _show_snackbar(page, "同步失败", is_error=True)
        result_text.value = f"失败: {ex}"
        result_text.color = "#EF4444"
        result_text.visible = True
        result_text.update()
        wc = sync_refs.get("warnings_container")
        if wc:
            wc.visible = False
            wc.update()
    finally:
        if not _shutdown_event.is_set():
            set_btn_state(btn, True, "同步到 MineBase")


def wire_sync_button(sync_refs: dict, page: ft.Page, log, module_refs: dict | None = None):
    """绑定 MineBase 同步按钮"""
    async def handle_sync_click(e: ft.ControlEvent):
        params = collect_processing_params(sync_refs)
        await on_sync_process(page, sync_refs, log, **params)
    sync_refs["btn"].on_click = handle_sync_click


async def _run_connection_test(
    btn, result, password: str,
    saved_config_loader, validate_fn, test_fn,
    page: ft.Page, log, label: str,
):
    """连接测试的通用生命周期管理。

    处理掩码密码自动加载、输入校验、按钮状态、结果展示和异常处理。
    调用方只需提供：校验函数、测试函数、refs 和标签。
    """
    from func.secret_store import MINEBASE_PASSWORD_MASK as _MASKED

    # 掩码密码自动加载
    if password == _MASKED:
        saved_cfg = saved_config_loader()
        password = saved_cfg.get("password", "")
        if not password:
            _show_snackbar(page, "未找到已保存的密码，请先输入密码并保存", is_error=True)
            return

    # 输入校验
    error = validate_fn(password)
    if error:
        _show_snackbar(page, error, is_error=True)
        return

    set_btn_state(btn, False, "测试中...")
    result.visible = False
    result.update()

    try:
        success, msg = await asyncio.to_thread(test_fn, password)
        result.value = msg
        result.color = "#10B981" if success else "#EF4444"
        result.visible = True
        result.update()

        _log_message(log, f"{label}连接测试: {msg}", level=logging.INFO if success else logging.WARNING)
        _show_snackbar(page, "连接成功" if success else "连接失败", is_error=not success)
    except Exception as exc:
        result.value = str(exc)[:200]
        result.color = "#EF4444"
        result.visible = True
        result.update()
        _show_snackbar(page, "测试异常", is_error=True)
    finally:
        if not _shutdown_event.is_set():
            set_btn_state(btn, True, "测试连接")


async def on_test_db_connection(page: ft.Page, config_refs: dict, log):
    """测试数据库连接

    如果密码字段显示掩码（********），自动从已保存的配置中加载真实密码，
    方便用户无需重新输入密码即可测试连接。加载的密码不会回填到界面。
    """
    from func.config_loader import get_minebase_db_config

    host = (config_refs["mb_db_host"].value or "").strip()
    port_str = (config_refs["mb_db_port"].value or "").strip()
    database = (config_refs["mb_db_name"].value or "").strip()
    user = (config_refs["mb_db_user"].value or "").strip()
    password = config_refs["mb_db_pass"].value or ""

    def _validate(pwd):
        if not port_str.isdigit():
            return "端口必须是数字"
        return None

    def _test(pwd):
        return test_db_connection(host, int(port_str), database, user, pwd)

    await _run_connection_test(
        config_refs["mb_test_btn"], config_refs["mb_test_result"],
        password, get_minebase_db_config, _validate, _test,
        page, log, "数据库",
    )


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

    url = (config_refs["mb_api_url"].value or "").strip()
    username = (config_refs["mb_api_user"].value or "").strip()
    password = config_refs["mb_api_pass"].value or ""

    def _validate(pwd):
        if not url:
            return "请填写 API 地址"
        return None

    def _test(pwd):
        return test_api_connection(url, username, pwd)

    await _run_connection_test(
        config_refs["mb_api_test_btn"], config_refs["mb_api_test_result"],
        password, get_minebase_api_config, _validate, _test,
        page, log, "API",
    )


def wire_test_api_button(config_refs: dict, page: ft.Page, log):
    """绑定 API 测试连接按钮"""
    async def handle_test_click(e: ft.ControlEvent):
        await on_test_api_connection(page, config_refs, log)
    config_refs["mb_api_test_btn"].on_click = handle_test_click


def init(config_section_refs: dict):
    """初始化：加载配置"""
    if "load_config" in config_section_refs:
        config_section_refs["load_config"]()
