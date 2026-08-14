"""异常值检测配置区域组件。"""
import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from gui.components.common import _log_message, safe_update
from gui.i18n import t


def _create_anomaly_config_section(page: ft.Page, log):
    """创建异常值检测配置卡片，返回 (card, refs_dict)。"""

    from func.anomaly.rules import ALL_NUMERIC_SENTINEL, DEFAULT_THRESHOLDS

    # 数据类型选项
    _DATA_TYPE_OPTIONS = [
        ("fuel", t("components:user_config._anomaly.油耗_75d6")),
        ("fuel_engine", t("components:user_config._anomaly.发动机_9a82")),
        ("production_running", t("components:user_config._anomaly.运行数据_6644")),
        ("production", t("components:user_config._anomaly.生产数据_9fb6")),
        ("electrical", t("components:user_config._anomaly.电力消耗_79c4")),
        ("worktime", t("components:user_config._anomaly.工时数据_8c32")),
    ]

    # 当前选中的数据类型
    _current_type = ["fuel"]

    # 每个数据类型的阈值行：{data_type: [[col, min, max, default], ...]}
    _threshold_rows: dict[str, list[list[str]]] = {}

    # 全局统计参数
    sigma_field = ft.TextField(
        label=t("components:user_config._anomaly.σ倍数_c60a"), value="3.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text=t("components:user_config._anomaly.默认3.0_f9fb"),
    )
    pct_low_field = ft.TextField(
        label=t("components:user_config._anomaly.百分位下限_d760"), value="1.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text=t("components:user_config._anomaly.默认1.0_e719"),
    )
    pct_high_field = ft.TextField(
        label=t("components:user_config._anomaly.百分位上限_2563"), value="99.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text=t("components:user_config._anomaly.默认99.0_8254"),
    )

    # 检测方法开关
    use_threshold_toggle = ft.Checkbox(
        label=t("components:user_config._anomaly.绝对阈值检测_5c7a"), value=True,
        tooltip=t("components:user_config._anomaly.基于用户配置的min/max范_0313"),
    )
    use_sigma_toggle = ft.Checkbox(
        label=t("components:user_config._anomaly.σ异常检测_bef4"), value=True,
        tooltip=t("components:user_config._anomaly.基于标准差的统计离群检测_5a35"),
    )
    use_percentile_toggle = ft.Checkbox(
        label=t("components:user_config._anomaly.百分位检测_2031"), value=True,
        tooltip=t("components:user_config._anomaly.基于百分位数的极端值检测_8532"),
    )

    # --- 逐列检测开关（持久化到用户配置） ---
    _COLUMN_LABELS: dict[str, str] = {
        "fuel": t("components:user_config._anomaly.油耗_75d6"), "fuel_engine": t("components:user_config._anomaly.发动机_9a82"),
        "production_running": t("components:user_config._anomaly.运行_4c76"), "production": t("components:user_config._anomaly.生产_ac45"),
        "electrical": t("components:user_config._anomaly.电力_3f2a"), "worktime": t("components:user_config._anomaly.工时_e8c0"),
    }
    _COLUMN_DEFS: dict[str, dict[str, list[str]]] = {
        "fuel": {"threshold": ["油品消耗"], "statistical": ["油品消耗"]},
        "fuel_engine": {"threshold": ["发动机小时数开始", "发动机小时数结束", "运行小时数"], "statistical": ["运行小时数"]},
        "production_running": {"threshold": ["运行里程", "运行小时数", "趟次"], "statistical": ["运行里程", "运行小时数", "趟次"]},
        "production": {"threshold": ["趟次", "产量"], "statistical": ["趟次", "产量"]},
        "electrical": {"threshold": ["电力消耗"], "statistical": ["电力消耗"]},
        "worktime": {"threshold": ["__all_numeric__"], "statistical": []},
    }
    column_toggles: dict[str, ft.Checkbox] = {}  # key: "dtype:col"
    column_toggle_rows: dict[str, ft.Row] = {}

    def _build_column_toggles():
        """构建逐列开关 UI。"""
        for dtype in _COLUMN_LABELS:
            cols_cfg = _COLUMN_DEFS.get(dtype, {})
            all_cols = sorted(set(cols_cfg.get("threshold", []) + cols_cfg.get("statistical", [])))
            if not all_cols:
                continue
            cbs: list[ft.Control] = []
            for col in all_cols:
                key = f"{dtype}:{col}"
                label = t("components:user_config._anomaly.全部数值列_d28d") if col == "__all_numeric__" else col
                cb = ft.Checkbox(
                    label=label,
                    value=True,
                    visual_density=ft.VisualDensity.COMPACT,
                )
                column_toggles[key] = cb
                cbs.append(
                    ft.Container(
                        content=cb,
                        width=190 if len(label) >= 7 else 140,
                    )
                )
            column_toggle_rows[dtype] = ft.Row(
                cbs,
                wrap=True,
                spacing=8,
                run_spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

    column_toggle_area = ft.Column(spacing=4)
    _build_column_toggles()

    def _show_column_toggles(data_type: str):
        selected_row = column_toggle_rows.get(data_type)
        column_toggle_area.controls = [selected_row] if selected_row else []
        safe_update(column_toggle_area)

    _show_column_toggles(_current_type[0])

    type_segment = ft.SegmentedButton(
        selected=[_current_type[0]],
        segments=[
            ft.Segment(value=key, label=ft.Text(_COLUMN_LABELS[key]))
            for key, _ in _DATA_TYPE_OPTIONS
        ],
        allow_empty_selection=False,
        show_selected_icon=False,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_500),
        ),
    )
    rows_column = ft.Column(spacing=4, expand=True)
    status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _build_rows():
        """根据当前数据类型构建阈值编辑行。"""
        controls = []
        dt = _current_type[0]
        rows = _threshold_rows.get(dt, [])

        # 表头
        controls.append(ft.Row(
            [
                ft.Text(t("components:user_config._anomaly.列名/标记_93eb"), expand=True, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text(t("components:user_config._anomaly.最小值_c322"), width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text(t("components:user_config._anomaly.最大值_5da8"), width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text(t("components:user_config._anomaly.默认值_225f"), width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY,
                        tooltip=t("components:user_config._anomaly.处理异常值时的替换值_27f2")),
                ft.Text("", width=40),
            ],
            spacing=4,
        ))

        for i in range(len(rows)):
            idx = i

            col_field = ft.TextField(
                value=rows[idx][0], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text=t("components:user_config._anomaly.列名或__all_numeri_79fb"),
            )
            min_field = ft.TextField(
                value=rows[idx][1], width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text=t("components:user_config._anomaly.无下限_3696"),
            )
            max_field = ft.TextField(
                value=rows[idx][2], width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text=t("components:user_config._anomaly.无上限_1891"),
            )
            default_field = ft.TextField(
                value=rows[idx][3] if len(rows[idx]) > 3 else "",
                width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="0",
                tooltip=t("components:user_config._anomaly.选择「处理异常值」时替换为此值_2288"),
            )

            def _on_col_change(e, _idx=idx):
                rows[_idx][0] = e.control.value.strip()

            def _on_min_change(e, _idx=idx):
                rows[_idx][1] = e.control.value.strip()

            def _on_max_change(e, _idx=idx):
                rows[_idx][2] = e.control.value.strip()

            def _on_default_change(e, _idx=idx):
                rows[_idx][3] = e.control.value.strip()

            def _on_remove(e, _idx=idx):
                rows.pop(_idx)
                _build_rows()

            col_field.on_change = _on_col_change
            min_field.on_change = _on_min_change
            max_field.on_change = _on_max_change
            default_field.on_change = _on_default_change
            remove_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, tooltip=t("components:user_config._anomaly.删除_2f4a"),
                icon_size=18, icon_color=theme.ERROR, on_click=_on_remove,
            )

            controls.append(ft.Row(
                [col_field, min_field, max_field, default_field, remove_btn],
                spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ))

        rows_column.controls = controls
        safe_update(rows_column)

    def _on_type_change(e):
        selected_values = e.control.selected
        if not selected_values:
            return
        _current_type[0] = selected_values[0]
        _show_column_toggles(_current_type[0])
        _build_rows()

    type_segment.on_change = _on_type_change

    def _add_row(e=None):
        dt = _current_type[0]
        if dt not in _threshold_rows:
            _threshold_rows[dt] = []
        _threshold_rows[dt].append(["", "", "", ""])
        _build_rows()

    def _reload():
        """从配置文件加载。"""
        ad = config_loader.get_anomaly_detection_config()

        # 加载阈值 + 处理规则
        _threshold_rows.clear()
        thresholds = ad.get("thresholds", {})
        handling = ad.get("handling_rules", {})
        for dt, _ in _DATA_TYPE_OPTIONS:
            dt_thresholds = thresholds.get(dt, {})
            dt_handling = handling.get(dt, {})
            rows = []
            for col, bounds in dt_thresholds.items():
                rule = dt_handling.get(col, {})
                default_val = str(rule.get("default", "")) if rule.get("strategy") == "default_value" else ""
                rows.append([
                    col,
                    str(bounds.get("min", "")) if "min" in bounds else "",
                    str(bounds.get("max", "")) if "max" in bounds else "",
                    default_val,
                ])
            _threshold_rows[dt] = rows

        # 加载统计参数
        sigma_field.value = str(ad.get("sigma_n", 3.0))
        pct_low_field.value = str(ad.get("percentile_low", 1.0))
        pct_high_field.value = str(ad.get("percentile_high", 99.0))

        # 加载检测方法开关
        use_threshold_toggle.value = ad.get("use_threshold", True)
        use_sigma_toggle.value = ad.get("use_sigma", True)
        use_percentile_toggle.value = ad.get("use_percentile", True)

        # 加载逐列检测开关
        thresholds_data = ad.get("thresholds", {})
        stat_data = ad.get("statistical_columns", {})
        for key, cb in column_toggles.items():
            dtype, col = key.split(":", 1)
            t_cfg = thresholds_data.get(dtype, {}).get(col, {})
            s_cfg = stat_data.get(dtype, {}).get(col, {})
            t_enabled = t_cfg.get("enabled", True) if isinstance(t_cfg, dict) else True
            s_enabled = s_cfg.get("enabled", True) if isinstance(s_cfg, dict) else True
            cb.value = t_enabled and s_enabled

        status_text.value = ""
        type_segment.selected = [_current_type[0]]
        _show_column_toggles(_current_type[0])
        _build_rows()
        safe_update(sigma_field)
        safe_update(pct_low_field)
        safe_update(pct_high_field)
        safe_update(use_threshold_toggle)
        safe_update(use_sigma_toggle)
        safe_update(use_percentile_toggle)
        safe_update(type_segment)
        for cb in column_toggles.values():
            safe_update(cb)

    def _collect_and_save(_e=None):
        """收集 UI 值并保存。"""
        # 收集阈值 + 处理规则
        thresholds = {}
        handling_rules = {}
        for dt, rows in _threshold_rows.items():
            dt_thresholds = {}
            dt_handling = {}
            for r in rows:
                col = r[0].strip()
                if not col:
                    continue
                # 阈值
                bounds = {}
                if r[1].strip():
                    try:
                        bounds["min"] = float(r[1])
                    except ValueError:
                        pass
                if r[2].strip():
                    try:
                        bounds["max"] = float(r[2])
                    except ValueError:
                        pass
                if bounds:
                    dt_thresholds[col] = bounds
                # 默认值（处理异常值时替换用）
                if len(r) > 3 and r[3].strip():
                    try:
                        dt_handling[col] = {"strategy": "default_value", "default": float(r[3])}
                    except ValueError:
                        dt_handling[col] = {"strategy": "default_value", "default": 0}
            if dt_thresholds:
                thresholds[dt] = dt_thresholds
            if dt_handling:
                handling_rules[dt] = dt_handling

        # 收集统计参数
        try:
            sigma_n = float(sigma_field.value or "3.0")
        except ValueError:
            sigma_n = 3.0
        try:
            pct_low = float(pct_low_field.value or "1.0")
        except ValueError:
            pct_low = 1.0
        try:
            pct_high = float(pct_high_field.value or "99.0")
        except ValueError:
            pct_high = 99.0

        updates = {
            "thresholds": thresholds,
            "handling_rules": handling_rules,
            "sigma_n": sigma_n,
            "percentile_low": pct_low,
            "percentile_high": pct_high,
            "use_threshold": use_threshold_toggle.value,
            "use_sigma": use_sigma_toggle.value,
            "use_percentile": use_percentile_toggle.value,
        }

        # 合并逐列检测开关到 thresholds 和 statistical_columns
        thresholds_out = updates["thresholds"]
        stat_cols_out: dict[str, dict] = {}
        for key, cb in column_toggles.items():
            dtype, col = key.split(":", 1)
            val = cb.value
            # thresholds 中标记 enabled
            if dtype in thresholds_out and col in thresholds_out[dtype]:
                thresholds_out[dtype][col] = {**thresholds_out[dtype][col], "enabled": val}
            elif val is False:
                # 列不在阈值表但被关闭，需记录
                thresholds_out.setdefault(dtype, {})[col] = {"enabled": False}
            # statistical_columns 中标记 enabled
            stat_cols_out.setdefault(dtype, {})[col] = {"enabled": val}
        updates["thresholds"] = thresholds_out
        updates["statistical_columns"] = stat_cols_out
        config_loader.update_anomaly_detection_config(updates)
        status_text.value = t("components:user_config._anomaly.异常值检测配置已保存_4f21")
        _log_message(log, t("components:user_config._anomaly.已保存异常值检测配置_8970"))
        safe_update(status_text)

    def _reset(_e=None):
        """恢复默认值。"""
        from func.config_loader import DEFAULT_ANOMALY_DETECTION
        config_loader.save_anomaly_detection_config(dict(DEFAULT_ANOMALY_DETECTION))
        _reload()
        status_text.value = t("components:user_config._anomaly.已恢复默认配置_455f")
        _log_message(log, t("components:user_config._anomaly.已恢复异常值检测默认配置_af9e"))
        safe_update(status_text)

    action_buttons = [
        theme.primary_btn(t("components:user_config._anomaly.保存配置_ed75"), icon=ft.Icons.SAVE, on_click=_collect_and_save),
        theme.secondary_btn(t("components:user_config._anomaly.重新加载_64ca"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload()),
        theme.secondary_btn(t("components:user_config._anomaly.恢复默认_7468"), icon=ft.Icons.RESTART_ALT, on_click=_reset),
        theme.accent_btn(t("components:user_config._anomaly.添加阈值_a2ce"), icon=ft.Icons.ADD, on_click=_add_row),
    ]

    card = theme.make_collapsible(
        title=t("components:user_config._anomaly.异常值检测配置_5f46"),
        subtitle=t("components:user_config._anomaly.配置各数据类型的检测阈值、σ倍_3096"),
        icon=ft.Icons.TUNE,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                t("components:user_config._anomaly.检测方法：选择启用的检测策略，_69b0")
                + t("components:user_config._anomaly.阈值规则对指定列名设置min/_8569")
                + f"使用 {ALL_NUMERIC_SENTINEL} 可对所有数值列统一检测。"
                + t("components:user_config._anomaly.默认值列仅在启用「处理异常值」_0d3b"),
                size=12, color=theme.TEXT_SECONDARY,
            ),
            ft.Row([use_threshold_toggle, use_sigma_toggle, use_percentile_toggle], spacing=16),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text(t("components:user_config._anomaly.统计参数_4f03"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.Row([sigma_field, pct_low_field, pct_high_field], spacing=12),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text(t("components:user_config._anomaly.数据类型_185f"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            type_segment,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text(t("components:user_config._anomaly.逐列检测开关_96dd"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.Text(
                t("components:user_config._anomaly.关闭某列的开关后，该列将不参与_c673"),
                size=11, color=theme.TEXT_SECONDARY,
            ),
            column_toggle_area,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text(t("components:user_config._anomaly.阈值配置_35a3"), size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            rows_column,
            ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            status_text,
        ],
    )

    return card, {
        "reload": _reload,
        "type_segment": type_segment,
        "column_toggle_area": column_toggle_area,
        "column_toggle_rows": column_toggle_rows,
        "rows_column": rows_column,
    }
