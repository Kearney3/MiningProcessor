"""每日报表聚合与导出。

日报以工效表中的设备/日期/班次为基准，其他数据通过统一设备解析层左连接，
这样即使某类数据缺失，也不会丢失工效设备。输入只支持 xlsx/xls。
"""

from __future__ import annotations

import ast
import copy
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from func.config_loader import get_daily_report_config
from func.excel_formatter import write_formatted_excel
from func.ledger_enrichment import resolve_equipment_attributes
from func.logger import get_logger
from func.string_utils import clean_string
from func.time_utils import local_today

logger = get_logger(__name__)


@dataclass
class DailyReportResult:
    report: pd.DataFrame
    warnings: list[dict[str, Any]]
    detail_sheets: dict[str, pd.DataFrame] = field(default_factory=dict)


_WORKTIME_ALIASES = {
    "planned_minutes": ["应运行分钟", "plannedMinutes", "planned_minutes"],
    "planned_hours": ["应运行小时数", "plannedHours", "planned_hours"],
    "planned_maintenance": ["计划维修/润滑", "plannedMaintenance", "planned_maintenance"],
    "unplanned_fault": ["未计划/故障", "unplannedFault", "unplanned_fault"],
    "total_production_minutes": [
        "总产量生产运行分钟", "总产量生产运行分钟数", "totalProductionMinutes",
        "total_production_minutes",
    ],
    "standby": ["待命", "standby"],
    "transfer": ["转移", "transfer"],
    "auxiliary_work": ["挖机场地推土/清理墙壁", "auxiliaryWork", "auxiliary_work"],
    "waiting_load": ["等待装货", "waitingLoad", "waiting_load"],
    "blasting": ["爆破", "blasting"],
    "refueling": ["柴油", "refueling"],
    "weather_snow": ["因天气：大风暴，雨，雪", "weatherSnow", "weather_snow"],
    "weather_dust": ["扬尘：洒水车不足", "weatherDust", "weather_dust"],
    "fill_water": ["排队/装水", "fillWater", "fill_water"],
    "power_issue_planned": ["因电力原因停车/计划", "powerIssuePlanned", "power_issue_planned"],
    "power_issue_unplanned": ["因电力原因停车/未计划", "powerIssueUnplanned", "power_issue_unplanned"],
}

DAILY_REPORT_FORMULA_OUTPUTS = (
    "延迟时间", "待机时间", "设备可动率", "设备可动利用率", "设备利用率",
)

def _clean_id(value: Any) -> str:
    value = clean_string(value)
    if not value:
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return value.lower()


def _date_series(df: pd.DataFrame, col: str = "日期") -> pd.Series:
    if col not in df.columns:
        return pd.Series(pd.NaT, index=df.index)
    return pd.to_datetime(df[col], errors="coerce").dt.date


def _find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    columns = {str(c).strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate in columns:
            return columns[candidate]
    return None


def _value(row: pd.Series, candidates: Iterable[str], default: Any = "") -> Any:
    col = _find_column(pd.DataFrame([row]), candidates)
    if col is None:
        return default
    value = row.get(col, default)
    return default if pd.isna(value) else value


def _number(value: Any) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0
    try:
        value = pd.to_numeric(value, errors="coerce")
        return 0.0 if pd.isna(value) else float(value)
    except (TypeError, ValueError):
        return 0.0


def _mapping_items(mapping: Any) -> list[tuple[str, list[str]]]:
    """接受 {目标: [源名称]} 或 [{target, source_names}] 两种配置形式。"""
    if not isinstance(mapping, dict):
        return []
    result = []
    for target, source_names in mapping.items():
        if isinstance(source_names, str):
            source_names = [source_names]
        if not isinstance(source_names, (list, tuple, set)):
            source_names = []
        names = [clean_string(x) for x in source_names if clean_string(x)]
        result.append((clean_string(target), names))
    return [(target, names) for target, names in result if target]


def _match_material_statistics(material: str, mappings: list[tuple[str, list[str]]]) -> str | None:
    """按配置顺序进行一次关键字匹配，命中一个统计类别后停止。"""
    folded_material = clean_string(material).casefold()
    if not folded_material:
        return None
    for target, keywords in mappings:
        if any(clean_string(keyword).casefold() in folded_material for keyword in keywords):
            return target
    return None


def _read_sheet(path: Path, preferred: str | None = None) -> pd.DataFrame | None:
    try:
        with pd.ExcelFile(path) as book:
            sheet = preferred if preferred in book.sheet_names else book.sheet_names[0]
            return pd.read_excel(book, sheet_name=sheet)
    except Exception as exc:
        logger.warning("读取日报数据文件失败 %s: %s", path, exc)
        return None


def _source_files(source_dir: str | Path) -> dict[str, list[Path]]:
    root = Path(source_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"日报输入目录不存在: {root}")
    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {".xlsx", ".xls"}]

    def exact(stem: str) -> list[Path]:
        return [p for p in files if p.stem.lower() == stem.lower()]

    def has_sheet(path: Path, sheet_name: str) -> bool:
        try:
            with pd.ExcelFile(path) as book:
                return sheet_name in book.sheet_names
        except Exception:
            return False

    # 标准中间结果优先使用明确的标准 Sheet；原始工作簿留给预处理阶段。
    worktime_candidates = sorted([p for p in files if "工作效率表" in p.name])
    worktime = [p for p in worktime_candidates if has_sheet(p, "工时数据")]
    raw_worktime = [p for p in worktime_candidates if p not in worktime]
    operation = exact("合并产量")
    fuel = exact("Fuel")
    electrical = exact("电力消耗统计")
    return {
        "worktime": worktime,
        "operation": operation,
        "production": operation,
        "fuel": fuel,
        "electrical": electrical,
        "raw_worktime": raw_worktime,
        "raw_production": sorted([
            p for p in files if "白班" in p.name or "夜班" in p.name
        ]),
        "raw_fuel": sorted([
            p for p in files if "Fuel report" in p.name or "设备柴油消耗" in p.name
        ]),
        "raw_electrical": sorted([
            p for p in files if "Цахилгааны хэлтэс" in p.name or "Electrical" in p.name
        ]),
    }


