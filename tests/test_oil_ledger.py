"""油品台账功能测试"""
import pytest
import pandas as pd
from pathlib import Path
from func.oil_ledger import OilLedger, OIL_LEDGER_COLUMNS


@pytest.fixture
def sample_excel(tmp_path):
    """创建一个带非标准列名的测试 Excel 文件"""
    df = pd.DataFrame({
        "Name": ["0# 柴油", "92# 汽油", "液压油 A"],
        "StdName": ["0号柴油", "92号汽油", "液压油"],
    })
    path = str(tmp_path / "test_oil.xlsx")
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def sample_excel_no_header(tmp_path):
    """创建一个第一行不是标题的测试 Excel 文件"""
    df = pd.DataFrame({
        0: ["油品名称", "0# 柴油", "92# 汽油"],
        1: ["标准油品名称", "0号柴油", "92号汽油"],
    })
    path = str(tmp_path / "test_no_header.xlsx")
    df.to_excel(path, index=False, header=False)
    return path


class TestOilLedgerColumns:
    def test_oil_ledger_columns_has_two_entries(self):
        assert len(OIL_LEDGER_COLUMNS) == 2

    def test_oil_ledger_columns_content(self):
        assert OIL_LEDGER_COLUMNS == ["油品名称", "标准油品名称"]


class TestLoadWithMapping:
    def test_load_with_column_mapping(self, sample_excel):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Name",
            "标准油品名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        records = ledger.to_dict()
        assert len(records) == 3
        assert records[0]["油品名称"] == "0# 柴油"
        assert records[0]["标准油品名称"] == "0号柴油"

    def test_load_without_mapping_uses_original_columns(self, sample_excel):
        ledger = OilLedger()
        ledger.load(sample_excel)
        records = ledger.to_dict()
        assert len(records) == 3
        assert "Name" in records[0]

    def test_load_partial_mapping(self, sample_excel):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Name",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        records = ledger.to_dict()
        assert records[0]["油品名称"] == "0# 柴油"
        assert "StdName" in records[0]


class TestLoadSkipHeader:
    def test_skip_header_false(self, sample_excel_no_header):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Col0",
            "标准油品名称": "Col1",
        }
        ledger.load(sample_excel_no_header, column_mapping=mapping, skip_header=False)
        records = ledger.to_dict()
        assert len(records) == 3
        assert records[0]["油品名称"] == "油品名称"

    def test_skip_header_true_uses_first_row_as_columns(self, sample_excel):
        ledger = OilLedger()
        ledger.load(sample_excel, skip_header=True)
        records = ledger.to_dict()
        assert len(records) == 3
        assert records[0]["Name"] == "0# 柴油"


class TestMatchWithNewSchema:
    def test_match_by_raw_name(self, sample_excel):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Name",
            "标准油品名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        result = ledger.match("0# 柴油")
        assert result is not None
        assert result["标准名称"] == "0号柴油"
        assert result["原始名称"] == "0# 柴油"

    def test_match_by_standard_name(self, sample_excel):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Name",
            "标准油品名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        result = ledger.match("0号柴油")
        assert result is not None
        assert result["标准名称"] == "0号柴油"

    def test_match_no_match(self, sample_excel):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Name",
            "标准油品名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        result = ledger.match("不存在的油品")
        assert result is None


class TestToDict:
    def test_to_dict_empty_ledger(self):
        ledger = OilLedger()
        assert ledger.to_dict() == []

    def test_to_dict_returns_all_records(self, sample_excel):
        ledger = OilLedger()
        mapping = {
            "油品名称": "Name",
            "标准油品名称": "StdName",
        }
        ledger.load(sample_excel, column_mapping=mapping)
        records = ledger.to_dict()
        assert len(records) == 3
        assert all(isinstance(r, dict) for r in records)


class TestEmptyCellHandling:
    def test_nan_cells_not_in_search_cache(self, tmp_path):
        """空单元格不应以 'nan' 进入搜索缓存"""
        df = pd.DataFrame({
            "油品名称": ["0# 柴油", None, ""],
            "标准油品名称": ["0号柴油", "92号汽油", None],
        })
        path = str(tmp_path / "with_nan.xlsx")
        df.to_excel(path, index=False)

        ledger = OilLedger()
        ledger.load(path)
        # "nan" 不应出现在搜索缓存中
        assert "nan" not in ledger._search_cache
        # 有效记录应存在
        assert "0# 柴油" in ledger._search_cache
        assert "0号柴油" in ledger._search_cache
        assert "92号汽油" in ledger._search_cache

    def test_match_skips_nan_rows(self, tmp_path):
        """match() 不应匹配到 nan 关键词"""
        df = pd.DataFrame({
            "油品名称": ["0# 柴油", None],
            "标准油品名称": ["0号柴油", None],
        })
        path = str(tmp_path / "with_nan.xlsx")
        df.to_excel(path, index=False)

        ledger = OilLedger()
        ledger.load(path)
        result = ledger.match("nan")
        assert result is None


class TestExportTemplate:
    def test_export_template_creates_file(self, tmp_path):
        ledger = OilLedger()
        out_path = str(tmp_path / "template.xlsx")
        ledger.export_template(out_path)
        assert Path(out_path).exists()

    def test_export_template_has_correct_columns(self, tmp_path):
        ledger = OilLedger()
        out_path = str(tmp_path / "template.xlsx")
        ledger.export_template(out_path)
        df = pd.read_excel(out_path)
        assert list(df.columns) == OIL_LEDGER_COLUMNS
