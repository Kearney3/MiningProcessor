"""维修分类配置管理区域组件

提供分类规则的导入（Excel）、导出模板、恢复默认功能，以及当前规则的可视化展示。
采用方案A：用户通过 Excel 模板维护分类规则，不在 GUI 内联编辑。
"""
import logging

import flet as ft

from gui.i18n import t

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
        (str(len(grouped)), t("components:maint_config.category")),
        (str(len(classifications)), t("components:maint_config.subcategory")),
        (str(len(noise_exact)), t("components:maint_config.exactNoise")),
        (str(len(noise_patterns)), t("components:maint_config.regexNoise")),
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
    sections.append(theme.section_title(t("components:maint_config.classificationRules")))
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
                    ft.Text(t("components:maint_config.itemssubcategory", count=len(entries)), size=11, color=theme.TEXT_SECONDARY),
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
        sections.append(theme.section_title(t("components:maint_config.reasonRules")))
        sections.append(ft.Container(height=4))

        _REASON_LABELS = {"fault": t("components:maint_config.fault"), "check_content": t("components:maint_config.checkContent"), "non_fault": t("components:maint_config.nonFault"), "skip": t("components:maint_config.skipped")}
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
        t("components:maint_config.manageFaultClassificationRulesConfigurationExcelImportconfigurationconfiguration")
        + t("components:maint_config.classificationdefaultclassificationCategoryclassificationclassification", num_majors=num_majors),
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
        t("components:maint_config.useDefaultClassificationMajorMinor", num_majors=_num_majors, num_minors=_num_minors),
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
            status_text.value = t("components:maint_config.configurationconfigurationItemsclassificationconfigurationItemsconfiguration", count=count, noise_count=noise_count)
            status_text.color = theme.TEXT_PRIMARY
            # 更新规则展示
            rules_container.content = _build_rules_display(rules)
        except Exception:
            status_text.value = t("components:maint_config.useDefaultClassificationConfiguration")
            status_text.color = theme.TEXT_SECONDARY
        try:
            status_text.update()
            rules_container.update()
        except RuntimeError:
            pass  # 控件尚未添加到页面

    # --- 导入 ---
    _import_picker = ft.FilePicker()
    page.services.append(_import_picker)
    import_btn = theme.secondary_btn(t("components:maint_config.fileExcelImport"), icon=ft.Icons.UPLOAD_FILE)

    async def _on_import_click(_):
        files = await _import_picker.pick_files(
            allowed_extensions=["xlsx", "xls"],
            dialog_title=t("components:maint_config.selectconfigurationclassificationconfigurationExcel"),
        )
        if not files:
            return
        filepath = files[0].path
        try:
            config_loader.import_maintenance_classifications(filepath)
            _log_message(log, t("components:maint_config.classificationconfigurationconfigurationImport", filepath=filepath))
            _refresh_status()
        except Exception as ex:
            _log_message(log, t("components:maint_config.importFailed", ex=ex), level=logging.ERROR)

    import_btn.on_click = _on_import_click

    # --- 导出模板 / 默认配置 ---
    _export_picker = ft.FilePicker()
    page.services.append(_export_picker)

    async def _do_export(with_defaults: bool):
        label = t("components:maint_config.includesDefaultData") if with_defaults else t("components:maint_config.blankTemplate")
        path = await _export_picker.save_file(
            dialog_title=t("components:maint_config.saveClassificationConfiguration", label=label),
            file_name=t("components:maint_config.maintenanceClassificationConfigurationTemplateXlsx"),
            allowed_extensions=["xlsx"],
        )
        if not path:
            return
        try:
            config_loader.export_maintenance_classification_template(path, with_defaults=with_defaults)
            _log_message(log, t("components:maint_config.classificationConfigurationTemplateExported", label=label, path=path))
        except Exception as ex:
            _log_message(log, t("components:maint_config.exportFailed", ex=ex), level=logging.ERROR)

    export_template_btn = theme.secondary_btn(t("components:maint_config.exportBlankTemplate"), icon=ft.Icons.FILE_DOWNLOAD)

    export_default_btn = theme.secondary_btn(t("components:maint_config.exportDefaultConfiguration"), icon=ft.Icons.FILE_DOWNLOAD)

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
                _log_message(log, t("components:maint_config.configurationdefaultclassificationconfiguration"))
                _refresh_status()
            except Exception as ex:
                _log_message(log, t("components:maint_config.restoreFailed", ex=ex), level=logging.ERROR)
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
            title=ft.Text(t("components:maint_config.confirmRestoreDefaults")),
            content=ft.Text(t("components:maint_config.defaultdefaultdefaultCategorySubcategoryclassificationdefaultDefaultconfiguratio", num_majors=num_majors, num_minors=num_minors)),
            actions=[
                ft.TextButton(t("components:maint_config.cancel"), on_click=cancel),
                ft.TextButton(t("components:maint_config.confirmRestore"), on_click=confirm),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    restore_btn = theme.secondary_btn(t("components:maint_config.restoreDefaults"), icon=ft.Icons.RESTORE)
    restore_btn.on_click = on_restore

    # --- 布局 ---
    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title(t("components:maint_config.maintenanceConfig")),
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
                theme.section_title(t("components:maint_config.actions")),
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
                            ft.Text(t("components:maint_config.configurationNotes"), size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                            ft.Text(t("components:maint_config.importFromExcelChooseAnExcelFileContainingTheClassificationRulesNoiseFiltersAndR"), size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(t("components:maint_config.exportBlankTemplateExportAHeaderOnlyTemplateForManualEntry"), size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(t("components:maint_config.exportDefaultConfigurationExportTheCompleteSystemClassificationRules"), size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(t("components:maint_config.restoreDefaultsResetTheCurrentConfigurationToSystemDefaults"), size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(t("components:maint_config.separateKeywordsWithTheChineseEnumerationComma"), size=12, color=theme.TEXT_SECONDARY),
                            ft.Text(t("components:maint_config.rulesMatchInRowOrderPutMoreSpecificKeywordsFirst"), size=12, color=theme.TEXT_SECONDARY),
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
