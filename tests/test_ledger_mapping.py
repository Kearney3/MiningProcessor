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
        # 有效记录应存在（key 已小写化）
        assert "卡车a" in ledger._search_cache
        assert "标准卡车a" in ledger._search_cache
        assert "标准卡车b" in ledger._search_cache

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
    def test_id_and_name_must_agree(self, std_ledger):
        """编号和名称同时存在时必须一致才命中，名称不存在则回退名称也失败"""
        result = std_ledger.match_device(name="不存在", device_id="002")
        assert result is None

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


@pytest.fixture
def case_sensitive_ledger(tmp_path):
    """创建包含英文设备编号的台账，用于测试大小写不敏感匹配"""
    df = pd.DataFrame({
        "设备名称": ["NTE240 #1101", "EX5600 EX#0123"],
        "设备编号": ["HT#1101", "EX#0123"],
        "公司": ["A公司", "B公司"],
        "标准设备名称": ["NTE240 HT#1101", "HITACHI EX5600 EX#0123"],
        "标准设备编号": ["HT#1101", "EX#0123"],
        "标准公司名称": ["A公司", "B公司"],
    })
    path = str(tmp_path / "case_ledger.xlsx")
    df.to_excel(path, index=False)
    ledger = EquipmentLedger()
    ledger.load(path)
    return ledger


class TestCaseInsensitiveMatch:
    """测试大小写不敏感匹配"""

    def test_name_match_upper_vs_lower(self, case_sensitive_ledger):
        """台账有 'NTE240 #1101'，查询 'nte240 #1101' 应命中"""
        result = case_sensitive_ledger.match("nte240 #1101")
        assert result is not None
        assert result["标准名称"] == "NTE240 HT#1101"

    def test_name_match_lower_vs_upper(self, case_sensitive_ledger):
        """台账有 'NTE240 #1101'，查询 'NTE240 #1101' 应命中"""
        result = case_sensitive_ledger.match("NTE240 #1101")
        assert result is not None
        assert result["标准名称"] == "NTE240 HT#1101"

    def test_name_match_mixed_case(self, case_sensitive_ledger):
        """台账有 'EX5600 EX#0123'，查询 'ex5600 ex#0123' 应命中"""
        result = case_sensitive_ledger.match("ex5600 ex#0123")
        assert result is not None
        assert result["标准名称"] == "HITACHI EX5600 EX#0123"

    def test_id_match_upper_vs_lower(self, case_sensitive_ledger):
        """台账有 'HT#1101'，查询 'ht#1101' 应命中"""
        result = case_sensitive_ledger.match_by_id("ht#1101")
        assert result is not None
        assert result["标准设备名称"] == "NTE240 HT#1101"

    def test_id_match_lower_vs_upper(self, case_sensitive_ledger):
        """台账有 'EX#0123'，查询 'EX#0123' 应命中"""
        result = case_sensitive_ledger.match_by_id("EX#0123")
        assert result is not None
        assert result["标准设备名称"] == "HITACHI EX5600 EX#0123"

    def test_id_match_mixed_case(self, case_sensitive_ledger):
        """台账有 'EX#0123'，查询 'Ex#0123' 应命中"""
        result = case_sensitive_ledger.match_by_id("Ex#0123")
        assert result is not None
        assert result["标准设备名称"] == "HITACHI EX5600 EX#0123"

    def test_device_match_id_without_name_fails(self, case_sensitive_ledger):
        """没有设备名称时不能仅凭大小写混合的编号命中"""
        result = case_sensitive_ledger.match_device(name=None, device_id="ht#1101")
        assert result is None

    def test_device_match_name_case_insensitive(self, case_sensitive_ledger):
        """match_device 名称大小写混合应命中"""
        result = case_sensitive_ledger.match_device(name="nte240 #1101", device_id=None)
        assert result is not None
        assert result["标准设备名称"] == "NTE240 HT#1101"

    def test_device_match_fallback_name_case_insensitive(self, case_sensitive_ledger):
        """match_device 编号未命中时回退到名称匹配，名称大小写不敏感"""
        result = case_sensitive_ledger.match_device(
            name="ex5600 ex#0123", device_id="nonexistent"
        )
        assert result is not None
        assert result["标准设备名称"] == "HITACHI EX5600 EX#0123"

    def test_std_name_lookup_case_insensitive(self, case_sensitive_ledger):
        """match_device 通过名称匹配后，_name_to_info 反查应大小写不敏感"""
        # 通过名称匹配，内部需要从标准名称反查完整信息
        result = case_sensitive_ledger.match_device(name="ex5600 ex#0123")
        assert result is not None
        assert result["标准设备编号"] == "EX#0123"
        assert result["标准公司名称"] == "B公司"


class TestExtractDeviceModelCaseInsensitive:
    """测试 extract_device_model 大小写不敏感"""

    def test_uppercase_prefix(self):
        from func.maintenance_utils import extract_device_model
        assert extract_device_model("HITACHI EX5600 EX#0123") == "HITACHI EX5600"

    def test_lowercase_prefix(self):
        from func.maintenance_utils import extract_device_model
        assert extract_device_model("HITACHI EX5600 ex#0123") == "HITACHI EX5600"

    def test_mixed_case_prefix(self):
        from func.maintenance_utils import extract_device_model
        assert extract_device_model("CAT D8T Dz#0168") == "CAT D8T"

    def test_no_match_returns_original(self):
        from func.maintenance_utils import extract_device_model
        assert extract_device_model("无编号设备") == "无编号设备"


