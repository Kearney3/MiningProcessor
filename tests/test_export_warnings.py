"""
测试异常行警告导出及显示增强功能。
"""
import tempfile
from pathlib import Path

import pandas as pd

from func.sync.export import export_anomaly_records_to_excel, export_warnings_to_excel
from tauri_bridge import _export_sync_anomalies, _export_sync_warnings


def test_export_warnings_to_excel_default_path():
    """测试默认导出路径生成与文件结构"""
    warnings = [
        {"data_type": "fuel", "row": 2, "field": "equipmentName", "value": "卡车-999", "message": "设备名未匹配"},
        {"data_type": "electrical", "row": 5, "field": "consumption", "value": None, "message": "数值为空"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = export_warnings_to_excel(warnings, input_dir=tmpdir)
        assert Path(out_path).exists()
        assert "异常行明细_" in out_path
        assert out_path.endswith(".xlsx")

        df = pd.read_excel(out_path)
        assert len(df) == 2
        assert list(df.columns) == ["数据类型", "行号", "字段", "原始值", "问题说明"]
        assert df.iloc[0]["原始值"] == "卡车-999"
        assert df.iloc[0]["数据类型"] == "油耗数据"
        assert df.iloc[1]["原始值"] == "（空）"


def test_export_warnings_to_excel_custom_path():
    """测试用户自定义保存位置导出"""
    warnings = [
        {"data_type": "fuel", "row": 1, "field": "device", "value": "A", "message": "msg"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        custom_path = Path(tmpdir) / "subfolder" / "custom_name.xlsx"
        out_path = export_warnings_to_excel(warnings, output_path=custom_path)
        assert out_path == str(custom_path)
        assert Path(out_path).exists()

        df = pd.read_excel(out_path)
        assert len(df) == 1


def test_tauri_bridge_export_sync_warnings():
    """测试 Tauri 接口返回结构与路径映射"""
    warnings = [
        {"data_type": "production", "row": 10, "field": "truckName", "value": "", "message": "缺少矿卡名称"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        res = _export_sync_warnings({"warnings": warnings, "input_dir": tmpdir})
        assert "output_file" in res
        out_file = res["output_file"]
        assert Path(out_file).exists()

        df = pd.read_excel(out_file)
        assert len(df) == 1
        assert df.iloc[0]["原始值"] == "（空）"
        assert df.iloc[0]["数据类型"] == "生产数据"


def test_tauri_bridge_custom_output_path():
    """测试 Tauri 接口传递自定义输出路径"""
    warnings = []

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "tauri_custom.xlsx"
        res = _export_sync_warnings({"warnings": warnings, "output_path": out_path, "input_dir": tmpdir})
        assert Path(res["output_file"]).exists()


def test_export_warning_types_mapping():
    """测试各类数据类型标签映射与序列化"""
    warnings = [
        {"data_type": "fuel", "row": 1, "field": "A", "value": 123, "message": "m1"},
        {"data_type": "electrical", "row": 2, "field": "B", "value": None, "message": "m2"},
        {"data_type": "operation", "row": 3, "field": "C", "value": "", "message": "m3"},
        {"data_type": "production", "row": 4, "field": "D", "value": None, "message": "m4"},
        {"data_type": "work_efficiency", "row": 5, "field": "E", "value": "Val", "message": "m5"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = export_warnings_to_excel(warnings, input_dir=tmpdir)
        df = pd.read_excel(out_path)

        expected_types = ["油耗数据", "电耗数据", "设备运行", "生产数据", "工作效率"]
        assert df["数据类型"].tolist() == expected_types

        # 验证空值处理
        assert df.iloc[1]["原始值"] == "（空）"
        assert df.iloc[2]["原始值"] == "（空）"
        assert df.iloc[3]["原始值"] == "（空）"


def test_export_anomaly_records_includes_locator_columns_and_reason():
    """异常值导出应保留定位列、检测方法、原因及合法的 0 值。"""
    records = [
        {
            "数据类型": "油耗信息",
            "相关字段": "油品消耗",
            "异常值": 0,
            "异常值原因": "低于下限 1",
            "行号": 8,
            "源表": "油耗信息",
            "源行号": 22,
            "检测方法": "threshold",
            "日期": "2026-08-24",
            "班次": "Day",
            "设备名称": "TR100",
            "设备编号": "TR-01",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = export_anomaly_records_to_excel(records, input_dir=tmpdir)
        assert Path(out_path).exists()
        assert "异常值检测结果_" in out_path

        df = pd.read_excel(out_path, sheet_name="异常值明细")
        assert list(df.columns) == [
            "数据类型", "相关字段", "异常值", "异常值原因", "行号", "源表", "源行号",
            "检测方法", "日期", "班次", "设备名称", "设备编号",
        ]
        assert df.iloc[0]["异常值"] == 0
        assert df.iloc[0]["检测方法"] == "threshold"
        assert df.iloc[0]["源行号"] == 22
        assert df.iloc[0]["异常值原因"] == "低于下限 1"

        summary = pd.read_excel(out_path, sheet_name="异常汇总")
        assert summary.iloc[0]["次数"] == 1


def test_tauri_bridge_export_sync_anomalies():
    """Tauri 导出 RPC 应接受异常值明细并返回输出路径。"""
    records = [{
        "数据类型": "电力消耗",
        "异常列": "电力消耗",
        "异常值": 50001,
        "说明": "超过上限 50000",
        "行号": 4,
        "检测方法": "threshold",
    }]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "anomalies.xlsx"
        res = _export_sync_anomalies({"records": records, "output_path": out_path})
        assert res["output_file"] == str(out_path)
        df = pd.read_excel(out_path, sheet_name="异常值明细")
        assert df.iloc[0]["相关字段"] == "电力消耗"
        assert df.iloc[0]["异常值原因"] == "超过上限 50000"
