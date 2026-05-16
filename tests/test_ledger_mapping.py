"""设备台账列映射功能测试"""
import pytest
import pandas as pd
from pathlib import Path
from func.equipment_ledger import EquipmentLedger, LEDGER_COLUMNS


@pytest.fixture
def sample_excel(tmp_path):
    """创建一个带非标准列名的测试 Excel 文件"""
    df = pd.DataFrame({
        "Name": ["卡车A", "卡车B", "挖掘机C"],
        "ID": ["001", "002", "003"],
        "Company": ["公司甲", "公司乙", "公司丙"],
        "StdName": ["标准卡车A", "标准卡车B", "标准挖掘机C"],
        "StdID": ["S001", "S002", "S003"],
        "StdCompany": ["标准公司甲", "标准公司乙", "标准公司丙"],
    })
    path = str(tmp_path / "test_ledger.xlsx")
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def sample_excel_no_header(tmp_path):
    """创建一个第一行不是标题的测试 Excel 文件"""
    df = pd.DataFrame({
        0: ["设备名称", "卡车A", "卡车B"],
        1: ["设备编号", "001", "002"],
        2: ["公司", "公司甲", "公司乙"],
        3: ["标准设备名称", "标准卡车A", "标准卡车B"],
        4: ["标准设备编号", "S001", "S002"],
        5: ["标准公司", "标准公司甲", "标准公司乙"],
    })
    path = str(tmp_path / "test_no_header.xlsx")
    df.to_excel(path, index=False, header=False)
    return path


class TestLedgerColumns:
    def test_ledger_columns_has_six_entries(self):
        assert len(LEDGER_COLUMNS) == 6

    def test_ledger_columns_content(self):
        assert LEDGER_COLUMNS == [
            "设备名称", "设备编号", "公司",
            "标准设备名称", "标准设备编号", "标准公司名称",
        ]


class TestLoadWithMapping:
    def test_load_with_column_mapping(self, sample_excel):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Name",
            "设备编号": "ID",
            "公司": "Company",
            "标准设备名称": "StdName",
            "标准设备编号": "StdID",
            "标准公司": "StdCompany",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        records = ledger.to_dict()
        assert len(records) == 3
        assert records[0]["设备名称"] == "卡车A"
        assert records[0]["标准设备名称"] == "标准卡车A"
        assert records[0]["公司"] == "公司甲"

    def test_load_without_mapping_uses_original_columns(self, sample_excel):
        ledger = EquipmentLedger()
        ledger.load(sample_excel)
        records = ledger.to_dict()
        assert len(records) == 3
        assert "Name" in records[0]

    def test_load_partial_mapping(self, sample_excel):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Name",
            "标准设备名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        records = ledger.to_dict()
        assert records[0]["设备名称"] == "卡车A"
        assert records[0]["标准设备名称"] == "标准卡车A"
        assert "ID" in records[0]


class TestLoadSkipHeader:
    def test_skip_header_false(self, sample_excel_no_header):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Col0",
            "设备编号": "Col1",
            "公司": "Col2",
            "标准设备名称": "Col3",
            "标准设备编号": "Col4",
            "标准公司": "Col5",
        }
        ledger.load(sample_excel_no_header, column_mapping=mapping, skip_header=False)
        records = ledger.to_dict()
        assert len(records) == 3
        assert records[0]["设备名称"] == "设备名称"

    def test_skip_header_true_uses_first_row_as_columns(self, sample_excel):
        ledger = EquipmentLedger()
        ledger.load(sample_excel, skip_header=True)
        records = ledger.to_dict()
        assert len(records) == 3
        assert records[0]["Name"] == "卡车A"


class TestMatchWithNewSchema:
    def test_match_by_raw_name(self, sample_excel):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Name",
            "标准设备名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        result = ledger.match("卡车A")
        assert result is not None
        assert result["标准名称"] == "标准卡车A"
        assert result["原始名称"] == "卡车A"

    def test_match_by_standard_name(self, sample_excel):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Name",
            "标准设备名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        result = ledger.match("标准卡车A")
        assert result is not None
        assert result["标准名称"] == "标准卡车A"

    def test_match_no_match(self, sample_excel):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Name",
            "标准设备名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        result = ledger.match("不存在的设备")
        assert result is None


