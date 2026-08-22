"""统一文件扫描与人工选择路径校验测试。"""

from pathlib import Path

import pytest

from func.file_scanner import classify_filename, scan_folder, selected_paths_in_folder


def _touch(path: Path) -> Path:
    path.write_bytes(b"")
    return path


def test_batch_scan_returns_each_file_and_recognized_types(tmp_path):
    fuel = _touch(tmp_path / "Fuel report 2026.xlsx")
    electrical = _touch(tmp_path / "Цахилгааны хэлтэс 2026.xlsx")
    unknown = _touch(tmp_path / "说明.xlsx")
    _touch(tmp_path / "~$临时.xlsx")

    result = scan_folder(tmp_path, scope="batch", keywords={
        "fuel": ["Fuel report"],
        "electrical": ["Цахилгааны хэлтэс"],
        "production": [],
        "worktime": [],
    })

    by_name = {item["name"]: item for item in result["files"]}
    assert by_name[fuel.name]["types"] == ["fuel"]
    assert by_name[fuel.name]["selected"] is True
    assert by_name[electrical.name]["types"] == ["electrical"]
    assert by_name[unknown.name]["types"] == []
    assert by_name[unknown.name]["selected"] is False
    assert "production" in result["missing"]
    assert str(fuel) in result["matched"]["fuel"]
    assert "~$临时.xlsx" not in by_name


def test_sync_scan_identifies_one_merged_file_as_two_data_types(tmp_path):
    merged = _touch(tmp_path / "合并产量.xlsx")

    result = scan_folder(tmp_path, scope="sync", keywords={})

    assert result["matched"] == {
        "production": [str(merged.resolve())],
        "operation": [str(merged.resolve())],
    }
    assert result["files"][0]["types"] == ["production", "operation"]


def test_daily_scan_recognizes_standard_and_raw_report_names(tmp_path):
    worktime = _touch(tmp_path / "202608_工作效率表.xlsx")
    fuel = _touch(tmp_path / "Fuel.xlsx")
    unknown = _touch(tmp_path / "notes.xlsx")

    result = scan_folder(tmp_path, scope="daily")

    by_name = {item["name"]: item for item in result["files"]}
    assert by_name[worktime.name]["types"] == ["worktime"]
    assert by_name[fuel.name]["types"] == ["fuel"]
    assert by_name[unknown.name]["recognized"] is False

def test_selected_paths_are_limited_to_input_directory(tmp_path):
    inside = _touch(tmp_path / "Fuel.xlsx")
    outside = _touch(tmp_path.parent / "outside.xlsx")

    assert selected_paths_in_folder(tmp_path, [inside.name]) == [inside.resolve()]
    with pytest.raises(ValueError, match="不在输入目录内"):
        selected_paths_in_folder(tmp_path, [outside])


def test_classify_filename_rejects_unknown_scope():
    with pytest.raises(ValueError, match="未知扫描范围"):
        classify_filename("Fuel.xlsx", scope="unknown")
