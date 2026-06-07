"""用户自定义配置区域组件（优化后的表单布局与错误处理）"""
import logging
import re

import flet as ft

from .types import UserConfigRefs

try:
    from . import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from func.config_loader import DEFAULT_FILE_KEYWORDS, get_minebase_column_mapping, save_minebase_column_mapping, reset_minebase_column_mapping, get_minebase_config_default
from .common import _log_message


def _sync_port_state(port_field: ft.TextField, is_valid: bool, message: str = ""):
    """统一端口字段的边框和提示状态。"""
    port_field.border_color = ft.Colors.RED if not is_valid else theme.BORDER
    port_field.error_text = message or None
    try:
        port_field.update()
    except (RuntimeError, AttributeError):
        pass


def _normalize_port_text(value: str | None) -> str:
    return re.sub(r"\D+", "", (value or "").strip())


# ---------------------------------------------------------------------------
# 1. 文件关键字配置
# ---------------------------------------------------------------------------

def _create_keywords_section(page: ft.Page, log):
    """创建文件关键字配置卡片，返回 (card, refs_dict)。"""

    kw_fuel = ft.TextField(label="燃油数据", hint_text="例如: 设备柴油消耗,Техник", expand=True, color=theme.TEXT_PRIMARY)
    kw_electrical = ft.TextField(label="电力数据", hint_text="例如: Electrical", expand=True, color=theme.TEXT_PRIMARY)
    kw_production = ft.TextField(label="生产数据", hint_text="例如: 白班,夜班", expand=True, color=theme.TEXT_PRIMARY)
    kw_worktime = ft.TextField(label="工时数据", hint_text="例如: 工时", expand=True, color=theme.TEXT_PRIMARY)
    kw_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _kw_defaults() -> dict[str, str]:
        return {k: ",".join(v) for k, v in DEFAULT_FILE_KEYWORDS.items()}

    def _apply_kw_to_ui(kw: dict[str, list[str]]):
        kw_fuel.value = ",".join(kw.get("fuel", []))
        kw_electrical.value = ",".join(kw.get("electrical", []))
        kw_production.value = ",".join(kw.get("production", []))
        kw_worktime.value = ",".join(kw.get("worktime", []))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _collect_kw_from_ui() -> dict[str, list[str]]:
        def _split(text: str) -> list[str]:
            return [s.strip() for s in (text or "").split(",") if s.strip()]
        return {
            "fuel": _split(kw_fuel.value),
            "electrical": _split(kw_electrical.value),
            "production": _split(kw_production.value),
            "worktime": _split(kw_worktime.value),
        }

    def _reload_keywords():
        saved = config_loader.get_user_config("file_keywords", None)
        if saved and isinstance(saved, dict):
            merged = dict(DEFAULT_FILE_KEYWORDS)
            for k, v in saved.items():
                if isinstance(v, list):
                    merged[k] = v
            _apply_kw_to_ui(merged)
        else:
            _apply_kw_to_ui(DEFAULT_FILE_KEYWORDS)
        kw_status_text.value = ""

    def save_keywords(_e):
        kw = _collect_kw_from_ui()
        config_loader.update_user_config({"file_keywords": kw})
        kw_status_text.value = "文件关键字配置已保存"
        _log_message(log, "已保存文件关键字配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def reset_keywords(_e):
        config_loader.update_user_config({"file_keywords": dict(DEFAULT_FILE_KEYWORDS)})
        _apply_kw_to_ui(DEFAULT_FILE_KEYWORDS)
        kw_status_text.value = "已恢复默认关键字"
        _log_message(log, "已恢复默认文件关键字配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    kw_action_buttons = [
        theme.primary_btn("保存关键字", icon=ft.Icons.SAVE, on_click=save_keywords),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_keywords()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=reset_keywords),
    ]

    keywords_card = theme.make_collapsible(
        title="文件关键字配置",
        subtitle="用于批量处理时自动识别文件夹中的数据文件",
        icon=ft.Icons.KEY,
        content_controls=[
            ft.Text(
                "所有类型均按文件名关键字匹配，Sheet 级别识别由各处理器内部完成。多个关键字用英文逗号分隔。",
                size=12,
                color=theme.TEXT_SECONDARY,
            ),
            kw_fuel,
            kw_electrical,
            kw_production,
            kw_worktime,
            ft.Row(kw_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            kw_status_text,
        ],
    )

    return keywords_card, {"reload": _reload_keywords, "save": save_keywords, "reset": reset_keywords}


# ---------------------------------------------------------------------------
# 2. 工作效率表头映射配置
# ---------------------------------------------------------------------------

def _create_header_mapping_section(page: ft.Page, log):
    """创建工作效率表头映射配置卡片，返回 (card, refs_dict)。"""

    _header_mapping_state: list[dict] = []  # [{index: int|None, original: str, new: str}, ...]

    header_rows_column = ft.Column(spacing=4, expand=True)
    header_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    # ── 行构建 ──
    def _build_header_rows():
        controls = []

        # 表头行
        header_labels = ft.Row(
            [
                ft.Text("列号", width=80, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("原始列名", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("匹配列名", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("", width=40),
            ],
            spacing=4,
        )
        controls.append(header_labels)

        for i, entry in enumerate(_header_mapping_state):
            idx = i

            index_field = ft.TextField(
                value=str(entry.get("index", "")) if entry.get("index") is not None else "",
                hint_text="从1起",
                width=80,
                text_size=13,
                dense=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
                border_color=theme.BORDER,
                focused_border_color=theme.PRIMARY,
                input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"),
            )
            orig_field = ft.TextField(
                value=entry.get("original", ""),
                hint_text="原始列名",
                expand=True,
                text_size=13,
                dense=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
                border_color=theme.BORDER,
                focused_border_color=theme.PRIMARY,
            )
            new_field = ft.TextField(
                value=entry.get("new", ""),
                hint_text="匹配列名",
                expand=True,
                text_size=13,
                dense=True,
                color=theme.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=theme.TEXT_SECONDARY, size=12),
                border_color=theme.BORDER,
                focused_border_color=theme.PRIMARY,
            )
            remove_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                tooltip="删除此行",
                icon_size=18,
                icon_color=theme.ERROR,
            )

            def _on_index_change(e, _idx=idx):
                val = e.control.value.strip()
                _header_mapping_state[_idx]["index"] = int(val) if val else None

            def _on_orig_change(e, _idx=idx):
                _header_mapping_state[_idx]["original"] = e.control.value

            def _on_new_change(e, _idx=idx):
                _header_mapping_state[_idx]["new"] = e.control.value

            def _on_remove(e, _idx=idx):
                _header_mapping_state.pop(_idx)
                _build_header_rows()

            index_field.on_change = _on_index_change
            orig_field.on_change = _on_orig_change
            new_field.on_change = _on_new_change
            remove_btn.on_click = _on_remove

            row = ft.Row(
                [index_field, orig_field, new_field, remove_btn],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            controls.append(row)

        header_rows_column.controls = controls
        try:
            header_rows_column.update()
        except (RuntimeError, AttributeError):
            pass

    def _add_header_row(e=None):
        _header_mapping_state.append({"index": None, "original": "", "new": ""})
        _build_header_rows()

    def _reload_header_mapping():
        _header_mapping_state.clear()
        config = config_loader.get_worktime_header_mapping()
        for entry in config.get("entries", []):
            _header_mapping_state.append(dict(entry))
        _build_header_rows()
        header_status_text.value = ""

    def _save_header_mapping(e=None):
        # 收集并验证
        entries = []
        indices_seen: dict[int, int] = {}  # index -> row number for error
        originals_seen: dict[str, int] = {}  # original -> row number for error
        has_error = False

        for i, pair in enumerate(_header_mapping_state):
            row_num = i + 1  # 1-based for display
            idx_raw = pair.get("index")
            orig = (pair.get("original") or "").strip()
            new_name = (pair.get("new") or "").strip()

            # 解析行号
            idx_val = None
            if idx_raw is not None:
                try:
                    idx_val = int(idx_raw)
                except (TypeError, ValueError):
                    idx_val = None

            # 跳过完全空行
            if idx_val is None and not orig and not new_name:
                continue

            # 匹配列名必填
            if not new_name:
                header_status_text.value = f"第 {row_num} 行：匹配列名不能为空"
                header_status_text.color = theme.ERROR
                has_error = True
                break

            # 去重检查：行号
            if idx_val is not None:
                if idx_val in indices_seen:
                    header_status_text.value = (
                        f"行号 {idx_val} 重复（第 {indices_seen[idx_val]} 行和第 {row_num} 行）"
                    )
                    header_status_text.color = theme.ERROR
                    has_error = True
                    break
                indices_seen[idx_val] = row_num

            # 去重检查：原始列名
            if orig:
                if orig in originals_seen:
                    header_status_text.value = (
                        f"原始列名「{orig}」重复（第 {originals_seen[orig]} 行和第 {row_num} 行）"
                    )
                    header_status_text.color = theme.ERROR
                    has_error = True
                    break
                originals_seen[orig] = row_num

            entries.append({"index": idx_val, "original": orig, "new": new_name})

        if has_error:
            _log_message(log, header_status_text.value, level=logging.WARNING)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return

        mapping_config = {
            "entries": entries,
        }
        config_loader.save_worktime_header_mapping(mapping_config)

        # 宽松提示：统计各条目适用模式
        pos_only = sum(1 for e in entries if e["index"] is not None and not e["original"])
        name_only = sum(1 for e in entries if e["index"] is None and e["original"])
        both = sum(1 for e in entries if e["index"] is not None and e["original"])
        hints = []
        if pos_only:
            hints.append(f"{pos_only} 条仅按位置有效")
        if name_only:
            hints.append(f"{name_only} 条仅按列名有效")
        if both:
            hints.append(f"{both} 条两种模式均有效")

        hint_text = "；".join(hints) if hints else ""
        status_msg = f"已保存 {len(entries)} 条表头映射"
        if hint_text:
            status_msg += f"（{hint_text}）"
        header_status_text.value = status_msg
        header_status_text.color = theme.WARNING if (pos_only or name_only) and not both else theme.TEXT_SECONDARY
        _log_message(log, f"已保存工作效率表头映射（{len(entries)} 条）")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_header_mapping(e=None):
        config_loader.save_worktime_header_mapping({"entries": config_loader.DEFAULT_WORKTIME_HEADER_MAPPING.get("entries", [])})
        _header_mapping_state.clear()
        # 重新加载默认值到状态
        for entry in config_loader.DEFAULT_WORKTIME_HEADER_MAPPING.get("entries", []):
            _header_mapping_state.append(dict(entry))
        _build_header_rows()
        header_status_text.value = "已恢复默认配置"
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已重置工作效率表头映射")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _clear_header_mapping(e=None):
        config_loader.save_worktime_header_mapping({"entries": []})
        _header_mapping_state.clear()
        _build_header_rows()
        header_status_text.value = "已清空配置"
        header_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已清空工作效率表头映射配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    header_action_buttons = [
        theme.primary_btn("保存映射", icon=ft.Icons.SAVE, on_click=_save_header_mapping),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_header_mapping()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_header_mapping),
        theme.secondary_btn("清空配置", icon=ft.Icons.DELETE_SWEEP, on_click=_clear_header_mapping),
        theme.accent_btn("添加映射", icon=ft.Icons.ADD, on_click=_add_header_row),
    ]

    header_mapping_card = theme.make_collapsible(
        title="工作效率表头映射配置",
        subtitle="配置行号/原始列名到新列名的映射关系",
        icon=ft.Icons.TABLE_CHART,
        initially_expanded=False,
        content_controls=[
            header_rows_column,
            ft.Row(header_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            header_status_text,
        ],
    )

    return header_mapping_card, {"reload": _reload_header_mapping}


# ---------------------------------------------------------------------------
# 3. MineBase 连接配置
# ---------------------------------------------------------------------------

def _create_minebase_section(page: ft.Page, log):
    """创建 MineBase 连接配置卡片，返回 (card, refs_dict)。"""

    mb_mode = ft.Dropdown(
        label="同步模式",
        width=200,
        options=[
            ft.dropdown.Option(key="api", text="API 模式"),
            ft.dropdown.Option(key="database", text="直连数据库"),
        ],
        value="api",
    )
    # API 配置
    mb_api_url = ft.TextField(label="API 地址", hint_text="http://localhost:3000", expand=True, color=theme.TEXT_PRIMARY)
    mb_api_user = ft.TextField(label="用户名", expand=True, color=theme.TEXT_PRIMARY)
    mb_api_pass = ft.TextField(label="密码", password=True, can_reveal_password=True, expand=True)
    # 数据库配置
    mb_db_host = ft.TextField(label="数据库主机", hint_text="localhost", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_port = ft.TextField(label="端口", value="5432", width=120, max_length=5,
                              input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"))
    mb_db_name = ft.TextField(label="数据库名", hint_text="minebase", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_user = ft.TextField(label="用户名", expand=True, color=theme.TEXT_PRIMARY)
    mb_db_pass = ft.TextField(label="密码", password=True, can_reveal_password=True, expand=True)
    mb_status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    # API / 数据库字段分组容器，按模式显示
    mb_api_fields = ft.Column(
        [mb_api_url, ft.Row([mb_api_user, mb_api_pass], spacing=8)],
        spacing=8,
    )
    mb_db_fields = ft.Column(
        [
            ft.Row([mb_db_host, mb_db_port], spacing=8),
            mb_db_name,
            ft.Row([mb_db_user, mb_db_pass], spacing=8),
        ],
        spacing=8,
    )

    def _toggle_mb_fields():
        is_api = mb_mode.value == "api"
        mb_api_fields.visible = is_api
        mb_db_fields.visible = not is_api
        try:
            mb_api_fields.update()
            mb_db_fields.update()
        except (RuntimeError, AttributeError):
            pass

    mb_mode.on_select = lambda _: _toggle_mb_fields()

    def _apply_mb_config(cfg: dict):
        mb_mode.value = cfg.get("mode", "api")
        api = cfg.get("api", {})
        mb_api_url.value = api.get("url", "")
        mb_api_user.value = api.get("username", "")
        mb_api_pass.value = api.get("password", "")
        db = cfg.get("database", {})
        mb_db_host.value = db.get("host", "")
        mb_db_port.value = str(db.get("port", 5432))
        mb_db_name.value = db.get("database", "")
        mb_db_user.value = db.get("user", "")
        mb_db_pass.value = db.get("password", "")
        _toggle_mb_fields()

    def _collect_mb_config() -> dict:
        return {
            "mode": mb_mode.value or "api",
            "api": {
                "url": (mb_api_url.value or "").strip(),
                "username": (mb_api_user.value or "").strip(),
                "password": mb_api_pass.value or "",
            },
            "database": {
                "host": (mb_db_host.value or "").strip() or "localhost",
                "port": int(_normalize_port_text(mb_db_port.value) or "5432"),
                "database": (mb_db_name.value or "").strip() or "minebase",
                "user": (mb_db_user.value or "").strip() or "postgres",
                "password": mb_db_pass.value or "",
            },
        }

    def _reload_mb_config():
        cfg = config_loader.get_minebase_config()
        _apply_mb_config(cfg)
        mb_status_text.value = ""

    def _save_mb_config(_e):
        port_val = int(_normalize_port_text(mb_db_port.value) or "5432")
        if port_val < 0 or port_val > 65535:
            _sync_port_state(mb_db_port, False, "端口必须在 0-65535 之间")
            _log_message(log, "保存 MineBase 配置失败：端口不合法", level=logging.WARNING)
            return
        _sync_port_state(mb_db_port, True)
        cfg = _collect_mb_config()
        config_loader.save_minebase_config(cfg)
        mb_status_text.value = "MineBase 连接配置已保存"
        _log_message(log, "已保存 MineBase 连接配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_mb_config(_e):
        defaults = get_minebase_config_default()
        config_loader.save_minebase_config(defaults)
        _apply_mb_config(defaults)
        mb_status_text.value = "已恢复默认配置"
        _log_message(log, "已恢复 MineBase 默认连接配置")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    mb_action_buttons = [
        theme.primary_btn("保存配置", icon=ft.Icons.SAVE, on_click=_save_mb_config),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: _reload_mb_config()),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_mb_config),
    ]

    minebase_card = theme.make_collapsible(
        title="数据库连接配置",
        subtitle="配置 MineBase 数据库同步的连接参数（API / 直连数据库）",
        icon=ft.Icons.STORAGE,
        initially_expanded=False,
        content_controls=[
            mb_mode,
            mb_api_fields,
            mb_db_fields,
            ft.Row(mb_action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            mb_status_text,
        ],
    )

    return minebase_card, {
        "mb_mode": mb_mode,
        "mb_db_host": mb_db_host,
        "mb_db_port": mb_db_port,
        "mb_db_name": mb_db_name,
        "mb_db_user": mb_db_user,
        "mb_db_pass": mb_db_pass,
        "mb_status_text": mb_status_text,
        "mb_action_buttons": mb_action_buttons,
        "reload": _reload_mb_config,
        "save": _save_mb_config,
        "reset": _reset_mb_config,
    }


# ---------------------------------------------------------------------------
# 4. 列映射配置
# ---------------------------------------------------------------------------

def _create_column_mapping_section(page: ft.Page, log):
    """创建 MineBase 列映射配置卡片，返回 (card, refs_dict)。"""

    _mapping_state: dict[str, dict[str, str]] = {}  # {data_type: {src: dst}}
    _mapping_data_types = ["work_efficiency", "fuel_consumption", "electricity_consumption", "equipment_operation", "production_record"]
    _mapping_type_labels = {
        "work_efficiency": "工作效率",
        "fuel_consumption": "油耗",
        "electricity_consumption": "电耗",
        "equipment_operation": "设备运行",
        "production_record": "生产数据",
    }
    # 每种数据类型对应的 MineBase 目标字段选项（camelCase API 字段名）
    _MINEBASE_FIELD_OPTIONS: dict[str, list[str]] = {
        "work_efficiency": [
            "equipmentName", "equipmentCode", "brand", "plannedMinutes", "plannedHours",
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
        label="数据类型",
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
                ft.Text("源列名（Excel 列）", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
                ft.Text("目标字段（MineBase）", expand=True, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_SECONDARY),
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
                tooltip="选择目标字段",
                icon_size=20,
                disabled=is_excluded,
                items=[
                    ft.PopupMenuItem(content=ft.Text(v), on_click=_on_menu_select) for v in options
                ],
            )
            remove_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="删除", icon_size=18, icon_color=theme.ERROR)

            exclude_cb = ft.Checkbox(
                value=is_excluded,
                tooltip="排除此列（不导入）",
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
            mapping_status_text.value = f"保存失败: {ex}"
            mapping_status_text.color = theme.ERROR
            _log_message(log, f"保存列映射配置失败: {ex}", level=logging.ERROR)
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return

        total = sum(len(v) for v in _mapping_state.values())
        mapping_status_text.value = f"已保存 {total} 条列映射"
        mapping_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, f"已保存列映射配置（{total} 条）")
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_mapping(e=None):
        reset_minebase_column_mapping()
        _reload_mapping()
        mapping_status_text.value = "已恢复默认映射"
        mapping_status_text.color = theme.TEXT_SECONDARY
        _log_message(log, "已恢复默认列映射配置")
        _build_mapping_rows()
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    mapping_action_buttons = [
        theme.primary_btn("保存映射", icon=ft.Icons.SAVE, on_click=_save_mapping),
        theme.secondary_btn("重新加载", icon=ft.Icons.REFRESH, on_click=lambda _: (_reload_mapping(), _build_mapping_rows())),
        theme.secondary_btn("恢复默认", icon=ft.Icons.RESTART_ALT, on_click=_reset_mapping),
        theme.accent_btn("添加映射", icon=ft.Icons.ADD, on_click=_add_mapping_row),
    ]

    mapping_card = theme.make_collapsible(
        title="MineBase 列映射配置",
        subtitle="配置 MiningProcessor 输出列到 MineBase 字段的映射关系",
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


# ---------------------------------------------------------------------------
# 主组装函数
# ---------------------------------------------------------------------------

def create_user_config_section(page: ft.Page, log) -> tuple[ft.Container, "UserConfigRefs"]:
    """创建用户配置页面，返回 (container, refs)。"""

    section_hint = ft.Text(
        "这里用于管理与业务处理无关的个人偏好设置。",
        size=13,
        color=theme.TEXT_SECONDARY,
    )

    keywords_card, kw_refs = _create_keywords_section(page, log)
    header_mapping_card, hm_refs = _create_header_mapping_section(page, log)
    minebase_card, mb_refs = _create_minebase_section(page, log)
    mapping_card, map_refs = _create_column_mapping_section(page, log)

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("用户配置"),
                section_hint,
                minebase_card,
                keywords_card,
                header_mapping_card,
                mapping_card,
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

    refs: UserConfigRefs = {
        "mb_mode": mb_refs["mb_mode"],
        "mb_db_host": mb_refs["mb_db_host"],
        "mb_db_port": mb_refs["mb_db_port"],
        "mb_db_name": mb_refs["mb_db_name"],
        "mb_db_user": mb_refs["mb_db_user"],
        "mb_db_pass": mb_refs["mb_db_pass"],
        "mb_status_text": mb_refs["mb_status_text"],
        "mb_action_buttons": mb_refs["mb_action_buttons"],
        "reload_mb_config": mb_refs["reload"],
        "save_mb_config": mb_refs["save"],
        "reset_mb_config": mb_refs["reset"],
        "reload_keywords": kw_refs["reload"],
        "reload_header_mapping": hm_refs["reload"],
    }

    kw_refs["reload"]()
    hm_refs["reload"]()
    mb_refs["reload"]()
    map_refs["reload"]()
    map_refs["build"]()
    return container, refs
