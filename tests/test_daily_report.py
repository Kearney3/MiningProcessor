import pandas as pd

from func import daily_report as daily_report_module
from func.daily_report import (
    build_daily_report,
    export_daily_report,
    validate_daily_report_formulas,
    _match_material_statistics,
)
from func.equipment_ledger import EquipmentLedger
from func.model_ledger import ModelLedger


def _ledger(cls, records):
    ledger = cls()
    ledger._df = pd.DataFrame(records)
    ledger._build_search_cache()
    return ledger


def _write_sources(root):
    worktime = pd.DataFrame([
        {
            "日期": "2026-08-10", "班次": "Day", "设备名称": "原挖机", "设备编号": "1", "公司": "原公司",
            "应运行分钟": 600, "计划维修/润滑": 60, "未计划/故障": 40, "转移": 10,
            "挖机场地推土/清理墙壁": 20, "等待装货": 30, "待命": 5,
            "爆破": 0, "柴油": 0, "因天气：大风暴，雨，雪": 0, "扬尘：洒水车不足": 0,
            "排队/装水": 0, "因电力原因停车/计划": 0, "因电力原因停车/未计划": 0,
            "总产量生产运行分钟": 400, "备注": "ok",
        },
        {
            "日期": "2026-08-10", "班次": "Day", "设备名称": "原矿卡", "设备编号": "2", "公司": "原公司",
            "应运行分钟": 600, "总产量生产运行分钟": 300,
        },
    ])
    operation = pd.DataFrame([
        {"日期": "2026-08-10", "班次": "Day", "设备名称": "原挖机", "设备编号": "1",
         "小时数仪表开始": 100, "小时数仪表结束": 110, "运行小时数": 8,
         "公里数仪表开始": 2, "公里数仪表结束": 22, "运行里程": 20},
        {"日期": "2026-08-10", "班次": "Day", "设备名称": "原矿卡", "设备编号": "2",
         "小时数仪表开始": 50, "小时数仪表结束": 58, "运行小时数": 7,
         "公里数仪表开始": 10, "公里数仪表结束": 50, "运行里程": 40},
    ])
    production = pd.DataFrame([
        {"日期": "2026-08-10", "班次": "Day", "矿卡名称": "原矿卡", "挖机名称": "原挖机",
         "矿石类型": "Нүүрс", "运次": 2, "产量": 100},
        {"日期": "2026-08-10", "班次": "Day", "矿卡名称": "原矿卡", "挖机名称": "原挖机",
         "矿石类型": "未配置物料", "运次": 9, "产量": 999},
    ])
    fuel = pd.DataFrame([{"日期": "2026-08-10", "班次": "Day", "设备名称": "原挖机", "设备编号": "1", "油品消耗": 10}])
    electrical = pd.DataFrame([{"日期": "2026-08-10", "班次": "Day", "设备名称": "原矿卡", "设备编号": "2", "电力消耗": 20}])
    worktime.to_excel(root / "202608_工作效率表.xlsx", sheet_name="工时数据", index=False)
    with pd.ExcelWriter(root / "合并产量.xlsx") as writer:
        operation.to_excel(writer, sheet_name="运行数据", index=False)
        production.to_excel(writer, sheet_name="生产数据", index=False)
    fuel.to_excel(root / "Fuel.xlsx", sheet_name="油耗信息", index=False)
    electrical.to_excel(root / "电力消耗统计.xlsx", sheet_name="电力消耗", index=False)


