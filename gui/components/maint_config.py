"""维修分类配置管理区域组件

提供分类规则的导入（Excel）、导出模板、恢复默认功能，以及当前规则的可视化展示。
采用方案A：用户通过 Excel 模板维护分类规则，不在 GUI 内联编辑。
"""
import logging

import flet as ft

from .common import _log_message

try:
    from . import theme
except ImportError:
    import gui.theme as theme


def _build_rules_display(rules: dict) -> ft.Column:
    """构建分类规则的可视化展示。"""
    classifications = rules.get("classifications", [])
    noise_exact = rules.get("noise_exact", set())
    noise_patterns = rules.get("noise_patterns", [])
    reason_rules = rules.get("reason_rules", {})

    # 按大类分组
    grouped: dict[str, list[dict]] = {}
    for entry in classifications:
        major = entry["major"]
        grouped.setdefault(major, []).append(entry)

    sections: list[ft.Control] = []

    # ── 统计概览 ──
    stats = [
        (str(len(grouped)), "大类"),
        (str(len(classifications)), "小类"),
        (str(len(noise_exact)), "精确噪声"),
        (str(len(noise_patterns)), "正则噪声"),
    ]
    stat_items = []
    for val, label in stats:
        stat_items.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(val, size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                        ft.Text(label, size=11, color=theme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                bgcolor=theme.SURFACE_HIGH,
                border_radius=theme.RADIUS_SM,
            )
        )
    sections.append(
        ft.Container(
            content=ft.Row(stat_items, spacing=8, alignment=ft.MainAxisAlignment.START),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border.all(1, theme.BORDER),
            border_radius=theme.RADIUS_SM,
        )
    )
    sections.append(ft.Container(height=12))

    # ── 分类规则列表 ──
    sections.append(theme.section_title("分类规则"))
    sections.append(ft.Container(height=4))

    for major, entries in grouped.items():
        rows: list[ft.Control] = []
        for entry in entries:
            kw_chips = ft.Row(
                [
                    ft.Container(
                        content=ft.Text(kw, size=11, color=ft.Colors.BLUE_700),
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    )
                    for kw in entry["keywords"]
                ],
                spacing=4,
                wrap=True,
            )
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(entry["minor"], size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_PRIMARY),
                                width=120,
                            ),
                            ft.Container(content=kw_chips, expand=True),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                )
            )

        major_header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(major, size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                    ft.Text(f"{len(entries)} 个小类", size=11, color=theme.TEXT_SECONDARY),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=theme.SURFACE_HIGH,
            border_radius=ft.BorderRadius.only(top_left=6, top_right=6, bottom_left=0, bottom_right=0),
        )
        sections.append(
            ft.Container(
                content=ft.Column([major_header, *rows], spacing=0),
                border=ft.Border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_SM,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        )
        sections.append(ft.Container(height=8))

    # ── 原因规则 ──
    if reason_rules:
        sections.append(ft.Container(height=4))
        sections.append(theme.section_title("原因规则"))
        sections.append(ft.Container(height=4))

        _REASON_LABELS = {"fault": "故障", "check_content": "检查内容", "non_fault": "非故障", "skip": "跳过"}
        _REASON_COLORS = {"fault": ft.Colors.RED_600, "check_content": ft.Colors.AMBER_600, "non_fault": ft.Colors.GREEN_600, "skip": ft.Colors.GREY_400}

        reason_items: list[ft.Control] = []
        for reason, rule in reason_rules.items():
            reason_items.append(
                ft.Row(
                    [
                        ft.Text(reason, size=12, color=theme.TEXT_PRIMARY, width=80),
                        ft.Text("→", size=12, color=theme.TEXT_SECONDARY),
                        ft.Text(_REASON_LABELS.get(rule, rule), size=12, weight=ft.FontWeight.W_500, color=_REASON_COLORS.get(rule, theme.TEXT_PRIMARY)),
                    ],
                    spacing=4,
                )
            )
        sections.append(
            ft.Container(
                content=ft.Row(reason_items, spacing=16, wrap=True),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border=ft.Border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_SM,
                bgcolor=theme.SURFACE_HIGH,
            )
        )

    return ft.Column(sections, spacing=0)


def _build_desc_text() -> ft.Text:
    """构建分类配置说明文字，动态显示实际大类数量。"""
    from func.maintenance_classification import get_default_classifications
    defs = get_default_classifications()
    num_majors = len({c["major"] for c in defs["classifications"]})
    return ft.Text(
        "管理维修记录的故障分类规则。支持从 Excel 导入自定义配置，"
        f"或使用系统默认的 {num_majors} 大类分类体系。",
        size=13,
        color=theme.TEXT_SECONDARY,
    )


def create_maint_config_section(page: ft.Page, log) -> tuple[ft.Container, dict]:
    """创建维修分类配置管理区域。

    Returns:
        (container, maint_config_refs)
    """
    from func import config_loader

    # --- 状态 ---
    from func.maintenance_classification import get_default_classifications
    _defs = get_default_classifications()
    _num_majors = len({c["major"] for c in _defs["classifications"]})
    _num_minors = len(_defs["classifications"])
    status_text = ft.Text(
        f"使用默认分类配置（{_num_majors} 大类 × {_num_minors} 小类）",
        size=13,
        color=theme.TEXT_SECONDARY,
    )

    # --- 规则展示区域 ---
    rules_container = ft.Container()

    def _refresh_status():
        """刷新状态文本和规则展示。"""
        try:
            rules = config_loader.get_maintenance_classifications()
            count = len(rules.get("classifications", []))
            noise_count = len(rules.get("noise_exact", set())) + len(rules.get("noise_patterns", []))
            status_text.value = f"当前配置: {count} 条分类规则, {noise_count} 条噪声规则"
            status_text.color = theme.TEXT_PRIMARY
            # 更新规则展示
            rules_container.content = _build_rules_display(rules)
        except Exception:
            status_text.value = "使用默认分类配置"
            status_text.color = theme.TEXT_SECONDARY
        try:
            status_text.update()
            rules_container.update()
        except RuntimeError:
            pass  # 控件尚未添加到页面

    # --- 导入 ---
    _import_picker = ft.FilePicker()
    page.services.append(_import_picker)
    import_btn = theme.secondary_btn("从 Excel 导入", icon=ft.Icons.UPLOAD_FILE)

    async def _on_import_click(_):
        files = await _import_picker.pick_files(
            allowed_extensions=["xlsx", "xls"],
            dialog_title="选择维修分类配置 Excel",
        )
        if not files:
            return
        filepath = files[0].path
        try:
            config_loader.import_maintenance_classifications(filepath)
            _log_message(log, f"分类配置已从 {filepath} 导入")
            _refresh_status()
        except Exception as ex:
            _log_message(log, f"导入失败: {ex}", level=logging.ERROR)

    import_btn.on_click = _on_import_click

    # --- 导出模板 / 默认配置 ---
    _export_picker = ft.FilePicker()
    page.services.append(_export_picker)

    async def _do_export(with_defaults: bool):
        label = "含默认数据" if with_defaults else "空白模板"
        path = await _export_picker.save_file(
            dialog_title=f"保存分类配置 ({label})",
            file_name="维修分类配置模板.xlsx",
            allowed_extensions=["xlsx"],
        )
        if not path:
            return
        try:
            config_loader.export_maintenance_classification_template(path, with_defaults=with_defaults)
            _log_message(log, f"分类配置模板已导出 ({label}): {path}")
        except Exception as ex:
            _log_message(log, f"导出失败: {ex}", level=logging.ERROR)

    export_template_btn = theme.secondary_btn("导出空白模板", icon=ft.Icons.FILE_DOWNLOAD)

    export_default_btn = theme.secondary_btn("导出默认配置", icon=ft.Icons.FILE_DOWNLOAD)

    async def _on_export_template(e):
        await _do_export(with_defaults=False)

    async def _on_export_default(e):
        await _do_export(with_defaults=True)

    export_template_btn.on_click = _on_export_template
    export_default_btn.on_click = _on_export_default

    # --- 恢复默认 ---
    def on_restore(e):
        def confirm(e):
            try:
                from func.maintenance_classification import get_default_classifications
                defaults = get_default_classifications()
                config_loader.update_maintenance_classifications(defaults)
                _log_message(log, "已恢复默认分类配置")
                _refresh_status()
            except Exception as ex:
                _log_message(log, f"恢复失败: {ex}", level=logging.ERROR)
            dialog.open = False
            page.update()

        def cancel(e):
            dialog.open = False
            page.update()

        from func.maintenance_classification import get_default_classifications
        defs = get_default_classifications()
        num_majors = len({c["major"] for c in defs["classifications"]})
        num_minors = len(defs["classifications"])
        dialog = ft.AlertDialog(
            title=ft.Text("确认恢复默认"),
            content=ft.Text(f"将恢复为系统默认的 {num_majors} 大类 × {num_minors} 小类分类规则，自定义配置将丢失。"),
            actions=[
                ft.TextButton("取消", on_click=cancel),
                ft.TextButton("确认恢复", on_click=confirm),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    restore_btn = theme.secondary_btn("恢复默认配置", icon=ft.Icons.RESTORE)
    restore_btn.on_click = on_restore

    # --- 布局 ---
    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("维修分类配置"),
                _build_desc_text(),
                ft.Container(height=8),
                # 状态
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=theme.TEXT_SECONDARY),
                            status_text,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_SM,
                    bgcolor=theme.SURFACE_HIGH,
                ),
                ft.Container(height=12),
                # 操作按钮
                theme.section_title("操作"),
                ft.Container(height=4),
                ft.Row(
                    [import_btn, export_template_btn, export_default_btn, restore_btn],
                    spacing=8,
                    wrap=True,
                ),
                ft.Container(height=12),
                # 规则展示
                rules_container,
                ft.Container(height=12),
                # 说明
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("配置说明", size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                            ft.Text("• 从 Excel 导入：选择包含「分类规则」「噪声过滤」「原因规则」sheet 的 Excel 文件", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text("• 导出空白模板：导出仅有表头的模板，供手动填写", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text("• 导出默认配置：导出包含系统默认分类规则的完整配置", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text("• 恢复默认配置：将当前配置重置为系统默认值", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text("• 关键词使用中文顿号「、」分隔", size=12, color=theme.TEXT_SECONDARY),
                            ft.Text("• 分类按行顺序匹配，更具体的关键词应放在前面", size=12, color=theme.TEXT_SECONDARY),
                        ],
                        spacing=4,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_SM,
                    bgcolor=theme.SURFACE_HIGH,
                ),
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    _refresh_status()

    maint_config_refs = {
        "refresh_status": _refresh_status,
    }
    return container, maint_config_refs
