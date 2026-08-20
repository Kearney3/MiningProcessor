"""MineBase 列映射配置区域组件。"""
import logging

import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func.config_loader import get_minebase_column_mapping, reset_minebase_column_mapping, save_minebase_column_mapping
from gui.components.common import _log_message
from gui.i18n import t


def _create_column_mapping_section(page: ft.Page, log):
    """创建 MineBase 列映射配置卡片，返回 (card, refs_dict)。"""

    _mapping_state: dict[str, dict[str, str]] = {}  # {data_type: {src: dst}}
    _mapping_data_types = ["work_efficiency", "fuel_consumption", "electricity_consumption", "equipment_operation", "production_record"]
    _mapping_type_labels = {
        "work_efficiency": t("components:user_config._column_mapping.worktimeEfficiency"),
        "fuel_consumption": t("components:user_config._column_mapping.fuelConsumption"),
        "electricity_consumption": t("components:user_config._column_mapping.electricalConsumption"),
        "equipment_operation": t("components:user_config._column_mapping.equipmentOperation"),
        "production_record": t("components:user_config._column_mapping.productionData"),
    }
    # 每种数据类型对应的 MineBase 目标字段选项（camelCase API 字段名）
    _MINEBASE_FIELD_OPTIONS: dict[str, list[str]] = {
        "work_efficiency": [
            "equipmentName", "equipmentCode", "company", "plannedMinutes", "plannedHours",
            "parkShift", "transfer", "auxiliaryWork", "waitingLoad", "blasting",
            "mealBreak", "refueling", "plannedMaintenance", "unplannedFault", "standby",
            "weatherSnow", "weatherDust", "fillWater", "totalProductionMinutes",
            "powerIssuePlanned", "powerIssueUnplanned", "totalProductionHours", "remark",
        ],
        "fuel_consumption": [
            "date", "shiftType", "equipmentName", "equipmentCode", "fuelName", "consumption",
        ],
        "electricity_consumption": [
            "date", "shiftType", "equipmentName", "consumption",
        ],
        "equipment_operation": [
            "date", "shiftType", "equipmentName", "company",
            "engineHoursStart", "engineHoursEnd", "runningHours",
            "milemeterStart", "milemeterEnd", "mileage", "tripCount",
        ],
        "production_record": [
            "date", "shiftType", "truckName", "excavatorName",
            "materialTypeName", "tripCount", "production",
        ],
    }
    _current_mapping_type = [_mapping_data_types[0]]

    # 每个数据类型维护一个 [(src, dst), ...] 列表，用索引做闭包引用
    _mapping_rows: dict[str, list[list[str]]] = {}

    mapping_type_dropdown = ft.Dropdown(
        label=t("components:user_config._column_mapping.dataType"),
        width=180,
        options=[ft.dropdown.Option(key=k, text=_mapping_type_labels.get(k, k)) for k in _mapping_data_types],
        value=_mapping_data_types[0],
    )
    mapping_rows_column = ft.Column(spacing=4, expand=True)
    mapping_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _sync_state_from_rows():
        """将当前行列表同步回 _mapping_state（保存前调用）。"""
        for dt, rows in _mapping_rows.items():
            state = {}
            for r in rows:
                if r[0].strip():
                    state[r[0]] = _SKIP if (len(r) > 2 and r[2]) else r[1]
            _mapping_state[dt] = state

    _SKIP = "__SKIP__"

    def _build_mapping_rows():
        controls = []
        dt = _current_mapping_type[0]
        rows = _mapping_rows.get(dt, [])

        # 表头
        controls.append(ft.Row(
            [
                ft.Text("", width=40),
                ft.Text(t("components:user_config._column_mapping.sourceColumnExcelColumn"), expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text(t("components:user_config._column_mapping.targetFieldMinebase"), expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("", width=40),
            ],
            spacing=4,
        ))

        for i in range(len(rows)):
            is_excluded = (rows[i][1] == _SKIP)

            src_field = ft.TextField(
                value=rows[i][0], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER, focused_border_color=theme.PRIMARY,
            )
            dst_field = ft.TextField(
                value="" if is_excluded else rows[i][1], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER, focused_border_color=theme.PRIMARY,
                disabled=is_excluded,
            )

            def _on_menu_select(e, _field=dst_field, _idx=i):
                val = e.control.content.value
                _field.value = val
                _field.update()
                rows[_idx][1] = val

            options = _MINEBASE_FIELD_OPTIONS.get(dt, [])
            dst_menu = ft.PopupMenuButton(
                icon=ft.Icons.ARROW_DROP_DOWN,
                tooltip=t("components:user_config._column_mapping.selectTargetField"),
                icon_size=20,
                disabled=is_excluded,
                items=[
                    ft.PopupMenuItem(content=ft.Text(v), on_click=_on_menu_select) for v in options
                ],
            )
            remove_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip=t("components:user_config._column_mapping.delete"), icon_size=18, icon_color=theme.ERROR)

            exclude_cb = ft.Checkbox(
                value=is_excluded,
                tooltip=t("components:user_config._column_mapping.excludeThisColumnDoNotImport"),
                active_color=theme.WARNING,
            )

            def _on_exclude_change(e, _idx=i, _dst=dst_field, _menu=dst_menu):
                excluded = e.control.value
                if excluded:
                    rows[_idx][1] = _SKIP
                    _dst.value = ""
                    _dst.disabled = True
                    _menu.disabled = True
                else:
                    rows[_idx][1] = ""
                    _dst.disabled = False
                    _menu.disabled = False
                _dst.update()
                _menu.update()

            def _on_src_change(e, _idx=i):
                rows[_idx][0] = e.control.value.strip()

            def _on_dst_change(e, _idx=i):
                rows[_idx][1] = e.control.value.strip()

            def _on_remove(e, _idx=i):
                rows.pop(_idx)
                _build_mapping_rows()

            exclude_cb.on_change = _on_exclude_change
            src_field.on_change = _on_src_change
            dst_field.on_change = _on_dst_change
            remove_btn.on_click = _on_remove

            controls.append(ft.Row([exclude_cb, src_field, dst_field, dst_menu, remove_btn], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        mapping_rows_column.controls = controls
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_mapping_type_change(e):
        _current_mapping_type[0] = mapping_type_dropdown.value
        _build_mapping_rows()

    mapping_type_dropdown.on_select = _on_mapping_type_change

    def _add_mapping_row(e=None):
        dt = _current_mapping_type[0]
        if dt not in _mapping_rows:
            _mapping_rows[dt] = []
        _mapping_rows[dt].append(["", "", False])
        _build_mapping_rows()

    def _reload_mapping():
        _mapping_state.clear()
        _mapping_rows.clear()
        data = get_minebase_column_mapping()
        for dt in _mapping_data_types:
            if dt in data:
                _mapping_state[dt] = dict(data[dt])
        # 从 _mapping_state 初始化行列表
        for dt in _mapping_data_types:
            entries = _mapping_state.get(dt, {})
            _mapping_rows[dt] = [[k, v, v == _SKIP] for k, v in entries.items()]
        mapping_status_text.value = ""

    def _save_mapping(e=None):
        # 从行列表同步到 state，清理空键
        _sync_state_from_rows()
        for dt in _mapping_state:
            _mapping_state[dt] = {k: v for k, v in _mapping_state[dt].items() if k.strip()}

        try:
            save_minebase_column_mapping(dict(_mapping_state))
        except Exception as ex:
            mapping_status_text.value = t("components:user_config._column_mapping.saveFailed", ex=ex)
            mapping_status_text.color = theme.ERROR
            _log_message(log, t("components:user_config._column_mapping.saveconfigurationconfigurationfailed", ex=ex), level=logging.ERROR)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return

        total = sum(len(v) for v in _mapping_state.values())
        mapping_status_text.value = t("components:user_config._column_mapping.savedItemscolumnMapping", total=total)
        mapping_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, t("components:user_config._column_mapping.savedconfigurationconfigurationItems", total=total))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_mapping(e=None):
        reset_minebase_column_mapping()
        _reload_mapping()
        mapping_status_text.value = t("components:user_config._column_mapping.defaultMappingRestored")
        mapping_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, t("components:user_config._column_mapping.configurationdefaultconfigurationconfiguration"))
        _build_mapping_rows()
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    mapping_action_buttons = [
        theme.primary_btn(t("components:user_config._column_mapping.saveMapping"), icon=ft.Icons.SAVE, on_click=_save_mapping),
        theme.secondary_btn(t("components:user_config._column_mapping.reload"), icon=ft.Icons.REFRESH, on_click=lambda _: (_reload_mapping(), _build_mapping_rows())),
        theme.secondary_btn(t("components:user_config._column_mapping.restoreDefault"), icon=ft.Icons.RESTART_ALT, on_click=_reset_mapping),
        theme.accent_btn(t("components:user_config._column_mapping.addMapping"), icon=ft.Icons.ADD, on_click=_add_mapping_row),
    ]

    mapping_card = theme.make_collapsible(
        title=t("components:user_config._column_mapping.minebaseConfigurationconfiguration"),
        subtitle=t("components:user_config._column_mapping.configurationMiningprocessorOutputconfigurationMinebaseConfiguration"),
        icon=ft.Icons.MAP,
        initially_expanded=False,
        content_controls=[
            mapping_type_dropdown,
            mapping_rows_column,
            ft.Row(mapping_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            mapping_status_text,
        ],
    )

    return mapping_card, {"reload": _reload_mapping, "build": _build_mapping_rows}