@pytest.fixture
def ambiguous_ledger(tmp_path):
    """创建包含歧义名称的台账：同一原始名称映射到不同标准名称"""
    df = pd.DataFrame({
        "设备名称": ["卡车A", "卡车A", "挖掘机B"],
        "设备编号": ["001", "002", "003"],
        "公司": ["公司甲", "公司乙", "公司丙"],
        "标准设备名称": ["标准卡车A1", "标准卡车A2", "标准挖掘机B"],
        "标准设备编号": ["S001", "S002", "S003"],
        "标准公司名称": ["标准公司甲", "标准公司乙", "标准公司丙"],
    })
    path = str(tmp_path / "ambiguous.xlsx")
    df.to_excel(path, index=False)
    ledger = EquipmentLedger()
    ledger.load(path)
    return ledger


@pytest.fixture
def duplicate_ledger(tmp_path):
    """创建包含重复名称的台账：同一原始名称映射到相同标准名称"""
    df = pd.DataFrame({
        "设备名称": ["卡车A", "卡车A", "挖掘机B"],
        "设备编号": ["001", "002", "003"],
        "公司": ["公司甲", "公司乙", "公司丙"],
        "标准设备名称": ["标准卡车A", "标准卡车A", "标准挖掘机B"],
        "标准设备编号": ["S001", "S002", "S003"],
        "标准公司名称": ["标准公司甲", "标准公司乙", "标准公司丙"],
    })
    path = str(tmp_path / "duplicate.xlsx")
    df.to_excel(path, index=False)
    ledger = EquipmentLedger()
    ledger.load(path)
    return ledger


class TestMatchDeviceIdNameCombined:
    """测试编号+名称组合匹配"""

    def test_id_and_name_agree(self, std_ledger):
        """编号和名称都匹配且结果一致 → 命中"""
        result = std_ledger.match_device(name="卡车A", device_id="001")
        assert result is not None
        assert result["标准设备名称"] == "标准卡车A"
        assert result["标准设备编号"] == "S001"

    def test_name_ambiguity_is_resolved_by_id(self, ambiguous_ledger):
        """名称本身有歧义时，编号应能通过联合匹配消除歧义"""
        # "卡车A" 映射到两个标准设备，但 001 唯一对应第一条记录。
        result = ambiguous_ledger.match_device(name="卡车A", device_id="001")
        assert result is not None
        assert result["标准设备名称"] == "标准卡车A1"
        assert result["标准设备编号"] == "S001"

    def test_id_matches_name_not_found(self, std_ledger):
        """编号匹配但名称不在台账中 → 编号和名称不一致，回退名称也失败"""
        result = std_ledger.match_device(name="不存在的设备", device_id="001")
        assert result is None

    def test_id_fails_name_matches(self, std_ledger):
        """编号不匹配 → 回退到名称匹配"""
        result = std_ledger.match_device(name="卡车A", device_id="不存在")
        assert result is not None
        assert result["标准设备名称"] == "标准卡车A"

    def test_id_only_does_not_match(self, std_ledger):
        """没有设备名称时不能仅凭编号匹配"""
        result = std_ledger.match_device(name=None, device_id="001")
        assert result is None


class TestNameAmbiguity:
    """测试名称歧义处理"""

    def test_ambiguous_name_returns_none(self, ambiguous_ledger):
        """同一名称映射到不同标准记录 → 视为未命中"""
        result = ambiguous_ledger.match("卡车A")
        assert result is None

    def test_duplicate_name_returns_match(self, duplicate_ledger):
        """同一名称但标准设备编号不同 → 视为歧义"""
        result = duplicate_ledger.match("卡车A")
        assert result is None

    def test_unique_name_matches_normally(self, ambiguous_ledger):
        """无歧义的名称正常匹配"""
        result = ambiguous_ledger.match("挖掘机B")
        assert result is not None
        assert result["标准名称"] == "标准挖掘机B"

    def test_ambiguous_name_match_device_returns_none(self, ambiguous_ledger):
        """歧义名称通过 match_device 也应返回 None"""
        result = ambiguous_ledger.match_device(name="卡车A")
        assert result is None

    def test_duplicate_name_match_device_fails(self, duplicate_ledger):
        """名称匹配到不同标准设备编号时，match_device 应失败"""
        result = duplicate_ledger.match_device(name="卡车A")
        assert result is None

    def test_id_name_disagree_but_name_consistent(self, duplicate_ledger):
        """联合匹配失败后，名称歧义仍不能回退成功"""
        # 003 对应 "标准挖掘机B"，"卡车A" 对应 "标准卡车A"（不一致）
        # 回退到名称匹配："卡车A" 对应 S001/S002，标准编号不一致 → 失败
        result = duplicate_ledger.match_device(name="卡车A", device_id="003")
        assert result is None