def test_daily_report_uses_worktime_devices_and_expands_production(tmp_path):
    _write_sources(tmp_path)
    equipment = _ledger(EquipmentLedger, [
        {"设备名称": "原挖机", "设备编号": "1", "公司": "原公司", "标准设备名称": "标准挖机",
         "标准设备编号": "HT#1", "标准公司名称": "标准公司"},
        {"设备名称": "原矿卡", "设备编号": "2", "公司": "原公司", "标准设备名称": "标准矿卡",
         "标准设备编号": "HT#2", "标准公司名称": "标准公司"},
    ])
    model = _ledger(ModelLedger, [
        {"标准设备编号": "HT#1", "标准公司名称": "型号公司", "所有权": "自有", "设备型号": "EX",
         "设备类型": "挖机", "内部分类": "采矿"},
        {"标准设备编号": "HT#2", "标准公司名称": "型号公司", "所有权": "租赁", "设备型号": "TR",
         "设备类型": "矿卡", "内部分类": "运输"},
    ])
    result = build_daily_report(tmp_path, "2026-08-10", "2026-08-10",
                                equipment_ledger=equipment, model_ledger=model)
    assert len(result.report) == 2
    assert list(result.report.columns[:13]) == [
        "日期", "班次", "原始设备名称", "标准设备名称", "原始设备编号",
        "标准设备编号", "原始公司名称", "标准公司名称", "所有权", "设备型号",
        "设备类型", "内部分类", "产量",
    ]
    assert "能耗" in result.report.columns and "能耗单位" in result.report.columns
    excavator = result.report[result.report["标准设备编号"] == "HT#1"].iloc[0]
    truck = result.report[result.report["标准设备编号"] == "HT#2"].iloc[0]
    assert excavator["焦煤"] == 100
    assert truck["焦煤"] == 100
    assert excavator["产量"] == 1099 and excavator["趟次"] == 11
    assert excavator["Нүүрс产量"] == 100 and excavator["Нүүрс趟次"] == 2
    assert excavator["未配置物料产量"] == 999 and excavator["未配置物料趟次"] == 9
    assert truck["能耗"] == 20 and truck["能耗单位"] == "kWh"
    assert excavator["能耗"] == 10 and excavator["能耗单位"] == "L"
    assert excavator["标准公司名称"] == "型号公司"
    assert excavator["设备型号"] == "EX"
    assert excavator["延迟时间"] == 60
    assert excavator["待机时间"] == 5
    assert round(excavator["设备可动率"], 6) == round(500 / 600, 6)
    assert round(excavator["设备可动利用率"], 6) == round(460 / 500, 6)
    assert round(excavator["设备利用率"], 6) == round(460 / 600, 6)
    assert any(
        item["数据类型"] == "生产数据" and "未归入其他" in item["消息"]
        for item in result.warnings
    )


def test_daily_report_export_has_warning_sheet(tmp_path):
    _write_sources(tmp_path)
    output = tmp_path / "每日.xlsx"
    result = export_daily_report(tmp_path, output, "2026-08-10", "2026-08-10")
    assert output.exists()
    assert len(result.warnings) == 1
    assert result.warnings[0]["值"] == "未配置物料"
    assert set(pd.ExcelFile(output).sheet_names) == {"日报", "匹配警告"}


def test_daily_report_export_can_include_detail_sheets_and_runtime_identity_options(tmp_path):
    _write_sources(tmp_path)
    output = tmp_path / "每日分项.xlsx"
    result = export_daily_report(
        tmp_path,
        output,
        "2026-08-10",
        "2026-08-10",
        config={
            "include_raw_equipment_name": False,
            "include_raw_equipment_code": False,
            "include_raw_company_name": False,
        },
        include_detail_sheets=True,
    )

    assert set(result.detail_sheets) == {"工时统计", "运行统计", "生产统计", "油耗统计", "电耗统计"}
    assert set(pd.ExcelFile(output).sheet_names) == {
        "日报", "工时统计", "运行统计", "生产统计", "油耗统计", "电耗统计", "匹配警告",
    }
    report = pd.read_excel(output, sheet_name="日报")
    assert "原始设备名称" not in report.columns
    assert "原始设备编号" not in report.columns
    assert "原始公司名称" not in report.columns