def _concat_sources(paths: list[Path], sheet: str | None) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = _read_sheet(path, sheet)
        if frame is not None and not frame.empty:
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


_PREPROCESS_OPTION_DEFAULTS = {
    "skip_hidden_rows": False,
    "skip_hidden_cols": False,
    "filter_zero_engine_hours": False,
    "filter_zero_work_hours": False,
    "filter_zero_hours_meter": False,
    "filter_zero_km_meter": False,
    "filter_zero_run_hours": False,
    "filter_zero_run_km": False,
}


def _preprocess_options(options: dict[str, Any] | None) -> dict[str, Any]:
    """规范化日报预处理选项，确保只透传现有处理器支持的参数。"""
    result = dict(_PREPROCESS_OPTION_DEFAULTS)
    if isinstance(options, dict):
        for key in result:
            result[key] = bool(options.get(key, result[key]))
    return result


def _processing_year_month(start: date | str | None, end: date | str | None,
                           paths: Iterable[Path]) -> tuple[int, int]:
    """为原始工效/油耗处理器确定年月。"""
    for value in (start, end):
        if value is not None:
            parsed = pd.to_datetime(value, errors="coerce")
            if not pd.isna(parsed):
                return int(parsed.year), int(parsed.month)
    for path in paths:
        match = re.search(r"(20\d{2})[.\-_](\d{1,2})", path.name)
        if match:
            return int(match.group(1)), int(match.group(2))
    today = local_today()
    return today.year, today.month


def _preprocess_worktime(path: Path, year: int, month: int, options: dict[str, Any]) -> pd.DataFrame | None:
    """调用现有工效处理器，返回已标准化的工时表。"""
    from func.config_loader import get_worktime_header_mapping
    from func.excel_worktime import process_excel_data

    header_mapping = copy.deepcopy(get_worktime_header_mapping())
    # 位置映射依赖原始列位置。跳过隐藏列后位置会变化，优先改用同一配置中的关键字匹配。
    if options["skip_hidden_cols"] and header_mapping.get("mode") == "position":
        if any(entry.get("keywords") for entry in header_mapping.get("entries", [])):
            header_mapping["mode"] = "name"
            logger.info("日报工效预处理：跳过隐藏列，表头映射切换为关键字模式")
    sheets = process_excel_data(
        str(path), year, month, return_sheets=True,
        header_mapping=header_mapping,
        skip_hidden_rows=options["skip_hidden_rows"],
        skip_hidden_cols=options["skip_hidden_cols"],
    )
    return (sheets or {}).get("工时数据") if sheets else None


