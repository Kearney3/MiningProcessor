"""
GUI 业务逻辑层
处理各模块的后台任务、线程管理
"""
import asyncio
import logging
import flet as ft
import os
import pandas as pd
from func import config_loader
from func.excel_fuel import process_diesel_data
from func.excel_production_enhanced import MiningDataProcessor as ProdProcessor
from func.excel_electrical import parse_excel_data
from func.excel_worktime import process_excel_data
from func.excel_merger import merge_excel_files
from func.excel_batch import scan_files, process_files, MODULE_LABELS
from func.sync_to_minebase import sync as sync_to_minebase


from gui.components.common import _log_message


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
# 保存按钮原始样式，以便恢复
_btn_original_styles: dict[int, ft.ButtonStyle] = {}

_LOADING_STYLE = ft.ButtonStyle(bgcolor="#CBD5E1", color="#64748B")

# 模块类型中文标签
_MODULE_LABELS = {
    "fuel": "燃油数据",
    "electrical": "电力数据",
    "production": "生产数据",
    "worktime": "工时数据",
    "merge": "文件合并",
    "batch": "批量处理",
}


_active_snackbar: ft.SnackBar | None = None


def _show_snackbar(page: ft.Page, message: str, is_error: bool = False):
    """显示 snackbar 通知（线程安全，单一活跃实例）"""
    global _active_snackbar
    # 移除上一个未消失的 snackbar
    if _active_snackbar is not None:
        try:
            page.overlay.remove(_active_snackbar)
        except ValueError:
            pass
        _active_snackbar = None

    snackbar = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
        duration=3000,
    )
    _active_snackbar = snackbar
    page.overlay.append(snackbar)
    snackbar.open = True
    page.update()

    # 使用 asyncio 在 Flet 事件循环中安全清理
    async def _cleanup():
        nonlocal snackbar
        await asyncio.sleep(3.5)
        if _active_snackbar is snackbar:
            try:
                page.overlay.remove(snackbar)
                page.update()
            except (ValueError, RuntimeError):
                pass
            _active_snackbar = None

    try:
        page.run_task(_cleanup)
    except (AttributeError, RuntimeError):
        # 降级：run_task 不可用时用 Timer
        import threading
        def _fallback_cleanup():
            try:
                page.overlay.remove(snackbar)
                page.update()
            except (ValueError, RuntimeError):
                pass
        threading.Timer(3.5, _fallback_cleanup).start()


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
# 台账匹配后处理
# ---------------------------------------------------------------------------
def _find_col(columns, candidates):
    """在列名列表中查找第一个匹配的候选列名（支持 strip 匹配）"""
    # 先尝试精确匹配
    for c in candidates:
        if c in columns:
            return c
    # 再尝试 strip 后匹配
    stripped_map = {col.strip(): col for col in columns}
    for c in candidates:
        if c in stripped_map:
            return stripped_map[c]
    return None