def test_daily_report_formula_validation_rejects_unknown_names_and_bad_syntax():
    valid = {
        "延迟时间": "transfer+auxiliary_work+waiting_load",
        "待机时间": "blasting+refueling+standby+weather_snow+weather_dust+fill_water+power_issue_planned+power_issue_unplanned",
        "设备可动率": "(planned_minutes-planned_maintenance-unplanned_fault)/planned_minutes",
        "设备可动利用率": "planned_minutes>0?total_production_minutes/planned_minutes:0",
        "设备利用率": "planned_minutes>0?total_production_minutes/planned_minutes:0",
    }
    assert validate_daily_report_formulas(valid) == {}
    invalid = dict(valid, 延迟时间="transfer+not_mapped", 待机时间="transfer+", 设备可动率="")
    errors = validate_daily_report_formulas(invalid)
    assert "not_mapped" in errors["延迟时间"]
    assert "语法错误" in errors["待机时间"]
    assert errors["设备可动率"] == "公式不能为空"


def test_daily_report_formula_validation_checks_actual_worktime_fields():
    formulas = {
        "延迟时间": "transfer",
        "待机时间": "standby",
        "设备可动率": "planned_minutes/planned_minutes",
        "设备可动利用率": "total_production_minutes/planned_minutes",
        "设备利用率": "planned_minutes/planned_minutes",
    }
    errors = validate_daily_report_formulas(formulas, available_columns=["转移", "待命"])

    assert errors["设备可动率"] == "公式字段不存在于工时表头: planned_minutes"
    assert errors["设备可动利用率"] == "公式字段不存在于工时表头: planned_minutes, total_production_minutes"
    assert errors["设备利用率"] == "公式字段不存在于工时表头: planned_minutes"


def test_material_statistics_keywords_match_once_in_config_order():
    mappings = [("焦煤", ["coal"]), ("动力煤", ["coal"])]
    assert _match_material_statistics("raw-coal-material", mappings) == "焦煤"
    assert _match_material_statistics("石料", mappings) is None


def test_daily_report_preprocesses_raw_worktime_fixture(tmp_path, monkeypatch):
    """日报入口应能先处理按日期 Sheet 存放的原始工效表。"""
    source = tmp_path / "2026.08 Tsag Ashiglalt. August工作效率表.xlsx"
    source_files = {
        "worktime": [],
        "operation": [],
        "production": [],
        "fuel": [],
        "electrical": [],
        "raw_worktime": [source],
        "raw_production": [],
        "raw_fuel": [],
        "raw_electrical": [],
    }
    worktime = pd.DataFrame([
        {
            "日期": "2026-08-10",
            "班次": "Day",
            "设备名称": "模拟设备",
            "设备编号": "1",
            "公司": "模拟公司",
            "应运行分钟": 600,
            "计划维修/润滑": 0,
            "未计划/故障": 0,
            "总产量生产运行分钟": 400,
            "转移": 0,
            "待命": 0,
        },
    ])
    calls = []

    def fake_process_excel_data(file_path, year, month, **kwargs):
        calls.append((file_path, year, month, kwargs))
        return {"工时数据": worktime}

    monkeypatch.setattr(daily_report_module, "_source_files", lambda _: source_files)
    monkeypatch.setattr("func.excel_worktime.process_excel_data", fake_process_excel_data)
    monkeypatch.setattr(pd, "ExcelFile", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("该测试不应读取真实 Excel 文件")
    ))

    result = build_daily_report(tmp_path, "2026-08-10", "2026-08-10")

    assert len(result.report) > 0
    assert set(result.report["日期"].astype(str)) == {"2026-08-10"}
    assert {"原始设备名称", "应运行分钟", "转移"}.issubset(result.report.columns)
    assert len(calls) == 1
    file_path, year, month, kwargs = calls[0]
    assert file_path == str(source)
    assert (year, month) == (2026, 8)
    assert kwargs["return_sheets"] is True
    assert kwargs["skip_hidden_rows"] is False
    assert kwargs["skip_hidden_cols"] is False