def _preprocess_sources(source_dir: str | Path, start: date | str | None,
                        end: date | str | None, options: dict[str, Any],
                        warnings: list[dict[str, Any]]) -> dict[str, list[pd.DataFrame]]:
    """先调用各类既有处理器，再返回用于日报合并的标准化 DataFrame。"""
    from func.excel_electrical import parse_excel_data
    from func.excel_fuel import process_diesel_data
    from func.excel_production_enhanced import MiningDataProcessor

    files = _source_files(source_dir)
    all_raw = [path for paths in files.values() for path in paths]
    year, month = _processing_year_month(start, end, all_raw)
    result: dict[str, list[pd.DataFrame]] = {
        "worktime": [], "operation": [], "production": [], "fuel": [], "electrical": [],
    }

    def add_standard(data_type: str, paths: list[Path], sheet: str | None):
        for path in paths:
            frame = _read_sheet(path, sheet)
            if frame is not None and not frame.empty:
                result[data_type].append(frame)

    # 1. 目录中有原始文件时，必须先走对应处理器；标准中间结果仅作为回退。
    #    这样隐藏行/列与零值过滤选项不会因为旧的中间文件而失效。
    if not files["raw_worktime"]:
        add_standard("worktime", files["worktime"], "工时数据")
    if not files["raw_production"]:
        add_standard("operation", files["operation"], "运行数据")
        add_standard("production", files["production"], "生产数据")
    if not files["raw_fuel"]:
        add_standard("fuel", files["fuel"], "油耗信息")
    if not files["raw_electrical"]:
        add_standard("electrical", files["electrical"], None)

    if not result["worktime"] and files["raw_worktime"]:
        for path in files["raw_worktime"]:
            try:
                frame = _preprocess_worktime(path, year, month, options)
                if frame is not None and not frame.empty:
                    result["worktime"].append(frame)
                    logger.info("日报工效预处理完成：%s，共 %d 行", path.name, len(frame))
                    break
            except Exception as exc:
                warnings.append({"数据类型": "工时预处理", "字段": path.name,
                                 "值": str(path), "消息": str(exc)})
                logger.exception("日报工效预处理失败：%s", path)
    if not result["worktime"]:
        add_standard("worktime", files["worktime"], "工时数据")

    if files["raw_production"]:
        try:
            processor = MiningDataProcessor(
                skip_hidden_rows=options["skip_hidden_rows"],
                skip_hidden_cols=options["skip_hidden_cols"],
                filter_zero_hours_meter=options["filter_zero_hours_meter"],
                filter_zero_km_meter=options["filter_zero_km_meter"],
                filter_zero_run_hours=options["filter_zero_run_hours"],
                filter_zero_run_km=options["filter_zero_run_km"],
            )
            sheets = processor.process_folder(str(source_dir), return_sheets=True)
            if sheets:
                if sheets.get("运行数据") is not None:
                    result["operation"].append(sheets["运行数据"])
                if sheets.get("生产数据") is not None:
                    result["production"].append(sheets["生产数据"])
                logger.info("日报生产预处理完成：运行 %d 行，生产 %d 行",
                            len(sheets.get("运行数据", [])), len(sheets.get("生产数据", [])))
        except Exception as exc:
            warnings.append({"数据类型": "生产预处理", "字段": "运行/生产数据",
                             "值": str(source_dir), "消息": str(exc)})
            logger.exception("日报生产预处理失败：%s", source_dir)
    if not result["operation"]:
        add_standard("operation", files["operation"], "运行数据")
    if not result["production"]:
        add_standard("production", files["production"], "生产数据")

    if not result["fuel"] and files["raw_fuel"]:
        for path in files["raw_fuel"]:
            try:
                sheets = process_diesel_data(
                    str(path), target_year=year, return_sheets=True,
                    skip_hidden_rows=options["skip_hidden_rows"],
                    skip_hidden_cols=options["skip_hidden_cols"],
                    filter_zero_engine_hours=options["filter_zero_engine_hours"],
                    filter_zero_work_hours=options["filter_zero_work_hours"],
                )
                frame = (sheets or {}).get("油耗信息") if sheets else None
                if frame is not None and not frame.empty:
                    result["fuel"].append(frame)
                    logger.info("日报油耗预处理完成：%s，共 %d 行", path.name, len(frame))
                    break
            except Exception as exc:
                warnings.append({"数据类型": "油耗预处理", "字段": path.name,
                                 "值": str(path), "消息": str(exc)})
                logger.exception("日报油耗预处理失败：%s", path)
    if not result["fuel"]:
        add_standard("fuel", files["fuel"], "油耗信息")

    if not result["electrical"] and files["raw_electrical"]:
        for path in files["raw_electrical"]:
            try:
                sheets = parse_excel_data(
                    str(path), target_year=year, return_sheets=True,
                    add_shift_column=True, default_shift="Day",
                    skip_hidden_rows=options["skip_hidden_rows"],
                    skip_hidden_cols=options["skip_hidden_cols"],
                )
                frame = (sheets or {}).get("电力消耗") if sheets else None
                if frame is not None and not frame.empty:
                    result["electrical"].append(frame)
                    logger.info("日报电耗预处理完成：%s，共 %d 行", path.name, len(frame))
                    break
            except Exception as exc:
                warnings.append({"数据类型": "电耗预处理", "字段": path.name,
                                 "值": str(path), "消息": str(exc)})
                logger.exception("日报电耗预处理失败：%s", path)
    if not result["electrical"]:
        add_standard("electrical", files["electrical"], None)

    return result


def _concat_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    return pd.concat(valid, ignore_index=True) if valid else pd.DataFrame()