def _apply_ledger_matching(output_file: str, equipment_ledger=None, oil_ledger=None, preloaded_sheets=None):
    """
    对已写入的 Excel 文件进行台账匹配后处理。
    读取每个 sheet，检测列名，追加匹配字段，重新写回。
    对于生产数据（同时包含矿卡名称和挖机名称），匹配列名会添加（矿卡）或（挖机）后缀。
    """
    if not equipment_ledger and not oil_ledger:
        return

    if preloaded_sheets:
        sheets_to_match = dict(preloaded_sheets)
    else:
        try:
            xl = pd.ExcelFile(output_file)
        except Exception as ex:
            logging.warning(f"无法读取输出文件进行台账匹配: {ex}")
            return
        sheets_to_match = {name: xl.parse(name) for name in xl.sheet_names}

    sheet_data = {}
    matched_any = False

    for sheet_name, df in sheets_to_match.items():
        cols = set(df.columns)

        # 设备匹配
        if equipment_ledger:
            # 检测是否同时存在矿卡名称和挖机名称（生产数据场景）
            has_truck_col = "矿卡名称" in cols
            has_excavator_col = "挖机名称" in cols
            
            # 如果同时存在两个列，则分别匹配并添加后缀
            if has_truck_col and has_excavator_col:
                # 匹配矿卡名称
                name_col = "矿卡名称"
                id_col = "设备编号" if "设备编号" in cols else None
                std_names, std_ids, std_companies = [], [], []
                for _, row in df.iterrows():
                    name_val = row.get(name_col)
                    id_val = row.get(id_col) if id_col else None
                    name_str = str(name_val) if not pd.isna(name_val) else None
                    id_str = str(id_val) if id_val is not None and not pd.isna(id_val) else None
                    result = equipment_ledger.match_device(name=name_str, device_id=id_str)
                    if result:
                        std_names.append(result.get("标准设备名称", ""))
                        std_ids.append(result.get("标准设备编号", ""))
                        std_companies.append(result.get("标准公司名称", ""))
                    else:
                        std_names.append("")
                        std_ids.append("")
                        std_companies.append("")
                df["标准设备名称（矿卡）"] = std_names
                df["标准设备编号（矿卡）"] = std_ids
                df["标准公司名称（矿卡）"] = std_companies
                
                # 匹配挖机名称
                excavator_col = "挖机名称"
                std_names_ex, std_ids_ex, std_companies_ex = [], [], []
                for _, row in df.iterrows():
                    name_val = row.get(excavator_col)
                    name_str = str(name_val) if not pd.isna(name_val) else None
                    result = equipment_ledger.match_device(name=name_str, device_id=None)
                    if result:
                        std_names_ex.append(result.get("标准设备名称", ""))
                        std_ids_ex.append(result.get("标准设备编号", ""))
                        std_companies_ex.append(result.get("标准公司名称", ""))
                    else:
                        std_names_ex.append("")
                        std_ids_ex.append("")
                        std_companies_ex.append("")
                df["标准设备名称（挖机）"] = std_names_ex
                df["标准设备编号（挖机）"] = std_ids_ex
                df["标准公司名称（挖机）"] = std_companies_ex
                matched_any = True
            else:
                # 原有逻辑：单列匹配（非生产数据场景）
                name_col = _find_col(cols, ["设备名称", "矿卡名称"])
                id_col = "设备编号" if "设备编号" in cols else None
                if name_col:
                    std_names, std_ids, std_companies = [], [], []
                    for _, row in df.iterrows():
                        name_val = row.get(name_col)
                        id_val = row.get(id_col) if id_col else None
                        name_str = str(name_val) if not pd.isna(name_val) else None
                        id_str = str(id_val) if id_val is not None and not pd.isna(id_val) else None
                        result = equipment_ledger.match_device(name=name_str, device_id=id_str)
                        if result:
                            std_names.append(result.get("标准设备名称", ""))
                            std_ids.append(result.get("标准设备编号", ""))
                            std_companies.append(result.get("标准公司名称", ""))
                        else:
                            std_names.append("")
                            std_ids.append("")
                            std_companies.append("")
                    df["标准设备名称"] = std_names
                    df["标准设备编号"] = std_ids
                    df["标准公司名称"] = std_companies
                    matched_any = True

        # 油品匹配
        if oil_ledger:
            oil_col = _find_col(cols, ["油品种类", "油品名称"])
            if oil_col:
                std_oils = []
                for _, row in df.iterrows():
                    oil_val = row[oil_col]
                    if pd.isna(oil_val):
                        std_oils.append("")
                    else:
                        result = oil_ledger.match(str(oil_val))
                        std_oils.append(result["标准名称"] if result else "")
                df["标准油品名称"] = std_oils
                matched_any = True

        sheet_data[sheet_name] = df

    if not matched_any:
        return

    # 重写 Excel
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sheet_name, df in sheet_data.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    logging.info(f"台账匹配完成，已更新: {output_file}")


