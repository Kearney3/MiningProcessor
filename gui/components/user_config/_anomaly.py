"""异常值检测配置区域组件。"""
import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from gui.components.common import _log_message, safe_update


def _create_anomaly_config_section(page: ft.Page, log):
    """创建异常值检测配置卡片，返回 (card, refs_dict)。"""

    from func.anomaly.rules import ALL_NUMERIC_SENTINEL, DEFAULT_THRESHOLDS

    # 数据类型选项
    _DATA_TYPE_OPTIONS = [
        ("fuel", "油耗"),
        ("fuel_engine", "发动机"),
        ("production_running", "运行数据"),
        ("production", "生产数据"),
        ("electrical", "电力消耗"),
        ("worktime", "工时数据"),
    ]

    # 当前选中的数据类型
    _current_type = ["fuel"]

    # 每个数据类型的阈值行：{data_type: [[col, min, max, default], ...]}
    _threshold_rows: dict[str, list[list[str]]] = {}

    # 全局统计参数
    sigma_field = ft.TextField(
        label="σ 倍数", value="3.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text="默认 3.0",
    )
    pct_low_field = ft.TextField(
        label="百分位下限", value="1.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text="默认 1.0",
    )
    pct_high_field = ft.TextField(
        label="百分位上限", value="99.0", width=120,
        text_size=13, color=theme.TEXT_PRIMARY,
        hint_text="默认 99.0",
    )

    # 检测方法开关
    use_threshold_toggle = ft.Checkbox(
        label="绝对阈值检测", value=True,
        tooltip="基于用户配置的 min/max 范围检测",
    )
    use_sigma_toggle = ft.Checkbox(
        label="σ 异常检测", value=True,
        tooltip="基于标准差的统计离群检测",
    )
    use_percentile_toggle = ft.Checkbox(
        label="百分位检测", value=True,
        tooltip="基于百分位数的极端值检测",
    )

    # --- 逐列检测开关（持久化到用户配置） ---
    _COLUMN_LABELS: dict[str, str] = {
        "fuel": "油耗", "fuel_engine": "发动机",
        "production_running": "运行", "production": "生产",
        "electrical": "电力", "worktime": "工时",
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
                label = "全部数值列" if col == "__all_numeric__" else col
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
                ft.Text("列名 / 标记", expand=True, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("最小值", width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("最大值", width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("默认值", width=100, size=12,
                        weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY,
                        tooltip="处理异常值时的替换值"),
                ft.Text("", width=40),
            ],
            spacing=4,
        ))

        for i in range(len(rows)):
            idx = i

            col_field = ft.TextField(
                value=rows[idx][0], expand=True, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="列名或 __all_numeric__",
            )
            min_field = ft.TextField(
                value=rows[idx][1], width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="无下限",
            )
            max_field = ft.TextField(
                value=rows[idx][2], width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="无上限",
            )
            default_field = ft.TextField(
                value=rows[idx][3] if len(rows[idx]) > 3 else "",
                width=100, text_size=13, dense=True,
                color=theme.TEXT_PRIMARY, border_color=theme.BORDER,
                hint_text="0",
                tooltip="选择「处理异常值」时替换为此值",
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
                icon=ft.Icons.DELETE_OUTLINE, tooltip="删除",
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
        status_text.value = "异常值检测配置已保存"
        _log_message(log, "已保存异常值检测配置")
        safe_update(status_text)

    def _reset(_e=None):
        """恢复默认值。"""
        from func.config_loader import DEFAULT_ANOMALY_DETECTION
        config_loader.save_anomaly_detection_config(dict(DEFAULT_ANOMALY_DETECTION))
        _reload()
        status_text.value = "已恢复默认配置"
        _log_message(log, "已恢复异常值检测默认配置")
        safe_update(status_text)

    action_buttons = [
        theme.primary_btn("保存配置", icon=ft.Icons.SAVE, on_click=_collect_and_save),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset),
        theme.accent_btn("添加阈值", icon=ft.Icons.ADD, on_click=_add_row),
    ]

    card = theme.make_collapsible(
        title="异常值检测配置",
        subtitle="配置各数据类型的检测阈值、σ 倍数和百分位范围",
        icon=ft.Icons.TUNE,
        initially_expanded=False,
        content_controls=[
            ft.Text(
                "检测方法：选择启用的检测策略，关闭的策略不会应用。\n"
                "阈值规则对指定列名设置 min/max 范围；"
                f"使用 {ALL_NUMERIC_SENTINEL} 可对所有数值列统一检测。"
                "默认值列仅在启用「处理异常值」模式时生效。",
                size=12, color=theme.TEXT_SECONDARY,
            ),
            ft.Row([use_threshold_toggle, use_sigma_toggle, use_percentile_toggle], spacing=16),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("统计参数", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.Row([sigma_field, pct_low_field, pct_high_field], spacing=12),
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("数据类型", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            type_segment,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("逐列检测开关", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
            ft.Text(
                "关闭某列的开关后，该列将不参与任何异常检测（阈值、σ、百分位均跳过）。",
                size=11, color=theme.TEXT_SECONDARY,
            ),
            column_toggle_area,
            ft.Divider(height=1, color=theme.BORDER),
            ft.Text("阈值配置", size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
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