def _filter_dates(df: pd.DataFrame, start: date | str | None, end: date | str | None) -> pd.DataFrame:
    if df.empty or "日期" not in df.columns:
        return df
    dates = _date_series(df)
    if start is not None:
        start = pd.to_datetime(start).date()
        df = df.loc[dates >= start].copy()
        dates = _date_series(df)
    if end is not None:
        end = pd.to_datetime(end).date()
        df = df.loc[dates <= end].copy()
    return df


def _canonical_device(row: pd.Series, equipment_ledger=None, model_ledger=None, *, name_fields, id_fields, company_fields):
    name = _value(row, name_fields)
    device_id = _value(row, id_fields)
    company = clean_string(_value(row, company_fields))
    attrs = resolve_equipment_attributes(name, device_id, equipment_ledger, model_ledger)
    if not attrs["标准设备名称"]:
        attrs["标准设备名称"] = clean_string(name)
    if not attrs["标准设备编号"]:
        attrs["标准设备编号"] = clean_string(device_id)
    if not attrs["标准公司名称"]:
        attrs["标准公司名称"] = company
    attrs["原始设备名称"] = clean_string(name)
    attrs["原始设备编号"] = clean_string(device_id)
    attrs["原始公司名称"] = company
    return attrs


def _device_key(attrs: dict[str, Any], target_date: Any, shift: Any) -> tuple:
    identity = _clean_id(attrs.get("标准设备编号")) or clean_string(attrs.get("标准设备名称")).lower()
    return (target_date, clean_string(shift), identity)


def _convert_ternary(expression: str) -> str:
    """将用户配置的 cond?yes:no 转成 AST 支持的 if 表达式。"""
    expression = expression.strip()
    depth = 0
    question = -1
    quote = None
    for index, char in enumerate(expression):
        if quote:
            if char == quote and (index == 0 or expression[index - 1] != "\\"):
                quote = None
            continue
        if char in "'\"":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "?" and depth == 0:
            question = index
            break
    if question < 0:
        return expression
    depth = 0
    nested = 0
    colon = -1
    for index in range(question + 1, len(expression)):
        char = expression[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif depth == 0 and char == "?":
            nested += 1
        elif depth == 0 and char == ":":
            if nested:
                nested -= 1
            else:
                colon = index
                break
    if colon < 0:
        raise ValueError("三元表达式缺少 ':'")
    condition = expression[:question]
    yes = expression[question + 1:colon]
    no = expression[colon + 1:]
    return f"({_convert_ternary(yes)} if {_convert_ternary(condition)} else {_convert_ternary(no)})"


class _SafeFormula:
    _allowed_binops = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
    _allowed_cmps = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)

    def __init__(self, expression: str):
        self.expression = _convert_ternary(str(expression or "0"))
        self.tree = ast.parse(self.expression, mode="eval").body
        self.names = {
            node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name)
        }

    def evaluate(self, values: dict[str, float]) -> float:
        try:
            return float(self._eval(self.tree, values))
        except (ArithmeticError, TypeError, ValueError, KeyError, ZeroDivisionError):
            return 0.0

    def validate(self) -> None:
        """用一组安全数值执行一次 AST，提前发现不支持的公式节点。"""
        sample_values = {name: 1.0 for name in self.names}
        try:
            self._eval(self.tree, sample_values)
        except (ArithmeticError, TypeError, ValueError, KeyError, ZeroDivisionError) as exc:
            raise ValueError(str(exc)) from exc

    def _eval(self, node, values):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id, 0.0)
        if isinstance(node, ast.BinOp) and isinstance(node.op, self._allowed_binops):
            left, right = self._eval(node.left, values), self._eval(node.right, values)
            if isinstance(node.op, ast.Div) and right == 0:
                return 0.0
            return {ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                    ast.Mult: lambda: left * right, ast.Div: lambda: left / right,
                    ast.Mod: lambda: left % right, ast.Pow: lambda: left ** right}[type(node.op)]()
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._eval(node.operand, values)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, values)
            for op, comparator in zip(node.ops, node.comparators):
                if not isinstance(op, self._allowed_cmps):
                    raise ValueError("不支持的比较运算")
                right = self._eval(comparator, values)
                if not {ast.Lt: left < right, ast.LtE: left <= right, ast.Gt: left > right,
                        ast.GtE: left >= right, ast.Eq: left == right,
                        ast.NotEq: left != right}[type(op)]:
                    return 0.0
                left = right
            return 1.0
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values_ = [bool(self._eval(item, values)) for item in node.values]
            return float(all(values_) if isinstance(node.op, ast.And) else any(values_))
        if isinstance(node, ast.IfExp):
            return self._eval(node.body if self._eval(node.test, values) else node.orelse, values)
        raise ValueError("公式包含不支持的语法")


def _available_formula_names(available_columns: Iterable[Any]) -> set[str]:
    """根据实际工时表头，计算当前可用的公式变量。"""
    column_names = {str(column).strip() for column in available_columns}
    aliases = _worktime_formula_aliases()
    return {
        name
        for name, candidates in aliases.items()
        if any(str(candidate).strip() in column_names for candidate in candidates)
    }


