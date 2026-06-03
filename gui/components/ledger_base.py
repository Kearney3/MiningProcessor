"""台账区域组件通用工厂

将 ledger.py 和 oil_ledger.py 的共同结构提取为参数化的工厂函数，
消除 ~350 行重复代码。
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import flet as ft

from func import config_loader
from .common import (
    _log_message, _last_directory, _update_last_directory,
    SortState, create_sortable_columns, _cell_text,
    create_column_mapping_dialog,
)

try:
    from . import theme
except ImportError:
    import gui.theme as theme


@dataclass
class LedgerConfig:
    """台账组件配置"""
    # 显示名称
    section_title: str           # "设备台账" / "油品台账"
    label_prefix: str            # "台账" / "油品台账"
    empty_icon: str              # ft.Icons 常量
    empty_text: str              # "暂无设备台账数据" / "暂无油品台账数据"
    template_filename: str       # "设备台账模板.xlsx" / "油品台账模板.xlsx"
    dialog_title: str            # "导入设备台账" / "导入油品台账"
    dialog_height: int = 400     # 列映射对话框高度

    # 后端模块
    backend_module: object = None   # equipment_ledger / oil_ledger 模块
    backend_class_name: str = ""    # "EquipmentLedger" / "OilLedger"
    columns: list[str] = None       # LEDGER_COLUMNS / OIL_LEDGER_COLUMNS
    standard_cols: list[tuple[str, str]] = None  # 列映射标准列定义

    # config_loader 函数
    save_cache: object = None    # Callable[[list[dict]], None]
    load_cache: object = None    # Callable[[], list[dict] | None]
    clear_cache: object = None   # Callable[[], None]
    has_cache: object = None     # Callable[[], bool]

    # refs 键名前缀
    var_prefix: str = "ledger"   # "ledger" / "oil"


def create_ledger_section_factory(
    page: ft.Page,
    log,
    cfg: LedgerConfig,
) -> tuple[ft.Container, dict]:
    """通用台账区域组件工厂。

    Args:
        page: Flet 页面对象。
        log: 日志回调。
        cfg: 台账配置。

    Returns:
        (container, refs) 元组。
    """
    if cfg.columns is None:
        cfg.columns = []
    if cfg.standard_cols is None:
        cfg.standard_cols = []

    # --- 状态 ---
    records: list[dict] = []
    _page = [0]
    _instance = [None]
    _sort_state = SortState()

    # --- 控件 ---
    path_label = ft.Text(f"未加载{cfg.label_prefix}", size=12, color=ft.Colors.GREY)

    table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c)) for c in cfg.columns],
        rows=[],
        column_spacing=12,
        heading_row_height=32,
        data_row_min_height=28,
        data_row_max_height=36,
    )

    PAGE_SIZE = 20

    def _total_pages() -> int:
        return max(1, (len(records) + PAGE_SIZE - 1) // PAGE_SIZE)

    page_label = ft.Text("1 / 1", size=12)
    prev_btn = ft.IconButton(ft.Icons.CHEVRON_LEFT, disabled=True)
    next_btn = ft.IconButton(ft.Icons.CHEVRON_RIGHT, disabled=True)

    pagination = ft.Row(
        [prev_btn, page_label, next_btn],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=4,
    )

    def _update_page_controls():
        total = _total_pages()
        page_label.value = f"{_page[0] + 1} / {total}"
        prev_btn.disabled = _page[0] <= 0
        next_btn.disabled = _page[0] >= total - 1

    # --- 排序 ---
    def _sort_records():
        nonlocal records
        if not records:
            return
        df = pd.DataFrame(records)
        if _sort_state.column and _sort_state.column in df.columns:
            df = df.sort_values(by=_sort_state.column, ascending=_sort_state.ascending, kind="stable")
            records = df.to_dict("records")

    # --- 空状态提示 ---
    empty_hint = ft.Column(
        [
            ft.Icon(cfg.empty_icon, size=48, color=ft.Colors.GREY_300),
            ft.Text(cfg.empty_text, size=14, color=theme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
            ft.Text("点击上方「导入台账」开始", size=12, color=ft.Colors.GREY_400),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
    )

    # --- 表格包装器 ---
    table.expand = True
    table_wrapper = ft.Column(
        controls=[table, empty_hint],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # --- 构建表格 ---
    def build_table():
        if not records:
            table.rows = []
            table.columns = [ft.DataColumn(ft.Text("暂无数据"))]
            empty_hint.visible = True
            _update_page_controls()
            page.update()
            return

        empty_hint.visible = False

        # 应用排序
        df = pd.DataFrame(records)
        df = _sort_state.apply_to_dataframe(df)
        sorted_records = df.to_dict("records")

        start = _page[0] * PAGE_SIZE
        end = start + PAGE_SIZE
        page_records = sorted_records[start:end]

        def on_sort_callback():
            _page[0] = 0
            build_table()

        table.columns = create_sortable_columns(cfg.columns, _sort_state, on_sort_callback)

        # 设置排序指示器
        sort_col_idx = _sort_state.get_column_index(cfg.columns)
        if sort_col_idx is not None:
            table.sort_column_index = sort_col_idx
            table.sort_ascending = _sort_state.ascending
        else:
            table.sort_column_index = None

        table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(_cell_text(r.get(c)))) for c in cfg.columns]
            )
            for r in page_records
        ]
        _update_page_controls()
        page.update()

    def _on_prev(e):
        if _page[0] > 0:
            _page[0] -= 1
            build_table()

    def _on_next(e):
        if _page[0] < _total_pages() - 1:
            _page[0] += 1
            build_table()

    prev_btn.on_click = _on_prev
    next_btn.on_click = _on_next

    # --- 操作函数 ---
    def _do_import(mapping: dict, skip_header: bool):
        """列映射确认后的导入逻辑"""
        nonlocal records
        try:
            file_path = _last_directory[0]
            if not file_path or not os.path.exists(file_path):
                _log_message(log, "未选择文件")
                return

            df = pd.read_excel(file_path)
            if skip_header:
                df = df.iloc[1:]

            # 应用列映射
            renamed = {}
            for std_col, src_col in mapping.items():
                if src_col in df.columns:
                    renamed[src_col] = std_col
            if renamed:
                df = df.rename(columns=renamed)

            # 只保留标准列中存在的列
            valid_cols = [c for c in cfg.columns if c in df.columns]
            if valid_cols:
                df = df[valid_cols]

            records = df.to_dict("records")
            _page[0] = 0

            # 更新路径标签
            path_label.value = f"已加载: {Path(file_path).name}"
            path_label.color = ft.Colors.GREEN

            # 创建后端实例
            backend_class = getattr(cfg.backend_module, cfg.backend_class_name)
            instance = backend_class()
            instance._df = df
            if hasattr(instance, '_build_search_cache'):
                instance._build_search_cache()
            _instance[0] = instance

            build_table()
            _log_message(log, f"已加载{cfg.label_prefix}: {file_path}，共 {len(records)} 条记录")
        except Exception as ex:
            _log_message(log, f"加载{cfg.label_prefix}失败: {ex}", level=logging.ERROR)

    async def on_import(e):
        """导入按钮点击"""
        picker = ft.FilePicker()
        files = await picker.pick_files(
            dialog_title=cfg.dialog_title,
            allowed_extensions=["xlsx", "xls"],
            initial_directory=_last_directory[0] if _last_directory[0] else None,
        )
        if not files:
            return
        file_path = files[0].path
        _update_last_directory(file_path)
        try:
            df = pd.read_excel(file_path)
            file_columns = list(df.columns)
            dialog = create_column_mapping_dialog(
                page, file_columns, cfg.standard_cols, _do_import,
                height=cfg.dialog_height,
            )
            page.show_dialog(dialog)
            page.update()
        except Exception as ex:
            _log_message(log, f"读取{cfg.label_prefix}文件失败: {ex}", level=logging.ERROR)

    def on_export_template(e):
        """导出模板"""
        try:
            backend_class = getattr(cfg.backend_module, cfg.backend_class_name)
            instance = backend_class()
            path = os.path.join(os.getcwd(), cfg.template_filename)
            if hasattr(instance, 'export_template'):
                instance.export_template(path)
            else:
                # 回退：创建空模板
                df = pd.DataFrame(columns=cfg.columns)
                df.to_excel(path, index=False)
            _log_message(log, f"已导出模板: {path}")
        except Exception as ex:
            _log_message(log, f"导出模板失败: {ex}", level=logging.ERROR)

    def on_clear(e):
        """清空"""
        nonlocal records
        records = []
        _instance[0] = None
        _page[0] = 0
        path_label.value = f"未加载{cfg.label_prefix}"
        path_label.color = ft.Colors.GREY
        build_table()
        _log_message(log, f"{cfg.label_prefix}已清空")

    def on_save_default(e):
        """保存为默认"""
        try:
            if records and cfg.save_cache:
                cfg.save_cache(records)
                _log_message(log, f"已保存为默认{cfg.label_prefix}")
                _update_default_btn_state()
        except Exception as ex:
            _log_message(log, f"保存默认{cfg.label_prefix}失败: {ex}", level=logging.ERROR)

    def on_cancel_default(e):
        """取消默认"""
        try:
            if cfg.clear_cache:
                cfg.clear_cache()
            _log_message(log, f"已取消默认{cfg.label_prefix}")
            _update_default_btn_state()
        except Exception as ex:
            _log_message(log, f"取消默认{cfg.label_prefix}失败: {ex}", level=logging.ERROR)

    def load_from_cache():
        """从缓存加载默认台账"""
        try:
            if cfg.has_cache and cfg.has_cache() and cfg.load_cache:
                cached = cfg.load_cache()
                if cached:
                    nonlocal records
                    records = cached
                    _page[0] = 0

                    # 创建后端实例（如果支持）
                    backend_class = getattr(cfg.backend_module, cfg.backend_class_name)
                    instance = backend_class()
                    if hasattr(instance, '_df'):
                        instance._df = pd.DataFrame(cached)
                    if hasattr(instance, '_build_search_cache'):
                        instance._build_search_cache()
                    _instance[0] = instance

                    path_label.value = f"默认{cfg.label_prefix} (缓存)"
                    path_label.color = ft.Colors.GREEN
                    build_table()
                    _log_message(log, f"已自动加载默认{cfg.label_prefix}（缓存），共 {len(records)} 条")
        except Exception as ex:
            _log_message(log, f"加载缓存{cfg.label_prefix}失败: {ex}", level=logging.WARNING)

    def get_instance():
        """获取当前后端实例"""
        return _instance[0]

    # --- 按钮 ---
    import_btn = theme.secondary_btn(f"导入{cfg.label_prefix}", icon=ft.Icons.UPLOAD, on_click=on_import)
    clear_btn = theme.secondary_btn(f"清空{cfg.label_prefix}", icon=ft.Icons.DELETE_SWEEP, on_click=on_clear, disabled=True)
    export_template_btn = theme.secondary_btn("导出模板", icon=ft.Icons.DOWNLOAD, on_click=on_export_template)
    save_default_btn = theme.primary_btn("保存为默认", icon=ft.Icons.BOOKMARK, on_click=on_save_default, disabled=True)
    cancel_default_btn = theme.secondary_btn("取消默认", icon=ft.Icons.BOOKMARK_REMOVE, on_click=on_cancel_default, disabled=not (cfg.has_cache() if cfg.has_cache else False))

    def _update_default_btn_state():
        has_records = len(records) > 0
        has_cached = cfg.has_cache() if cfg.has_cache else False
        clear_btn.disabled = not has_records
        save_default_btn.disabled = not has_records
        cancel_default_btn.disabled = not has_cached
        try:
            clear_btn.update()
            save_default_btn.update()
            cancel_default_btn.update()
        except (RuntimeError, AttributeError):
            pass

    # --- 布局 ---
    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title(cfg.section_title),
                ft.Column(
                    [
                        ft.Row(
                            [import_btn, clear_btn, export_template_btn],
                            spacing=8,
                        ),
                        ft.Row(
                            [save_default_btn, cancel_default_btn, path_label],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Container(
                    content=table_wrapper,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_MD,
                    padding=4,
                    bgcolor=theme.SURFACE_HIGH,
                    expand=True,
                ),
                pagination,
            ],
            spacing=8,
            expand=True,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    # --- 初始加载缓存 ---
    load_from_cache()
    _update_default_btn_state()

    # --- refs ---
    refs = {
        f"{cfg.var_prefix}_table": table,
        f"{cfg.var_prefix}_path_label": path_label,
        f"{cfg.var_prefix}_records": records,
        f"get_{cfg.var_prefix}": get_instance,
        "build_table": build_table,
        "load_from_cache": load_from_cache,
    }

    return container, refs