def _get_output_file(module_type: str, path: str, **kwargs) -> str | None:
    """根据模块类型和输入路径，推断输出文件路径"""
    if module_type == "fuel":
        return os.path.join(os.path.dirname(path), "Fuel.xlsx")
    elif module_type == "production":
        base = path if os.path.isdir(path) else os.path.dirname(path)
        return os.path.join(base, "合并产量.xlsx")
    elif module_type == "electrical":
        return os.path.join(os.path.dirname(path), "电力消耗统计.xlsx")
    elif module_type == "worktime":
        year = kwargs.get("year", 2025)
        month = kwargs.get("month", 1)
        return os.path.join(os.path.dirname(path), f"{year}{month:02d}_工作效率表.xlsx")
    elif module_type == "merge":
        keyword = kwargs.get("keyword", "")
        return os.path.join(path, f"{keyword}_合并.xlsx")
    elif module_type == "batch":
        return None  # 台账匹配已在 batch_process 内部处理
    return None


# ---------------------------------------------------------------------------
# 任务执行
# ---------------------------------------------------------------------------
def _execute_task(module_type: str, path: str, **kwargs) -> str | None:
    """在后台线程中执行处理任务"""
    error_message = None
    equipment_ledger = kwargs.pop("equipment_ledger", None)
    oil_ledger = kwargs.pop("oil_ledger", None)

    try:
        worktime_sheets = None
        if module_type == "fuel":
            process_diesel_data(path, kwargs.get("year"))
        elif module_type == "production":
            raw_start = kwargs.get("raw_start", -1)
            device_load_map = config_loader.get_device_load_map()
            processor = ProdProcessor(raw_start=raw_start, device_load_map=device_load_map)
            logging.info(f"装载量参数：{device_load_map}")
            if os.path.isdir(path):
                output_file = os.path.join(path, "合并产量.xlsx")
                processor.process_folder(path, output_file)
            else:
                output_file = os.path.join(os.path.dirname(path) or ".", "合并产量.xlsx")
                processor.process_single_file(path, output_file)
        elif module_type == "electrical":
            parse_excel_data(path, kwargs.get("year"),
                             add_shift_column=kwargs.get("add_shift_column", False),
                             default_shift=kwargs.get("default_shift", "Day"))
        elif module_type == "worktime":
            year = kwargs.get("year", 2025)
            month = kwargs.get("month", 1)
            header_mapping = kwargs.get("header_mapping", None)
            file_dir = os.path.dirname(path) or "."
            output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
            worktime_sheets = process_excel_data(path, year, month, output_file,
                                                 return_sheets=True, header_mapping=header_mapping)
        elif module_type == "merge":
            keyword = kwargs.get("keyword", "")
            strip_time = kwargs.get("strip_time", False)
            sort_configs = kwargs.get("sort_configs", None)
            merge_excel_files(path, keyword, strip_time=strip_time, sort_configs=sort_configs)
        # batch 模块由 _execute_batch_task 单独处理

        # 台账匹配后处理
        if equipment_ledger or oil_ledger:
            output_file = _get_output_file(module_type, path, **kwargs)
            if output_file and os.path.exists(output_file):
                sheets_data = worktime_sheets if module_type == "worktime" else None
                _apply_ledger_matching(output_file, equipment_ledger, oil_ledger,
                                       preloaded_sheets=sheets_data)
    except Exception as ex:
        error_message = str(ex)

    return error_message