def validate_daily_report_formulas(
    formulas: dict[str, Any] | None,
    available_columns: Iterable[Any] | None = None,
) -> dict[str, str]:
    """校验日报公式语法、字段名和实际表头，返回 ``{字段: 错误信息}``。

    ``available_columns`` 在日报导出时传入实际工时表头，用于检查公式引用的
    canonical 字段是否真的存在。用户配置页没有输入文件，因此只做语法和字段名校验。
    """
    formulas = formulas if isinstance(formulas, dict) else {}
    allowed_names = set(_WORKTIME_ALIASES)
    available_names = (
        _available_formula_names(available_columns)
        if available_columns is not None else None
    )
    errors: dict[str, str] = {}
    for output_name in DAILY_REPORT_FORMULA_OUTPUTS:
        expression = formulas.get(output_name)
        if expression is None or not str(expression).strip():
            errors[output_name] = "公式不能为空"
            continue
        try:
            formula = _SafeFormula(expression)
            formula.validate()
        except (SyntaxError, ValueError) as exc:
            errors[output_name] = f"公式语法错误: {exc}"
            continue
        unknown = sorted(formula.names - allowed_names)
        if unknown:
            errors[output_name] = f"存在未支持的目标字段: {', '.join(unknown)}"
            continue
        if available_names is not None:
            missing = sorted(formula.names - available_names)
            if missing:
                errors[output_name] = f"公式字段不存在于工时表头: {', '.join(missing)}"
    return errors


def _worktime_formula_aliases() -> dict[str, list[str]]:
    """把现有工时表头/列映射配置纳入公式目标字段解析。"""
    from func.config_loader import get_minebase_column_mapping, get_worktime_header_mapping

    aliases = {key: list(values) for key, values in _WORKTIME_ALIASES.items()}
    target_to_key = {
        "plannedminutes": "planned_minutes",
        "plannedhours": "planned_hours",
        "plannedmaintenance": "planned_maintenance",
        "unplannedfault": "unplanned_fault",
        "totalproductionminutes": "total_production_minutes",
        "standby": "standby",
        "transfer": "transfer",
        "auxiliarywork": "auxiliary_work",
        "waitingload": "waiting_load",
        "blasting": "blasting",
        "refueling": "refueling",
        "weathersnow": "weather_snow",
        "weatherdust": "weather_dust",
        "fillwater": "fill_water",
        "powerissueplanned": "power_issue_planned",
        "powerissueunplanned": "power_issue_unplanned",
    }
    mapping = get_minebase_column_mapping().get("work_efficiency", {})
    if isinstance(mapping, dict):
        for source, target in mapping.items():
            key = target_to_key.get(str(target).replace("_", "").lower())
            if key:
                aliases[key].append(str(source))
    header_mapping = get_worktime_header_mapping()
    for entry in header_mapping.get("entries", []) if isinstance(header_mapping, dict) else []:
        new_name = clean_string(entry.get("new"))
        if not new_name:
            continue
        for key, values in aliases.items():
            if new_name in values:
                aliases[key].append(new_name)
    return aliases


def _formula_context(row: pd.Series, aliases: dict[str, list[str]] | None = None) -> dict[str, float]:
    context = {}
    for name, names in (aliases or _WORKTIME_ALIASES).items():
        context[name] = _number(_value(row, names))
    return context


def _operation_aggregates(operation: pd.DataFrame, equipment_ledger, model_ledger, start, end):
    result = {}
    operation = _filter_dates(operation, start, end)
    for _, row in operation.iterrows():
        target_date = _date_series(pd.DataFrame([row])).iloc[0]
        if pd.isna(target_date):
            continue
        shift = _value(row, ["班次", "shiftType"], "")
        attrs = _canonical_device(
            row, equipment_ledger, model_ledger,
            name_fields=["设备名称", "sourceEquipmentName", "原始设备名称", "标准设备名称"],
            id_fields=["设备编号", "sourceEquipmentCode", "原始设备编号", "标准设备编号"],
            company_fields=["公司", "sourceCompany", "原始公司名称"],
        )
        key = _device_key(attrs, target_date, shift)
        bucket = result.setdefault(key, {"小时数仪表开始": None, "小时数仪表结束": None,
                                         "运行小时数": 0.0, "公里数仪表开始": None,
                                         "公里数仪表结束": None, "运行里程": 0.0})
        for out, aliases in {
            "小时数仪表开始": ["小时数仪表开始", "engineHoursStart"],
            "公里数仪表开始": ["公里数仪表开始", "milemeterStart"],
        }.items():
            value = _number(_value(row, aliases))
            if bucket[out] is None or value < bucket[out]:
                bucket[out] = value
        for out, aliases in {
            "小时数仪表结束": ["小时数仪表结束", "engineHoursEnd"],
            "公里数仪表结束": ["公里数仪表结束", "milemeterEnd"],
        }.items():
            bucket[out] = _number(_value(row, aliases))
        bucket["运行小时数"] += _number(_value(row, ["运行小时数", "runningHours"]))
        bucket["运行里程"] += _number(_value(row, ["运行里程", "mileage"]))
    return result


