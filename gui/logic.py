"""
GUI 业务逻辑层
处理各模块的后台任务、线程管理
"""
import asyncio
import flet as ft
import os
from func.excel_fuel import process_diesel_data
from func.excel_production_enhanced import MiningDataProcessor as ProdProcessor
from func.excel_electrical import parse_excel_data
from func.excel_worktime import process_excel_data
from func.excel_merger import merge_excel_files



# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
def set_btn_state(btn: ft.Button, enabled: bool, label: str = "处理"):
    """设置按钮状态"""
    btn.disabled = not enabled
    btn.text = label
    btn.update()


# ---------------------------------------------------------------------------
# 任务执行
# ---------------------------------------------------------------------------
def _execute_task(module_type: str, path: str, **kwargs) -> str | None:
    """在后台线程中执行处理任务"""
    error_message = None

    try:
        if module_type == "fuel":
            process_diesel_data(path, kwargs.get("year"))
        elif module_type == "production":
            raw_start = kwargs.get("raw_start", 6)
            processor = ProdProcessor(raw_start=raw_start)
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
            file_dir = os.path.dirname(path) or "."
            output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
            process_excel_data(path, year, month, output_file)
        elif module_type == "merge":
            keyword = kwargs.get("keyword", "")
            strip_time = kwargs.get("strip_time", False)
            sort_configs = kwargs.get("sort_configs", None)
            merge_excel_files(path, keyword, strip_time=strip_time, sort_configs=sort_configs)
    except Exception as ex:
        error_message = str(ex)

    return error_message


async def run_task(page: ft.Page, module_type: str, path: str, btn: ft.Button, log, **kwargs):
    """异步执行处理任务，并在 UI 线程中恢复界面状态"""
    del page  # 保留现有调用签名，避免影响其他调用方

    log(f"[{module_type}] 开始处理...")
    try:
        error_message = await asyncio.to_thread(_execute_task, module_type, path, **kwargs)
        if error_message:
            log(f"[{module_type}] 处理失败: {error_message}")
        else:
            log(f"[{module_type}] 处理成功")
    finally:
        set_btn_state(btn, True, "处理")


# ---------------------------------------------------------------------------
# 按钮点击处理
# ---------------------------------------------------------------------------
async def on_fuel_process(page: ft.Page, fuel_refs: dict, log):
    """燃油处理按钮回调"""
    path = fuel_refs["path"].value
    if not path:
        log("请先选择文件")
        return
    btn = fuel_refs["btn"]
    year = int(fuel_refs["year"].value)
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "fuel", path, btn, log, year=year)


async def on_prod_process(page: ft.Page, prod_refs: dict, log):
    """生产处理按钮回调"""
    path = prod_refs["path"].value
    if not path:
        log("请先选择 Excel 文件或文件夹")
        return

    raw_start_text = (prod_refs["raw_start"].value or "6").strip()
    try:
        raw_start = int(raw_start_text)
        if raw_start < 1:
            raise ValueError
    except ValueError:
        log("请输入有效的 raw_start（正整数）")
        return

    btn = prod_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "production", path, btn, log, raw_start=raw_start)


async def on_elec_process(page: ft.Page, elec_refs: dict, log):
    """电力处理按钮回调"""
    path = elec_refs["path"].value
    if not path:
        log("请先选择文件")
        return

    year_text = elec_refs["year"].value
    try:
        year = int(year_text)
    except (TypeError, ValueError):
        log("请输入有效的年份")
        return

    btn = elec_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "electrical", path, btn, log, year=year)


async def on_work_process(page: ft.Page, work_refs: dict, log):
    """工时处理按钮回调"""
    path = work_refs["path"].value
    if not path:
        log("请先选择文件")
        return
    btn = work_refs["btn"]
    year = int(work_refs["year"].value)
    month = int(work_refs["month"].value)
    set_btn_state(btn, False, "处理中...")
    await run_task(page, "worktime", path, btn, log, year=year, month=month)


async def on_merge_process(page: ft.Page, merge_refs: dict, log):
    """Excel 合并按钮回调"""
    path = merge_refs["path"].value
    if not path:
        log("请先选择文件夹")
        return
    keyword = (merge_refs["keyword"].value or "").strip()
    if not keyword:
        log("请输入文件名关键字")
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
    await run_task(page, "merge", path, btn, log, keyword=keyword, strip_time=strip_time, sort_configs=sort_configs)


# ---------------------------------------------------------------------------
# 初始化 & 绑定
# ---------------------------------------------------------------------------
def wire_processing_buttons(module_refs: dict, page: ft.Page, log):
    """
    将模块 refs 中的按钮绑定到处理回调
    必须在模块区域创建完成后调用
    """

    async def handle_fuel_click(e: ft.ControlEvent):
        await on_fuel_process(page, module_refs["fuel"], log)

    async def handle_prod_click(e: ft.ControlEvent):
        await on_prod_process(page, module_refs["prod"], log)

    async def handle_elec_click(e: ft.ControlEvent):
        await on_elec_process(page, module_refs["elec"], log)

    async def handle_work_click(e: ft.ControlEvent):
        await on_work_process(page, module_refs["work"], log)

    module_refs["fuel"]["btn"].on_click = handle_fuel_click
    module_refs["prod"]["btn"].on_click = handle_prod_click
    module_refs["elec"]["btn"].on_click = handle_elec_click
    module_refs["work"]["btn"].on_click = handle_work_click

    async def handle_merge_click(e: ft.ControlEvent):
        await on_merge_process(page, module_refs["merge"], log)

    module_refs["merge"]["btn"].on_click = handle_merge_click


def init(config_section_refs: dict):
    """初始化：加载配置"""
    if "load_config" in config_section_refs:
        config_section_refs["load_config"]()
