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


from gui.components.common import _log_message


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
def set_btn_state(btn: ft.Button, enabled: bool, label: str = "处理"):
    """设置按钮状态"""
    btn.disabled = not enabled
    btn.text = label
    btn.update()


# ---------------------------------------------------------------------------
# 台账匹配后处理
# ---------------------------------------------------------------------------
def _find_col(columns, candidates):
    """在列名列表中查找第一个匹配的候选列名"""
    for c in candidates:
        if c in columns:
            return c
    return None


def _apply_ledger_matching(output_file: str, equipment_ledger=None, oil_ledger=None):
    """
    对已写入的 Excel 文件进行台账匹配后处理。
    读取每个 sheet，检测列名，追加匹配字段，重新写回。
    对于生产数据（同时包含矿卡名称和挖机名称），匹配列名会添加（矿卡）或（挖机）后缀。
    """
    if not equipment_ledger and not oil_ledger:
        return

    try:
        xl = pd.ExcelFile(output_file)
    except Exception as ex:
        logging.warning(f"无法读取输出文件进行台账匹配: {ex}")
        return

    sheet_data = {}
    matched_any = False

    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name)
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
        if module_type == "fuel":
            process_diesel_data(path, kwargs.get("year"))
        elif module_type == "production":
            raw_start = kwargs.get("raw_start", 6)
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
            parse_excel_data(path, kwargs.get("year"))
        elif module_type == "worktime":
            year = kwargs.get("year", 2025)
            month = kwargs.get("month", 1)
            header_mapping = kwargs.get("header_mapping", None)
            file_dir = os.path.dirname(path) or "."
            output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
            process_excel_data(path, year, month, output_file, header_mapping=header_mapping)
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
                _apply_ledger_matching(output_file, equipment_ledger, oil_ledger)
    except Exception as ex:
        error_message = str(ex)

    return error_message


async def run_task(page: ft.Page, module_type: str, path: str, btn: ft.Button, log, **kwargs):
    """异步执行处理任务，按钮状态由调用方自行恢复"""
    del page, btn  # 保留现有调用签名，避免影响其他调用方

    _log_message(log, f"[{module_type}] 开始处理...")
    error_message = await asyncio.to_thread(_execute_task, module_type, path, **kwargs)
    if error_message:
        _log_message(log, f"[{module_type}] 处理失败: {error_message}", level=logging.ERROR)
    else:
        _log_message(log, f"[{module_type}] 处理成功")


