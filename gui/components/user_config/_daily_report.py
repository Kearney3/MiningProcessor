"""日报导出设置：物料关键字和公式。"""
from __future__ import annotations

import logging
from copy import deepcopy

import flet as ft

from func import config_loader
from func.daily_report import DAILY_REPORT_FORMULA_OUTPUTS, validate_daily_report_formulas
from gui.components.common import _log_message

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from ._helpers import _create_keyword_input
from gui.i18n import t


def _create_daily_report_config_section(page: ft.Page, log):
    """创建日报设置卡片，使用与工作效率表头映射一致的关键字标签交互。"""
    config_state: dict = {}
    material_rows: list[dict] = []
    formula_fields: dict[str, ft.TextField] = {}
    status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    material_column = ft.Column(spacing=6)
    formula_column = ft.Column(spacing=6)

    def _set_status(message: str, color=theme.TEXT_SECONDARY):
        status_text.value = message
        status_text.color = color
        try:
            status_text.update()
        except (RuntimeError, AttributeError):
            pass

    def _rebuild_material_rows(mapping: dict):
        material_rows.clear()
        for target, keywords in mapping.items():
            kw_column, kw_get, kw_set = _create_keyword_input(
                page, "", t("components:user_config._daily_report.enterAKeywordAndPressEnterToAdd"),
            )
            kw_set(keywords if isinstance(keywords, list) else [])
            target_field = ft.TextField(
                value=str(target), width=115, dense=True, text_size=13,
                border_color=theme.BORDER, focused_border_color=theme.PRIMARY,
            )
            material_rows.append({"target": target_field, "get": kw_get})
            material_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(t("components:user_config._daily_report.statisticsColumn"), width=48, size=11, color=theme.TEXT_SECONDARY),
                            target_field,
                            ft.Container(content=kw_column, expand=True),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    border=ft.Border(bottom=ft.BorderSide(1, theme.BORDER)),
                )
            )
        try:
            material_column.update()
        except (RuntimeError, AttributeError):
            pass

    def _collect_material_mapping() -> dict[str, list[str]]:
        result = {}
        for row in material_rows:
            target = (row["target"].value or "").strip()
            keywords = [str(value).strip() for value in row["get"]() if str(value).strip()]
            if target and keywords:
                result[target] = keywords
        return result

    def _collect_formulas() -> dict[str, str]:
        return {key: field.value or "" for key, field in formula_fields.items()}

    def _reload(e=None):
        nonlocal config_state
        config_state = config_loader.get_daily_report_config()
        for key in DAILY_REPORT_FORMULA_OUTPUTS:
            if key not in formula_fields:
                formula_fields[key] = ft.TextField(
                    label=key,
                    value="",
                    multiline=True,
                    min_lines=1,
                    max_lines=2,
                    expand=True,
                    dense=True,
                    text_size=12,
                    border_color=theme.BORDER,
                    focused_border_color=theme.PRIMARY,
                )
            formula_fields[key].value = str(config_state.get("formulas", {}).get(key, ""))
            formula_fields[key].error_text = None
        formula_column.controls = list(formula_fields.values())
        try:
            formula_column.update()
        except (RuntimeError, AttributeError):
            pass
        _rebuild_material_rows(config_state.get("material_statistics", {}))
        _set_status("")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _validate(e=None, formulas: dict[str, str] | None = None):
        formulas = formulas if formulas is not None else _collect_formulas()
        errors = validate_daily_report_formulas(formulas)
        for key, field in formula_fields.items():
            field.error_text = errors.get(key)
        if errors:
            message = "；".join(f"{key}：{value}" for key, value in errors.items())
            _set_status(
                t(
                    "components:user_config._daily_report.dailyReportFormulaValidationFailed",
                    message=message,
                ),
                theme.ERROR,
            )
            _log_message(log, t("components:user_config._daily_report.dailyReportFormulaValidationFailed", message=message), level=logging.WARNING)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return errors
        _set_status(
            t("components:user_config._daily_report.formulaValidationPassed"),
            theme.SUCCESS,
        )
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass
        return {}

    def _save(e=None):
        formulas = _collect_formulas()
        errors = _validate(formulas=formulas)
        if errors:
            return

        report_config = {
            "material_statistics": _collect_material_mapping(),
            "formulas": formulas,
        }
        try:
            config_loader.save_daily_report_config(report_config)
            _set_status(t("components:user_config._daily_report.dailyReportExportSettingsSaved"), theme.SUCCESS)
            _log_message(log, t("components:user_config._daily_report.saveddailyReportExportSettings"))
        except Exception as exc:
            _set_status(str(exc), theme.ERROR)
            _log_message(log, t("components:user_config._daily_report.dailyReportExportSettingssaveFailed", exc=exc), level=logging.ERROR)

    def _reset(e=None):
        _rebuild_material_rows(deepcopy(config_loader.DEFAULT_DAILY_REPORT_CONFIG["material_statistics"]))
        defaults = config_loader.DEFAULT_DAILY_REPORT_CONFIG
        for key, field in formula_fields.items():
            field.value = defaults["formulas"].get(key, "")
            field.error_text = None
        _set_status(t("components:user_config._daily_report.defaultdefaultValueDefaultsavedefault"), theme.TEXT_SECONDARY)
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    material_header = ft.Row(
        [
            ft.Text(t("components:user_config._daily_report.statisticsColumn"), width=48, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
            ft.Text(t("components:user_config._daily_report.itemname"), width=115, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
            ft.Text(t("components:user_config._daily_report.keywordNameMatchingMatching"), expand=True, size=11, weight=ft.FontWeight.W_600, color=theme.TEXT_SECONDARY),
        ],
        spacing=8,
    )
    material_box = ft.Container(
        content=ft.Column([material_header, material_column], spacing=0),
        border=ft.Border.all(1, theme.BORDER),
        border_radius=8,
    )
    formula_hint = ft.Text(
        t("components:user_config._daily_report.validateFormulaSyntaxAndFieldNamesWhenSavingVerifyFieldsAgainstActualWorktimeHea"),
        size=11, color=theme.TEXT_SECONDARY,
    )
    action_row = ft.Row(
        [
            theme.secondary_btn(
                t("components:user_config._daily_report.validateFormula"),
                icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                on_click=_validate,
                height=34,
            ),
            theme.primary_btn(t("components:user_config._daily_report.save"), icon=ft.Icons.SAVE, on_click=_save),
            theme.secondary_btn(t("components:user_config._daily_report.reload"), icon=ft.Icons.REFRESH, on_click=_reload, height=34),
            theme.secondary_btn(t("components:user_config._daily_report.restoreDefault"), icon=ft.Icons.RESTART_ALT, on_click=_reset, height=34),
        ], spacing=8, wrap=True,
    )
    card = theme.make_collapsible(
        title=t("components:user_config._daily_report.dailyReportExportSettings"),
        subtitle=t("components:user_config._daily_report.dailyReportexportdailyReportselectdailyReportdatadailyReportDailyReport"),
        icon=getattr(ft.Icons, "SUMMARIZE", ft.Icons.DESCRIPTION),
        initially_expanded=False,
        content_controls=[
            ft.Text(t("components:user_config._daily_report.configurationtypeconfigurationconfigurationDailyReportconfigurationdataconfigura"), size=12, color=theme.TEXT_SECONDARY),
            theme.module_card([material_box], label=t("components:user_config._daily_report.materialStatisticsConfiguration")),
            formula_hint,
            theme.module_card([formula_column], label=t("components:user_config._daily_report.delayIdleTimeAndUtilizationFormulas")),
            action_row,
            status_text,
        ],
    )
    _reload()
    return card, {"reload": _reload, "validate": _validate, "save": _save, "reset": _reset}