async def run_task(page: ft.Page, module_type: str, path: str, btn: ft.Button, log, **kwargs):
    """异步执行处理任务，按钮状态由调用方自行恢复"""
    del btn  # 保留现有调用签名，避免影响其他调用方

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
# 按钮点击处理
# ---------------------------------------------------------------------------
async def on_fuel_process(page: ft.Page, fuel_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """燃油处理按钮回调"""
    btn = fuel_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    try:
        path = fuel_refs["path"].value
        if not path:
            _log_message(log, "请先选择文件", level=logging.WARNING)
            set_btn_state(btn, True, "处理")
            return
        year = int(fuel_refs["year"].value)
        await run_task(page, "fuel", path, btn, log, year=year, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
        set_btn_state(btn, True, "处理")
    except Exception:
        set_btn_state(btn, True, "处理")
        raise


async def on_prod_process(page: ft.Page, prod_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """生产处理按钮回调"""
    btn = prod_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    try:
        path = prod_refs["path"].value
        if not path:
            _log_message(log, "请先选择 Excel 文件或文件夹", level=logging.WARNING)
            set_btn_state(btn, True, "处理")
            return

        raw_start_text = (prod_refs["raw_start"].value or "-1").strip()
        try:
            raw_start = int(raw_start_text)
            if raw_start != -1 and raw_start < 1:
                raise ValueError
        except ValueError:
            _log_message(log, "请输入有效的 raw_start（正整数或-1【自动检测行】）", level=logging.WARNING)
            set_btn_state(btn, True, "处理")
            return

        await run_task(page, "production", path, btn, log, raw_start=raw_start, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
        set_btn_state(btn, True, "处理")
    except Exception:
        set_btn_state(btn, True, "处理")
        raise


async def on_elec_process(page: ft.Page, elec_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """电力处理按钮回调"""
    btn = elec_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    try:
        path = elec_refs["path"].value
        if not path:
            _log_message(log, "请先选择文件", level=logging.WARNING)
            set_btn_state(btn, True, "处理")
            return

        year_text = elec_refs["year"].value
        try:
            year = int(year_text)
        except (TypeError, ValueError):
            _log_message(log, "请输入有效的年份", level=logging.WARNING)
            set_btn_state(btn, True, "处理")
            return

        add_shift = elec_refs.get("add_shift")
        default_shift_ref = elec_refs.get("default_shift")
        await run_task(page, "electrical", path, btn, log, year=year,
                       add_shift_column=add_shift.value if add_shift else False,
                       default_shift=default_shift_ref.value if default_shift_ref else "Day",
                       equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
        set_btn_state(btn, True, "处理")
    except Exception:
        set_btn_state(btn, True, "处理")
        raise


async def on_work_process(page: ft.Page, work_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """工时处理按钮回调"""
    btn = work_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    try:
        path = work_refs["path"].value
        if not path:
            _log_message(log, "请先选择文件", level=logging.WARNING)
            set_btn_state(btn, True, "处理")
            return
        year = int(work_refs["year"].value)
        month = int(work_refs["month"].value)
        # 表头映射：根据开关状态决定是否传入
        header_mapping = None
        header_toggle = work_refs.get("header_toggle")
        if header_toggle and header_toggle.value:
            mapping_config = config_loader.get_worktime_header_mapping()
            header_mode = work_refs.get("header_mode")
            header_fuzzy = work_refs.get("header_fuzzy")
            mapping_config["mode"] = header_mode.value if header_mode else "position"
            mapping_config["fuzzy"] = header_fuzzy.value if header_fuzzy else False
            header_mapping = mapping_config
        await run_task(page, "worktime", path, btn, log, year=year, month=month,
                       equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                       header_mapping=header_mapping)
        set_btn_state(btn, True, "处理")
    except Exception:
        set_btn_state(btn, True, "处理")
        raise


async def on_merge_process(page: ft.Page, merge_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """Excel 合并按钮回调"""
    btn = merge_refs["btn"]
    set_btn_state(btn, False, "合并中...")
    try:
        path = merge_refs["path"].value
        if not path:
            _log_message(log, "请先选择文件夹", level=logging.WARNING)
            set_btn_state(btn, True, "合并")
            return
        keyword = (merge_refs["keyword"].value or "").strip()
        if not keyword:
            _log_message(log, "请输入文件名关键字", level=logging.WARNING)
            set_btn_state(btn, True, "合并")
            return
        # 收集排序配置
        sort_configs = []
        for cfg in merge_refs.get("sort_configs_state", []):
            col = (cfg.get("column") or "").strip()
            if col:
                sort_configs.append({"column": col, "ascending": bool(cfg.get("ascending", True))})
        strip_time = bool(merge_refs["strip_time"].value)
        await run_task(page, "merge", path, btn, log, keyword=keyword, strip_time=strip_time, sort_configs=sort_configs, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
        set_btn_state(btn, True, "合并")
    except Exception:
        set_btn_state(btn, True, "合并")
        raise


def _show_batch_progress(progress_row, progress_bar, progress_text, cancel_btn):
    if progress_bar is not None:
        progress_bar.value = 0.0
        progress_bar.visible = True
        progress_bar.update()
    if progress_text is not None:
        progress_text.value = "0%"
        progress_text.visible = True
        progress_text.update()
    if cancel_btn is not None:
        cancel_btn.disabled = False
        cancel_btn.visible = True
        cancel_btn.update()
    if progress_row is not None:
        progress_row.visible = True
        progress_row.update()


def _hide_batch_progress(progress_row, progress_bar, progress_text, cancel_btn):
    if progress_bar is not None:
        progress_bar.visible = False
        progress_bar.update()
    if progress_text is not None:
        progress_text.visible = False
        progress_text.update()
    if cancel_btn is not None:
        cancel_btn.visible = False
        cancel_btn.update()
    if progress_row is not None:
        progress_row.visible = False
        progress_row.update()


def _handle_batch_cancel(cancel_event, cancel_btn):
    if cancel_event is not None:
        cancel_event.set()
    if cancel_btn is not None:
        cancel_btn.disabled = True
        cancel_btn.update()


async def _consume_batch_progress_queue(progress_queue, progress_bar, progress_text):
    last_percent = None
    while True:
        try:
            payload = progress_queue.get_nowait()
        except Exception:
            break
        last_percent = payload.get("percent", last_percent)
        if progress_bar is not None and last_percent is not None:
            progress_bar.value = float(last_percent)
            progress_bar.update()
        if progress_text is not None and last_percent is not None:
            progress_text.value = f"{int(last_percent * 100)}%"
            progress_text.update()
    if last_percent is not None:
        if progress_bar is not None:
            progress_bar.value = float(last_percent)
            progress_bar.update()
        if progress_text is not None:
            progress_text.value = f"{int(last_percent * 100)}%"
            progress_text.update()


async def on_batch_process(page: ft.Page, batch_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """批量处理按钮回调（带文件扫描 + 缺失确认弹窗）"""
    import queue
    import threading

    path = batch_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件夹", level=logging.WARNING)
        return

    btn = batch_refs["btn"]
    set_btn_state(btn, False, "扫描中...")

    year = int(batch_refs["year"].value)
    month = int(batch_refs["month"].value)
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
            mapping_config = config_loader.get_worktime_header_mapping()
            header_mode = batch_refs.get("header_mode")
            header_fuzzy = batch_refs.get("header_fuzzy")
            mapping_config["mode"] = header_mode.value if header_mode else "position"
            mapping_config["fuzzy"] = header_fuzzy.value if header_fuzzy else False
            worktime_header_mapping = mapping_config

        # ── 第三阶段：执行处理 ──
        set_btn_state(btn, False, "处理中...")
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
                    )
                except Exception as ex:
                    thread_result["error"] = ex

            await asyncio.to_thread(_batch_target)
            await _consume_batch_progress_queue(progress_queue, progress_bar, progress_text)
            if "error" in thread_result:
                raise thread_result["error"]
            if cancel_event is not None and cancel_event.is_set():
                _log_message(log, "用户取消了批量处理", level=logging.WARNING)
                _show_snackbar(page, "批量处理已取消")
            else:
                _log_message(log, "批量处理完成")
                _show_snackbar(page, "批量处理完成")
        except Exception as ex:
            _log_message(log, f"批量处理失败: {ex}", level=logging.ERROR)
            _show_snackbar(page, f"批量处理失败: {ex}", is_error=True)

    finally:
        # 确保所有路径（包括早期返回）都清理进度条和按钮状态
        _hide_batch_progress(progress_row, progress_bar, progress_text, cancel_btn)
        set_btn_state(btn, True, "批量处理")


# ---------------------------------------------------------------------------
# 初始化 & 绑定
# ---------------------------------------------------------------------------
def wire_processing_buttons(module_refs: dict, page: ft.Page, log, ledger_refs: dict = None, oil_ledger_refs: dict = None):
    """
    将模块 refs 中的按钮绑定到处理回调
    必须在模块区域创建完成后调用
    """
    ledger_refs = ledger_refs or {}
    oil_ledger_refs = oil_ledger_refs or {}

    def _get_ledgers():
        """根据开关状态获取台账实例"""
        toggle = module_refs.get("_match_toggle")
        if not toggle or not toggle.value:
            return None, None
        eq = ledger_refs.get("get_ledger", lambda: None)()
        oil = oil_ledger_refs.get("get_oil", lambda: None)()
        # 日志：显示台账加载状态
        if eq is None and oil is None:
            logging.warning("台账匹配已启用，但设备台账和油品台账均未加载")
        elif eq is None:
            logging.warning("设备台账未加载，设备匹配将被跳过")
        elif oil is None:
            logging.warning("油品台账未加载，油品匹配将被跳过")
        return eq, oil

    async def handle_fuel_click(e: ft.ControlEvent):
        eq, oil = _get_ledgers()
        await on_fuel_process(page, module_refs["fuel"], log, equipment_ledger=eq, oil_ledger=oil)

    async def handle_prod_click(e: ft.ControlEvent):
        eq, oil = _get_ledgers()
        await on_prod_process(page, module_refs["prod"], log, equipment_ledger=eq, oil_ledger=oil)

    async def handle_elec_click(e: ft.ControlEvent):
        eq, oil = _get_ledgers()
        await on_elec_process(page, module_refs["elec"], log, equipment_ledger=eq, oil_ledger=oil)

    async def handle_work_click(e: ft.ControlEvent):
        eq, oil = _get_ledgers()
        await on_work_process(page, module_refs["work"], log, equipment_ledger=eq, oil_ledger=oil)

    async def handle_merge_click(e: ft.ControlEvent):
        eq, oil = _get_ledgers()
        await on_merge_process(page, module_refs["merge"], log, equipment_ledger=eq, oil_ledger=oil)

    module_refs["fuel"]["btn"].on_click = handle_fuel_click
    module_refs["prod"]["btn"].on_click = handle_prod_click
    module_refs["elec"]["btn"].on_click = handle_elec_click
    module_refs["work"]["btn"].on_click = handle_work_click
    module_refs["merge"]["btn"].on_click = handle_merge_click

    # Batch
    if "batch" in module_refs:
        async def handle_batch_click(e: ft.ControlEvent):
            batch_toggle = module_refs["batch"].get("ledger_toggle")
            if batch_toggle and batch_toggle.value:
                eq = ledger_refs.get("get_ledger", lambda: None)()
                oil = oil_ledger_refs.get("get_oil", lambda: None)()
            else:
                eq, oil = None, None
            await on_batch_process(page, module_refs["batch"], log, equipment_ledger=eq, oil_ledger=oil)
        module_refs["batch"]["btn"].on_click = handle_batch_click


async def on_sync_process(page: ft.Page, sync_refs: dict, log):
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

    set_btn_state(btn, False, "同步中...")
    result_text.visible = False
    result_text.update()

    try:
        _log_message(log, f"[数据同步] 开始同步 (模式={mode}, 类型={selected_types}, 预览={dry_run})")

        def _do_sync():
            return sync_to_minebase(
                input_dir=path,
                mode=mode,
                data_types=selected_types,
                dry_run=dry_run,
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


def init(config_section_refs: dict):
    """初始化：加载配置"""
    if "load_config" in config_section_refs:
        config_section_refs["load_config"]()