# ---------------------------------------------------------------------------
# 按钮点击处理
# ---------------------------------------------------------------------------
async def on_fuel_process(page: ft.Page, fuel_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """燃油处理按钮回调"""
    path = fuel_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件", level=logging.WARNING)
        return
    btn = fuel_refs["btn"]
    year = int(fuel_refs["year"].value)
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "fuel", path, btn, log, year=year, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
    set_btn_state(btn, True, "处理")


async def on_prod_process(page: ft.Page, prod_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """生产处理按钮回调"""
    path = prod_refs["path"].value
    if not path:
        _log_message(log, "请先选择 Excel 文件或文件夹", level=logging.WARNING)
        return

    raw_start_text = (prod_refs["raw_start"].value or "6").strip()
    try:
        raw_start = int(raw_start_text)
        if raw_start != -1 and raw_start < 1:
            raise ValueError
    except ValueError:
        _log_message(log, "请输入有效的 raw_start（正整数或-1【自动检测行】）", level=logging.WARNING)
        return

    btn = prod_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "production", path, btn, log, raw_start=raw_start, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
    set_btn_state(btn, True, "处理")


async def on_elec_process(page: ft.Page, elec_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """电力处理按钮回调"""
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

    btn = elec_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "electrical", path, btn, log, year=year, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
    set_btn_state(btn, True, "处理")


async def on_work_process(page: ft.Page, work_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """工时处理按钮回调"""
    path = work_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件", level=logging.WARNING)
        return
    btn = work_refs["btn"]
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
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "worktime", path, btn, log, year=year, month=month,
                   equipment_ledger=equipment_ledger, oil_ledger=oil_ledger,
                   header_mapping=header_mapping)
    set_btn_state(btn, True, "处理")


async def on_merge_process(page: ft.Page, merge_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """Excel 合并按钮回调"""
    path = merge_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件夹", level=logging.WARNING)
        return
    keyword = (merge_refs["keyword"].value or "").strip()
    if not keyword:
        _log_message(log, "请输入文件名关键字", level=logging.WARNING)
        return
    strip_time = bool(merge_refs["strip_time"].value)
    # 收集排序配置
    sort_configs = []
    for cfg in merge_refs.get("sort_configs_state", []):
        col = (cfg.get("column") or "").strip()
        if col:
            sort_configs.append({"column": col, "ascending": bool(cfg.get("ascending", True))})
    btn = merge_refs["btn"]
    set_btn_state(btn, False, "合并中...")
    await run_task(page, "merge", path, btn, log, keyword=keyword, strip_time=strip_time, sort_configs=sort_configs, equipment_ledger=equipment_ledger, oil_ledger=oil_ledger)
    set_btn_state(btn, True, "合并")


async def on_batch_process(page: ft.Page, batch_refs: dict, log, equipment_ledger=None, oil_ledger=None):
    """批量处理按钮回调（带文件扫描 + 缺失确认弹窗）"""
    import threading

    path = batch_refs["path"].value
    if not path:
        _log_message(log, "请先选择文件夹", level=logging.WARNING)
        return

    year = int(batch_refs["year"].value)
    month = int(batch_refs["month"].value)
    raw_start = -1 if batch_refs["auto_detect"].value else 6
    merge_output = bool(batch_refs["merge"].value)

    btn = batch_refs["btn"]
    set_btn_state(btn, False, "扫描中...")

    # ── 第一阶段：扫描文件 ──
    try:
        matched, missing = await asyncio.to_thread(scan_files, path)
    except Exception as ex:
        _log_message(log, f"文件扫描失败: {ex}", level=logging.ERROR)
        set_btn_state(btn, True, "批量处理")
        return

    found_labels = [MODULE_LABELS.get(k, k) for k in matched]
    missing_labels = [MODULE_LABELS.get(k, k) for k in missing]
    _log_message(log, f"扫描完成 — 已找到: {', '.join(found_labels) or '无'}; 未找到: {', '.join(missing_labels) or '无'}")

    # ── 第二阶段：缺失确认弹窗 ──
    if missing:
        event = threading.Event()
        should_continue = [True]

        def _on_confirm(e):
            page.close(dialog)
            should_continue[0] = True
            event.set()

        def _on_cancel(e):
            page.close(dialog)
            should_continue[0] = False
            event.set()

        missing_text = "、".join(missing_labels)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("部分数据文件未找到"),
            content=ft.Text(f"以下类型的数据文件未在文件夹中检测到：\n\n{missing_text}\n\n是否继续处理已找到的数据？"),
            actions=[
                ft.TextButton("继续处理", on_click=_on_confirm),
                ft.TextButton("取消", on_click=_on_cancel),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dialog)

        # 等待用户操作（带超时防死锁）
        confirmed = await asyncio.to_thread(event.wait, 300)
        if not confirmed or not should_continue[0]:
            _log_message(log, "用户取消了批量处理", level=logging.WARNING)
            set_btn_state(btn, True, "批量处理")
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
        await asyncio.to_thread(
            process_files,
            path, matched, year, month, raw_start, merge_output,
            equipment_ledger, oil_ledger, filter_date,
            worktime_header_mapping,
        )
        _log_message(log, "批量处理完成")
    except Exception as ex:
        _log_message(log, f"批量处理失败: {ex}", level=logging.ERROR)
    finally:
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
        oil = oil_ledger_refs.get("get_oil_ledger", lambda: None)()
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
                oil = oil_ledger_refs.get("get_oil_ledger", lambda: None)()
            else:
                eq, oil = None, None
            await on_batch_process(page, module_refs["batch"], log, equipment_ledger=eq, oil_ledger=oil)
        module_refs["batch"]["btn"].on_click = handle_batch_click


def init(config_section_refs: dict):
    """初始化：加载配置"""
    if "load_config" in config_section_refs:
        config_section_refs["load_config"]()
