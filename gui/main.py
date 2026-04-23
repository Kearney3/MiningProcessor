"""
GUI 主窗口 - Flet 实现
使用模块化结构：components.py（UI组件）+ logic.py（业务逻辑）
"""
import flet as ft
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gui.components as cmp
import gui.logic as logic


def main(page: ft.Page):
    page.title = "矿山数据处理工具"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1020
    page.window_height = 850

    # ---- 滚动容器 ----
    scroll_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    # ---- 共享日志状态 ----
    log_lines: list[str] = []

    def log(msg: str):
        log_lines.append(msg)
        if len(log_lines) > 500:
            log_lines.pop(0)
        log_view.value = "\n".join(log_lines)
        try:
            log_view.update()
        except RuntimeError:
            pass  # Guard: log_view not yet added to page

    # ---- 创建各区域 UI ----
    ledger_section, ledger_refs = cmp.create_ledger_section(page, log)
    config_section, config_refs = cmp.create_config_section(page, log)
    modules_section, module_refs = cmp.create_modules_section(page)
    log_view = cmp.create_log_view()
    progress_bar = ft.ProgressBar(value=0, width=page.width - 40)

    # ---- 绑定处理按钮 ----
    logic.wire_processing_buttons(module_refs, page, log)

    # ---- 组装页面 ----
    scroll_col.controls.append(ft.Text("矿山数据处理工具", size=24, weight=ft.FontWeight.BOLD))
    scroll_col.controls.append(ft.Divider())
    scroll_col.controls.append(ledger_section)
    scroll_col.controls.append(ft.Divider())
    scroll_col.controls.append(config_section)
    scroll_col.controls.append(ft.Divider())
    scroll_col.controls.append(modules_section)
    scroll_col.controls.append(ft.Divider())
    scroll_col.controls.append(log_view)
    scroll_col.controls.append(progress_bar)
    page.add(scroll_col)

    # ---- 初始化（放在 page.add 之后） ----
    logic.init(config_refs)
    log("已就绪")


if __name__ == "__main__":
    ft.run(main)