def _energy_aggregates(df: pd.DataFrame, equipment_ledger, model_ledger, start, end, *, electrical=False):
    result = {}
    df = _filter_dates(df, start, end)
    for _, row in df.iterrows():
        target_date = _date_series(pd.DataFrame([row])).iloc[0]
        if pd.isna(target_date):
            continue
        shift = _value(row, ["班次", "shiftType"], "")
        attrs = _canonical_device(
            row, equipment_ledger, model_ledger,
            name_fields=["设备名称", "sourceEquipmentName", "原始设备名称", "标准设备名称"],
            id_fields=["设备编号", "sourceEquipmentCode", "原始设备编号", "标准设备编号"],
            company_fields=["公司", "sourceCompany", "原始公司名称"],
        )
        key = _device_key(attrs, target_date, shift)
        result[key] = result.get(key, 0.0) + _number(
            _value(row, ["电力消耗", "consumption"] if electrical else ["油品消耗", "consumption"])
        )
    return result


def _build_detail_sheets(
    sources: dict[str, list[pd.DataFrame]],
    start: date | str | None,
    end: date | str | None,
) -> dict[str, pd.DataFrame]:
    """构建可选的日报分项 Sheet，保留各模块经过预处理后的明细。"""
    sheet_specs = (
        ("工时统计", "worktime"),
        ("运行统计", "operation"),
        ("生产统计", "production"),
        ("油耗统计", "fuel"),
        ("电耗统计", "electrical"),
    )
    sheets: dict[str, pd.DataFrame] = {}
    for sheet_name, data_type in sheet_specs:
        frame = _filter_dates(_concat_frames(sources.get(data_type, [])), start, end)
        if not frame.empty:
            sheets[sheet_name] = frame.reset_index(drop=True)
    return sheets


