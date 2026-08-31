"""维修记录提取工具测试。"""

from datetime import date

from func.maintenance_utils import parse_comment


def test_parse_comment_normalizes_day_and_night_shifts():
    assert parse_comment("白班：更换滤芯\n夜班: 检查液压油") == [
        ("day", "更换滤芯"),
        ("night", "检查液压油"),
    ]


def test_parse_comment_keeps_unmarked_shift():
    assert parse_comment("检查设备") == [("未标注", "检查设备")]


def test_maintenance_report_normalizes_chinese_shift_labels(monkeypatch, tmp_path):
    from func import excel_maintenance

    source = tmp_path / "input.xlsx"
    source.touch()
    records = [
        {
            "日期": date(2026, 8, 31),
            "原始设备名称": "TR001",
            "原因": "检修",
            "班次": "白班",
            "维修内容": "发动机异响",
            "工时_分钟": 30,
        },
        {
            "日期": date(2026, 8, 31),
            "原始设备名称": "TR001",
            "原因": "检修",
            "班次": "夜班",
            "维修内容": "液压油漏油",
            "工时_分钟": 30,
        },
    ]
    monkeypatch.setattr(excel_maintenance, "extract_all_records", lambda *args, **kwargs: records)

    sheets = excel_maintenance.process_maintenance_data(
        str(source),
        return_sheets=True,
        details_only=True,
    )

    assert sheets["维修明细"]["班次"].tolist() == ["day", "night"]
