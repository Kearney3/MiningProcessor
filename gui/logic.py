"""
GUI 业务逻辑层
处理各模块的后台任务、线程管理
"""
import flet as ft
import io
import os
import sys
import threading
from excel_fuel import process_diesel_data
from excel_production_enhanced import MiningDataProcessor as ProdProcessor
from excel_electrical import parse_excel_data
from excel_worktime import process_excel_data


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
def set_btn_state(btn: ft.Button, enabled: bool, label: str = "处理"):
    """设置按钮状态"""
    btn.disabled = not enabled
    btn.text = label
    btn.update()


# ---------------------------------------------------------------------------
# 线程任务包装
# ---------------------------------------------------------------------------
def run_task(page: ft.Page, module_type: str, path: str, btn: ft.Button, log, **kwargs):
    """在后台线程中执行处理任务"""
    def do():
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            log(f"[{module_type}] 开始处理...")
            if module_type == "fuel":
                process_diesel_data(path, kwargs.get("year"))
            elif module_type == "production":
                output_file = os.path.join(
                    os.path.dirname(path) or ".", "工作效率表_合并.xlsx"
                )
                processor = ProdProcessor()
                processor.process_folder(path, output_file)
            elif module_type == "electrical":
                parse_excel_data(path, kwargs.get("year"))
            elif module_type == "worktime":
                year = kwargs.get("year", 2025)
                month = kwargs.get("month", 1)
                file_dir = os.path.dirname(path) or "."
                output_file = os.path.join(file_dir, f"{year}{month:02d}_工作效率表.xlsx")
                process_excel_data(path, year, month, output_file)

            captured_stdout = sys.stdout.getvalue()
            captured_stderr = sys.stderr.getvalue()
            if captured_stdout:
                for line in captured_stdout.rstrip("\n").split("\n"):
                    if line.strip():
                        log(f"[stdout] {line}")
            if captured_stderr:
                for line in captured_stderr.rstrip("\n").split("\n"):
                    if line.strip():
                        log(f"[stderr] {line}")
            log(f"[{module_type}] 处理成功")
        except Exception as ex:
            captured_stderr = sys.stderr.getvalue()
            if captured_stderr:
                for line in captured_stderr.rstrip("\n").split("\n"):
                    if line.strip():
                        log(f"[stderr] {line}")
            log(f"[{module_type}] 处理失败: {ex}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            def restore():
                set_btn_state(btn, True, "处理")
            page.call_on_main_thread(restore)
            page.update()

    t = threading.Thread(target=do, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# 按钮点击处理
# ---------------------------------------------------------------------------
def on_fuel_process(page: ft.Page, fuel_refs: dict, log):
    """燃油处理按钮回调"""
    path = fuel_refs["path"].value
    if not path:
        log("请先选择文件")
        return
    btn = fuel_refs["btn"]
    year = fuel_refs["year"].value
    set_btn_state(btn, False, "处理中...")
    run_task(page, "fuel", path, btn, log, year=year)


def on_prod_process(page: ft.Page, prod_refs: dict, log):
    """生产处理按钮回调"""
    path = prod_refs["path"].value
    if not path:
        log("请先选择文件夹")
        return
    btn = prod_refs["btn"]
    set_btn_state(btn, False, "处理中...")
    run_task(page, "production", path, btn, log)


def on_elec_process(page: ft.Page, elec_refs: dict, log):
    """电力处理按钮回调"""
    path = elec_refs["path"].value
    if not path:
        log("请先选择文件")
        return
    btn = elec_refs["btn"]
    year = elec_refs["year"].value
    set_btn_state(btn, False, "处理中...")
    run_task(page, "electrical", path, btn, log, year=year)


def on_work_process(page: ft.Page, work_refs: dict, log):
    """工时处理按钮回调"""
    path = work_refs["path"].value
    if not path:
        log("请先选择文件或文件夹")
        return
    btn = work_refs["btn"]
    year = int(work_refs["year"].value)
    month = int(work_refs["month"].value)
    set_btn_state(btn, False, "处理中...")
    run_task(page, "worktime", path, btn, log, year=year, month=month)


# ---------------------------------------------------------------------------
# 初始化 & 绑定
# ---------------------------------------------------------------------------
def wire_processing_buttons(module_refs: dict, page: ft.Page, log):
    """
    将模块 refs 中的按钮绑定到处理回调
    必须在模块区域创建完成后调用
    """
    module_refs["fuel"]["btn"].on_click = lambda e: on_fuel_process(page, module_refs["fuel"], log)
    module_refs["prod"]["btn"].on_click = lambda e: on_prod_process(page, module_refs["prod"], log)
    module_refs["elec"]["btn"].on_click = lambda e: on_elec_process(page, module_refs["elec"], log)
    module_refs["work"]["btn"].on_click = lambda e: on_work_process(page, module_refs["work"], log)


def init(config_section_refs: dict):
    """初始化：加载配置"""
    if "load_config" in config_section_refs:
        config_section_refs["load_config"]()