class TestToDict:
    def test_to_dict_empty_ledger(self):
        ledger = EquipmentLedger()
        assert ledger.to_dict() == []

    def test_to_dict_returns_all_records(self, sample_excel):
        ledger = EquipmentLedger()
        mapping = {
            "设备名称": "Name",
            "标准设备名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        records = ledger.to_dict()
        assert len(records) == 3
        assert all(isinstance(r, dict) for r in records)


class TestEmptyCellHandling:
    def test_nan_cells_not_in_search_cache(self, tmp_path):
        """空单元格不应以 'nan' 进入搜索缓存"""
        df = pd.DataFrame({
            "设备名称": ["卡车A", None, ""],
            "标准设备名称": ["标准卡车A", "标准卡车B", None],
        })
        path = str(tmp_path / "with_nan.xlsx")
        df.to_excel(path, index=False)

        ledger = EquipmentLedger()
        ledger.load(path)
        # "nan" 不应出现在搜索缓存中
        assert "nan" not in ledger._search_cache
        # 有效记录应存在
        assert "卡车A" in ledger._search_cache
        assert "标准卡车A" in ledger._search_cache
        assert "标准卡车B" in ledger._search_cache

    def test_match_skips_nan_rows(self, tmp_path):
        """match() 不应匹配到 nan 关键词"""
        df = pd.DataFrame({
            "设备名称": ["卡车A", None],
            "标准设备名称": ["标准卡车A", None],
        })
        path = str(tmp_path / "with_nan.xlsx")
        df.to_excel(path, index=False)

        ledger = EquipmentLedger()
        ledger.load(path)
        result = ledger.match("nan")
        assert result is None


class TestExportTemplate:
    def test_export_template_creates_file(self, tmp_path):
        ledger = EquipmentLedger()
        out_path = str(tmp_path / "template.xlsx")
        ledger.export_template(out_path)
        assert Path(out_path).exists()

    def test_export_template_has_correct_columns(self, tmp_path):
        ledger = EquipmentLedger()
        out_path = str(tmp_path / "template.xlsx")
        ledger.export_template(out_path)
        df = pd.read_excel(out_path)
        assert list(df.columns) == LEDGER_COLUMNS


@pytest.fixture
def std_ledger(tmp_path):
    """创建一个使用标准列名的设备台账"""
    df = pd.DataFrame({
        "设备名称": ["卡车A", "卡车B", "挖掘机C"],
        "设备编号": ["001", "002", "003"],
        "公司": ["公司甲", "公司乙", "公司丙"],
        "标准设备名称": ["标准卡车A", "标准卡车B", "标准挖掘机C"],
        "标准设备编号": ["S001", "S002", "S003"],
        "标准公司名称": ["标准公司甲", "标准公司乙", "标准公司丙"],
    })
    path = str(tmp_path / "std_ledger.xlsx")
    df.to_excel(path, index=False)
    ledger = EquipmentLedger()
    ledger.load(path)
    return ledger


class TestMatchById:
    def test_match_by_id_found(self, std_ledger):
        result = std_ledger.match_by_id("001")
        assert result is not None
        assert result["标准设备名称"] == "标准卡车A"
        assert result["标准设备编号"] == "S001"
        assert result["标准公司名称"] == "标准公司甲"

    def test_match_by_id_not_found(self, std_ledger):
        result = std_ledger.match_by_id("999")
        assert result is None

    def test_match_by_id_empty(self, std_ledger):
        result = std_ledger.match_by_id("")
        assert result is None


class TestMatchDevice:
    def test_match_by_id_priority(self, std_ledger):
        """编号精确匹配优先于名称模糊匹配"""
        result = std_ledger.match_device(name="不存在", device_id="002")
        assert result is not None
        assert result["标准设备名称"] == "标准卡车B"
        assert result["标准设备编号"] == "S002"

    def test_match_by_name_fallback(self, std_ledger):
        """无编号时回退到名称匹配"""
        result = std_ledger.match_device(name="卡车A", device_id=None)
        assert result is not None
        assert result["标准设备名称"] == "标准卡车A"

    def test_match_by_name_with_empty_id(self, std_ledger):
        """编号为空时回退到名称匹配"""
        result = std_ledger.match_device(name="卡车A", device_id="")
        assert result is not None
        assert result["标准设备名称"] == "标准卡车A"

    def test_match_device_no_match(self, std_ledger):
        result = std_ledger.match_device(name="不存在", device_id=None)
        assert result is None

    def test_match_device_both_none(self, std_ledger):
        result = std_ledger.match_device(name=None, device_id=None)
        assert result is None
