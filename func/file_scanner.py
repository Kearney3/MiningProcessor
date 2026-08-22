"""统一的 Excel 文件扫描与报表类型识别。

扫描只负责回答两个问题：目录中有哪些 Excel 文件，以及每个文件可能属于
哪些业务类型。真正的读取和处理仍由各业务处理器完成。这样 GUI 可以先让
用户检查识别结果，再把用户勾选的文件列表传给后续流程。
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from func.config_loader import get_file_keywords
from func.sync.constants import DATA_TYPE_REGISTRY

EXCEL_SUFFIXES = frozenset({".xlsx", ".xls"})

BATCH_TYPES = ("fuel", "electrical", "production", "worktime")
SYNC_TYPES = ("fuel", "production", "electrical", "work_efficiency", "operation")
DAILY_TYPES = ("worktime", "production", "electrical", "fuel")

TYPE_LABELS = {
    "fuel": "油耗",
    "electrical": "电耗",
    "production": "生产",
    "operation": "运行",
    "worktime": "工时",
    "work_efficiency": "工时",
}


def _excel_files(root: Path, *, recursive: bool = False) -> list[Path]:
    """列出待扫描的 Excel 文件；批处理还支持生产处理器使用的子目录。"""
    candidates = root.rglob("*") if recursive else root.iterdir()
    return sorted(
        (
            path
            for path in candidates
            if path.is_file()
            and path.suffix.lower() in EXCEL_SUFFIXES
            and not path.name.startswith("~$")
        ),
        key=lambda path: path.name.casefold(),
    )


def _contains_keyword(name: str, keyword: str) -> bool:
    return bool(keyword) and keyword.casefold() in name.casefold()


def _pattern_matches(name: str, pattern: str) -> bool:
    folded_name = name.casefold()
    folded_pattern = pattern.casefold()
    if fnmatch.fnmatch(folded_name, folded_pattern):
        return True
    # 与同步发现逻辑一致：标准输出的 .xlsx 模式也接受 .xls。
    if folded_pattern.endswith(".xlsx"):
        return fnmatch.fnmatch(folded_name, folded_pattern[:-5] + ".xls")
    return False


def _configured_matches(name: str, module_type: str, keywords: dict[str, list[str]]) -> bool:
    return any(_contains_keyword(name, keyword) for keyword in keywords.get(module_type, []))


def _classify_batch(name: str, keywords: dict[str, list[str]]) -> list[str]:
    """按批处理配置的文件名关键字识别类型。"""
    return [
        module_type
        for module_type in BATCH_TYPES
        if _configured_matches(name, module_type, keywords)
    ]


def _classify_sync(name: str, keywords: dict[str, list[str]]) -> list[str]:
    """识别同步输入，覆盖标准化输出文件和原始报表文件。"""
    types: list[str] = []

    # 标准化输出文件：同一个「合并产量」文件同时提供生产和运行数据。
    for data_type, info in DATA_TYPE_REGISTRY.items():
        if _pattern_matches(name, str(info.get("file_pattern", ""))):
            if data_type not in types:
                types.append(data_type)
            if data_type == "production" and "operation" not in types:
                types.append("operation")

    # 原始文件关键字回退，与同步处理器 discover_files 保持同一配置来源。
    if _configured_matches(name, "fuel", keywords) and "fuel" not in types:
        types.append("fuel")
    if _configured_matches(name, "electrical", keywords) and "electrical" not in types:
        types.append("electrical")
    if _configured_matches(name, "production", keywords):
        for data_type in ("production", "operation"):
            if data_type not in types:
                types.append(data_type)
    if _configured_matches(name, "worktime", keywords) and "work_efficiency" not in types:
        types.append("work_efficiency")

    return [data_type for data_type in SYNC_TYPES if data_type in types]


def _classify_daily(name: str) -> list[str]:
    """按日报的标准输出和原始报表命名规则识别类型。"""
    types: list[str] = []
    folded_name = name.casefold()
    folded_stem = Path(name).stem.casefold()

    if folded_stem == "fuel" or "fuel report" in folded_name or "设备柴油消耗" in name:
        types.append("fuel")
    if folded_stem == "电力消耗统计" or "electrical" in folded_name or "цахилгааны хэлтэс" in folded_name:
        types.append("electrical")
    if "工作效率表" in name:
        types.append("worktime")
    if folded_stem == "合并产量" or "白班" in name or "夜班" in name:
        types.append("production")

    return [data_type for data_type in DAILY_TYPES if data_type in types]


def classify_filename(
    name: str,
    *,
    scope: str = "batch",
    keywords: dict[str, list[str]] | None = None,
) -> list[str]:
    """识别单个文件名，返回稳定顺序的业务类型 ID。"""
    keywords = keywords if keywords is not None else get_file_keywords()
    if scope == "batch":
        return _classify_batch(name, keywords)
    if scope == "sync":
        return _classify_sync(name, keywords)
    if scope == "daily":
        return _classify_daily(name)
    raise ValueError(f"未知扫描范围: {scope}")


def _expected_types(scope: str) -> tuple[str, ...]:
    if scope == "batch":
        return BATCH_TYPES
    if scope == "sync":
        return SYNC_TYPES
    if scope == "daily":
        # 日报以工时数据为必需基准，其他类型缺失时仍可导出。
        return ("worktime",)
    raise ValueError(f"未知扫描范围: {scope}")


def scan_folder(
    folder_path: str | Path,
    *,
    scope: str = "batch",
    keywords: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """扫描目录并返回前端可直接展示的文件明细。

    返回结构：

    ``files``
        每个 Excel 文件一条记录，包含绝对路径、相对路径、识别出的类型和
        默认选择状态。未知文件的 ``types`` 为空且默认不选择。
    ``matched``
        按类型聚合的路径，兼容现有批处理和同步入口。
    ``missing``
        当前流程所需但没有识别到文件的类型。
    """
    root = Path(folder_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"输入目录不存在: {root}")

    matched: dict[str, list[str]] = {}
    records: list[dict[str, Any]] = []
    for path in _excel_files(root, recursive=scope == "batch"):
        types = classify_filename(path.name, scope=scope, keywords=keywords)
        path_str = str(path)
        for data_type in types:
            matched.setdefault(data_type, []).append(path_str)
        records.append(
            {
                "path": path_str,
                "name": path.name,
                "relative_path": str(path.relative_to(root)),
                "types": types,
                "recognized": bool(types),
                "selected": bool(types),
            }
        )

    present = set(matched)
    missing = [data_type for data_type in _expected_types(scope) if data_type not in present]
    return {"files": records, "matched": matched, "missing": missing}


def selected_paths_in_folder(
    folder_path: str | Path,
    selected_files: list[str | Path] | None,
) -> list[Path] | None:
    """校验并标准化用户选中的文件路径。

    ``None`` 表示调用方没有提供选择，保留原有自动发现行为；空列表表示
    用户明确关闭了所有文件。路径必须位于输入目录内，避免 GUI 选择参数
    被利用来读取目录外文件。
    """
    if selected_files is None:
        return None
    root = Path(folder_path).expanduser().resolve()
    result: list[Path] = []
    seen: set[Path] = set()
    for raw_path in selected_files:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file() or resolved.suffix.lower() not in EXCEL_SUFFIXES:
            raise ValueError(f"选中的文件不是支持的 Excel 文件: {raw_path}")
        if root != resolved and root not in resolved.parents:
            raise ValueError(f"选中的文件不在输入目录内: {raw_path}")
        if resolved.name.startswith("~$"):
            continue
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


__all__ = [
    "BATCH_TYPES",
    "DAILY_TYPES",
    "EXCEL_SUFFIXES",
    "SYNC_TYPES",
    "TYPE_LABELS",
    "classify_filename",
    "scan_folder",
    "selected_paths_in_folder",
]