def build_daily_report(
    source_dir: str | Path,
    start: date | str | None = None,
    end: date | str | None = None,
    *,
    equipment_ledger=None,
    model_ledger=None,
    config: dict[str, Any] | None = None,
    preprocess_options: dict[str, Any] | None = None,
    include_detail_sheets: bool = False,
) -> DailyReportResult:
    """先预处理原始数据，再构建日报 DataFrame，不写文件。"""
    base_config = get_daily_report_config()
    if isinstance(config, dict):
        config = {
            **base_config,
            **config,
            "material_statistics": {
                **base_config.get("material_statistics", {}),
                **config.get("material_statistics", {}),
            },
            "formulas": {
                **base_config.get("formulas", {}),
                **config.get("formulas", {}),
            },
        }
    else:
        config = base_config
    warnings: list[dict[str, Any]] = []
    options = _preprocess_options(preprocess_options)
    sources = _preprocess_sources(source_dir, start, end, options, warnings)
    detail_sheets = _build_detail_sheets(sources, start, end) if include_detail_sheets else {}

    worktime = _concat_frames(sources["worktime"])
    if worktime.empty:
        raise ValueError("未找到工时数据文件，日报必须以工效设备列表为基准")
    worktime = _filter_dates(worktime, start, end)
    if worktime.empty:
        return DailyReportResult(pd.DataFrame(), warnings, detail_sheets)

    identity_columns = {
        "日期", "班次", "设备名称", "设备编号", "公司",
        "sourceEquipmentName", "sourceEquipmentCode", "sourceCompany",
        "标准设备名称", "标准设备编号", "标准公司名称",
        "所有权", "设备型号", "设备类型", "内部分类",
    }
    # 日报的工时明细从“应运行分钟”开始，到“备注”结束，避免把序号、
    # 设备种类等识别字段混入最终日报；若源表缺少边界，则保留可用的非识别列。
    worktime_columns = list(worktime.columns)
    start_index = next(
        (index for index, column in enumerate(worktime_columns)
         if str(column) in {"应运行分钟", "plannedMinutes", "planned_minutes"}),
        None,
    )
    end_index = next(
        (index for index, column in reversed(list(enumerate(worktime_columns)))
         if str(column) in {"备注", "remark"}),
        None,
    )
    if start_index is not None:
        end_position = end_index if end_index is not None and end_index >= start_index else len(worktime_columns) - 1
        worktime_data_columns = worktime_columns[start_index:end_position + 1]
    else:
        worktime_data_columns = worktime_columns

    # 以工效记录构造唯一基础行；同一设备重复行只保留第一行，工时列随后按原值输出。
    base_rows: dict[tuple, dict[str, Any]] = {}
    worktime_extra: dict[tuple, dict[str, Any]] = {}
    for _, row in worktime.iterrows():
        target_date = _date_series(pd.DataFrame([row])).iloc[0]
        if pd.isna(target_date):
            continue
        shift = _value(row, ["班次", "shiftType"], "")
        attrs = _canonical_device(
            row, equipment_ledger, model_ledger,
            name_fields=["设备名称", "sourceEquipmentName", "原始设备名称", "标准设备名称"],
            id_fields=["设备编号", "sourceEquipmentCode", "原始设备编号", "标准设备编号"],
            company_fields=["公司", "sourceCompany", "原始公司名称"],
        )
        key = _device_key(attrs, target_date, shift)
        if key not in base_rows:
            base_rows[key] = {"日期": target_date, "班次": clean_string(shift), "设备角色": "设备", **attrs}
            worktime_extra[key] = {
                str(c): row.get(c) for c in worktime_data_columns
                if str(c) not in identity_columns
            }

    if equipment_ledger:
        unmatched_equipment = sorted({
            (
                clean_string(base.get("原始设备名称")),
                clean_string(base.get("原始设备编号")),
            )
            for base in base_rows.values()
            if not clean_string(base.get("标准设备编号"))
        })
        for name, device_id in unmatched_equipment:
            warnings.append({
                "数据类型": "设备台账", "字段": "标准设备编号",
                "值": device_id or name,
                "消息": "设备台账未匹配，已保留原始设备名称，标准设备编号为空",
            })

    operation = _concat_frames(sources["operation"])
    operations = _operation_aggregates(operation, equipment_ledger, model_ledger, start, end)
    fuel = _energy_aggregates(_concat_frames(sources["fuel"]), equipment_ledger, model_ledger, start, end)
    electricity = _energy_aggregates(_concat_frames(sources["electrical"]), equipment_ledger, model_ledger, start, end, electrical=True)

    production = _concat_frames(sources["production"])
    production = _filter_dates(production, start, end)
    statistic_materials = _mapping_items(config.get("material_statistics", {}))
    material_type_names: list[str] = []
    material_type_by_key: dict[str, str] = {}
    unmatched_statistics_materials: set[str] = set()
    production_buckets: dict[tuple, dict[str, Any]] = {}
    for _, row in production.iterrows():
        target_date = _date_series(pd.DataFrame([row])).iloc[0]
        if pd.isna(target_date):
            continue
        shift = _value(row, ["班次", "shiftType"], "")
        material = clean_string(_value(row, ["矿石类型", "sourceMaterialTypeName", "物料类型", "materialTypeName"]))
        material_key = material.casefold()
        if material and material_key not in material_type_by_key:
            material_type_by_key[material_key] = material
            material_type_names.append(material)
        material_display = material_type_by_key.get(material_key, material)
        production_value = _number(_value(row, ["产量", "production"]))
        trip_value = _number(_value(row, ["运次", "趟次", "tripCount", "trip_count"]))
        statistic_target = _match_material_statistics(material, statistic_materials)
        truck = _canonical_device(
            row, equipment_ledger, model_ledger,
            name_fields=["矿卡名称", "sourceTruckName"],
            id_fields=["矿卡编号", "sourceTruckCode"],
            company_fields=["矿卡公司", "sourceTruckCompany"],
        )
        excavator = _canonical_device(
            row, equipment_ledger, model_ledger,
            name_fields=["挖机名称", "sourceExcavatorName"],
            id_fields=["挖机编号", "sourceExcavatorCode"],
            company_fields=["挖机公司", "sourceExcavatorCompany"],
        )
        for attrs in (truck, excavator):
            if not attrs.get("原始设备名称"):
                continue
            key = _device_key(attrs, target_date, shift)
            bucket = production_buckets.setdefault(key, {
                "产量": 0.0, "趟次": 0.0, "统计": {}, "物料": {},
            })
            bucket["产量"] += production_value
            bucket["趟次"] += trip_value
            if statistic_target:
                bucket["统计"][statistic_target] = bucket["统计"].get(statistic_target, 0.0) + production_value
            elif material:
                unmatched_statistics_materials.add(material_display)
            if material:
                material_bucket = bucket["物料"].setdefault(material_display, {"产量": 0.0, "趟次": 0.0})
                material_bucket["产量"] += production_value
                material_bucket["趟次"] += trip_value

    for material in sorted(unmatched_statistics_materials, key=str.casefold):
        warnings.append({
            "数据类型": "生产数据", "字段": "物料统计配置", "值": material,
            "消息": "物料名称未命中任何统计分类，已保留在物料类型展开列，未归入其他",
        })

    formulas = config.get("formulas", {}) if isinstance(config.get("formulas", {}), dict) else {}
    formula_aliases = _worktime_formula_aliases()
    compiled_formulas = {}
    formula_errors = validate_daily_report_formulas(formulas, available_columns=worktime.columns)
    for key, message in formula_errors.items():
        warnings.append({
            "数据类型": "日报配置",
            "字段": key,
            "值": formulas.get(key, ""),
            "消息": message,
        })
    for key in DAILY_REPORT_FORMULA_OUTPUTS:
        expression = formulas.get(key)
        if key in formula_errors or expression is None:
            continue
        try:
            compiled_formulas[key] = _SafeFormula(expression)
        except (SyntaxError, ValueError):
            # validate_daily_report_formulas 已经给出可展示的错误信息。
            continue

    material_target_names = [target for target, _ in statistic_materials]
    output_rows = []
    for key, base in base_rows.items():
        row = dict(base)
        op = operations.get(key, {})
        row.update(op)
        prod = production_buckets.get(key, {"产量": 0.0, "趟次": 0.0, "统计": {}, "物料": {}})
        row["产量"] = prod["产量"]
        row["趟次"] = prod["趟次"]
        for target in material_target_names:
            row[target] = prod["统计"].get(target, 0.0)
        for material in material_type_names:
            material_bucket = prod["物料"].get(material, {"产量": 0.0, "趟次": 0.0})
            row[f"{material}产量"] = material_bucket["产量"]
            row[f"{material}趟次"] = material_bucket["趟次"]
        oil_value, electric_value = fuel.get(key), electricity.get(key)
        if oil_value is not None and electric_value is not None:
            warnings.append({"数据类型": "能耗", "字段": "能耗", "值": str(key),
                             "消息": "同一设备同时存在油耗和电耗，日报优先显示油耗"})
        if oil_value is not None:
            row["能耗"], row["能耗单位"] = oil_value, "L"
        elif electric_value is not None:
            row["能耗"], row["能耗单位"] = electric_value, "kWh"
        else:
            row["能耗"], row["能耗单位"] = 0.0, ""
        row["运距（里程/趟次/2）"] = row.get("运行里程", 0.0) / row["趟次"] / 2 if row["趟次"] else 0.0
        extra = worktime_extra.get(key, {})
        row.update(extra)
        context = _formula_context(pd.Series(extra), formula_aliases)
        for output_name in ("延迟时间", "待机时间", "设备可动率", "设备可动利用率", "设备利用率"):
            formula = compiled_formulas.get(output_name)
            if formula:
                row[output_name] = formula.evaluate(context)

        output_rows.append(row)

    report = pd.DataFrame(output_rows)
    if not report.empty:
        report = report.sort_values(["日期", "班次", "标准设备编号", "标准设备名称"], kind="stable").reset_index(drop=True)

    columns = ["日期", "班次"]
    if config.get("include_raw_equipment_name", True):
        columns.append("原始设备名称")
    columns.append("标准设备名称")
    if config.get("include_raw_equipment_code", True):
        columns.append("原始设备编号")
    columns.append("标准设备编号")
    if config.get("include_raw_company_name", True):
        columns.append("原始公司名称")
    columns.extend(["标准公司名称", "所有权", "设备型号", "设备类型", "内部分类", "产量", "趟次"])
    columns.extend(material_target_names)
    columns.extend([f"{material}产量" for material in material_type_names])
    columns.extend([f"{material}趟次" for material in material_type_names])
    columns.extend(["小时数仪表开始", "小时数仪表结束", "运行小时数", "公里数仪表开始", "公里数仪表结束",
                    "运行里程", "运距（里程/趟次/2）", "能耗", "能耗单位", "延迟时间", "待机时间",
                    "设备可动率", "设备可动利用率", "设备利用率"])
    known = set(columns)
    extra_worktime_columns = []
    for column in worktime_data_columns:
        column = str(column)
        if column not in known and column not in identity_columns:
            extra_worktime_columns.append(column)
    columns.extend(extra_worktime_columns)
    report = report.reindex(columns=[column for column in columns if column in report.columns])
    return DailyReportResult(report, warnings, detail_sheets)


def export_daily_report(
    source_dir: str | Path,
    output_file: str | Path,
    start: date | str | None = None,
    end: date | str | None = None,
    *,
    equipment_ledger=None,
    model_ledger=None,
    config: dict[str, Any] | None = None,
    preprocess_options: dict[str, Any] | None = None,
    include_detail_sheets: bool = False,
) -> DailyReportResult:
    """构建并导出日报，可选附加各模块分项 Sheet。"""
    result = build_daily_report(
        source_dir, start, end,
        equipment_ledger=equipment_ledger,
        model_ledger=model_ledger,
        config=config,
        preprocess_options=preprocess_options,
        include_detail_sheets=include_detail_sheets,
    )
    warning_df = pd.DataFrame(result.warnings, columns=["数据类型", "字段", "值", "消息"])
    sheets = {"日报": result.report, **result.detail_sheets, "匹配警告": warning_df}
    write_formatted_excel(str(output_file), sheets, date_only=True)
    logger.info("日报已导出: %s，共 %d 行，警告 %d 条", output_file, len(result.report), len(result.warnings))
    return result
