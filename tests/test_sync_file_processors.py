"""func.sync.file_processors 测试

覆盖: process_file_generic 通用包装、各处理器适配函数、错误处理。
"""
import pathlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.sync.file_processors import (
    _process_electrical_file,
    _process_fuel_file,
    _process_production_file,
    _process_work_efficiency_file,
    _summarize,
    process_file_generic,
)


# ---------------------------------------------------------------------------
# process_file_generic 测试
# ---------------------------------------------------------------------------


class TestProcessFileGeneric:
    """process_file_generic 通用包装器测试。"""

    def test_calls_processor_with_file_path_and_kwargs(self, tmp_path):
        """processor_fn 应收到 str(file_path) 和 **kwargs。"""
        fp = tmp_path / "test.xlsx"
        fp.write_bytes(b"")

        processor = MagicMock(return_value={"sheet": pd.DataFrame({"a": [1]})})

        def extract(result):
            return result.get("sheet") if result else None

        def mapper(df):
            return [{"a": v} for v in df["a"]]

        result = process_file_generic(
            fp,
            processor_fn=processor,
            sheet_extractor=extract,
            row_mapper=mapper,
            module_type="test",
            empty_result=[],
            extra_kw="value",
        )

        processor.assert_called_once_with(str(fp), extra_kw="value")
        assert result == [{"a": 1}]

    def test_returns_empty_result_when_extraction_returns_none(self, tmp_path):
        """sheet_extractor 返回 None 时，返回 empty_result。"""
        fp = tmp_path / "test.xlsx"
        fp.write_bytes(b"")

        def extract(result):
            return None  # 提取失败

        result = process_file_generic(
            fp,
            processor_fn=MagicMock(return_value={"key": "val"}),
            sheet_extractor=extract,
            row_mapper=lambda x: x,
            module_type="test",
            empty_result=[],
        )
        assert result == []

    def test_returns_empty_result_on_processor_exception(self, tmp_path):
        """processor 抛出异常时，返回 empty_result。"""
        fp = tmp_path / "fail.xlsx"
        fp.write_bytes(b"")

        result = process_file_generic(
            fp,
            processor_fn=MagicMock(side_effect=RuntimeError("boom")),
            sheet_extractor=lambda r: None,
            row_mapper=lambda x: x,
            module_type="test",
            empty_result=[],
        )
        assert result == []

    def test_returns_empty_result_as_dict_on_exception(self, tmp_path):
        """processor 抛出异常时，empty_result 可以是 dict。"""
        fp = tmp_path / "fail.xlsx"
        fp.write_bytes(b"")
        empty = {"production": [], "operation": []}

        result = process_file_generic(
            fp,
            processor_fn=MagicMock(side_effect=RuntimeError("boom")),
            sheet_extractor=lambda r: None,
            row_mapper=lambda x: x,
            module_type="test",
            empty_result=empty,
        )
        assert result == {"production": [], "operation": []}

    def test_returns_none_by_default_on_exception(self, tmp_path):
        """empty_result 默认为 None。"""
        fp = tmp_path / "fail.xlsx"
        fp.write_bytes(b"")

        result = process_file_generic(
            fp,
            processor_fn=MagicMock(side_effect=RuntimeError("boom")),
            sheet_extractor=lambda r: None,
            row_mapper=lambda x: x,
            module_type="test",
        )
        assert result is None

    def test_row_mapper_receives_extracted_data(self, tmp_path):
        """row_mapper 应收到 sheet_extractor 的返回值。"""
        fp = tmp_path / "test.xlsx"
        fp.write_bytes(b"")
        raw = {"col": [10, 20]}

        def extract(result):
            return raw if result else None

        mapper = MagicMock(return_value=[{"mapped": True}])

        result = process_file_generic(
            fp,
            processor_fn=MagicMock(return_value=raw),
            sheet_extractor=extract,
            row_mapper=mapper,
            module_type="test",
        )
        mapper.assert_called_once_with(raw)
        assert result == [{"mapped": True}]

    def test_dict_result_logged_with_summary(self, tmp_path, caplog):
        """dict 类型结果应使用 _summarize 记录各 key 的长度。"""
        fp = tmp_path / "test.xlsx"
        fp.write_bytes(b"")

        def extract(result):
            return result if result else None

        def mapper(data):
            return {"a": [1, 2], "b": [3]}

        import logging
        with caplog.at_level(logging.INFO):
            process_file_generic(
                fp,
                processor_fn=MagicMock(return_value={"x": 1}),
                sheet_extractor=extract,
                row_mapper=mapper,
                module_type="prodmod",
            )
        assert "a=2, b=1" in caplog.text

    def test_processor_kwargs_forwarded(self, tmp_path):
        """processor_kwargs 应原样传递给 processor_fn。"""
        fp = tmp_path / "test.xlsx"
        fp.write_bytes(b"")
        processor = MagicMock(return_value="data")

        process_file_generic(
            fp,
            processor_fn=processor,
            sheet_extractor=lambda r: r,
            row_mapper=lambda x: [x],
            module_type="test",
            alpha=1,
            beta="two",
            gamma=True,
        )

        processor.assert_called_once_with(str(fp), alpha=1, beta="two", gamma=True)


# ---------------------------------------------------------------------------
# _summarize 测试
# ---------------------------------------------------------------------------


class TestSummarize:
    """_summarize 辅助函数测试。"""

    def test_list_summary(self):
        assert _summarize([1, 2, 3]) == "3 行"

    def test_dict_summary(self):
        assert _summarize({"a": [1], "b": [2, 3]}) == "a=1, b=2"

    def test_fallback_to_str(self):
        assert _summarize(42) == "42"


# ---------------------------------------------------------------------------
# _process_fuel_file 测试
# ---------------------------------------------------------------------------


class TestProcessFuelFile:
    """_process_fuel_file 适配函数测试。"""

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    def test_calls_generic_with_fuel_params(self, mock_generic, mock_mapper_fn):
        """应调用 process_file_generic 并传入 fuel 相关参数。"""
        mock_generic.return_value = [{"date": "2025-01-01"}]
        fp = Path("/tmp/fuel.xlsx")

        result = _process_fuel_file(fp, year=2025)

        assert result == [{"date": "2025-01-01"}]
        mock_generic.assert_called_once()
        call_kwargs = mock_generic.call_args
        assert call_kwargs[1]["module_type"] == "fuel"
        assert call_kwargs[1]["empty_result"] == []
        assert call_kwargs[1]["target_year"] == 2025
        assert call_kwargs[1]["return_sheets"] is True

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    def test_returns_empty_on_failure(self, mock_generic, mock_mapper_fn):
        """处理器失败时返回空列表。"""
        mock_generic.return_value = []
        fp = Path("/tmp/fuel.xlsx")

        result = _process_fuel_file(fp)

        assert result == []


# ---------------------------------------------------------------------------
# _process_electrical_file 测试
# ---------------------------------------------------------------------------


class TestProcessElectricalFile:
    """_process_electrical_file 适配函数测试。"""

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    def test_calls_generic_with_electrical_params(self, mock_generic, mock_mapper_fn):
        """应调用 process_file_generic 并传入 electrical 相关参数。"""
        mock_generic.return_value = [{"consumption": 100}]
        fp = Path("/tmp/elec.xlsx")

        result = _process_electrical_file(fp, year=2025)

        assert result == [{"consumption": 100}]
        mock_generic.assert_called_once()
        call_kwargs = mock_generic.call_args
        assert call_kwargs[1]["module_type"] == "electrical"
        assert call_kwargs[1]["empty_result"] == []
        assert call_kwargs[1]["add_shift_column"] is True
        assert call_kwargs[1]["default_shift"] == "Night"

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    def test_returns_empty_on_failure(self, mock_generic, mock_mapper_fn):
        mock_generic.return_value = []
        fp = Path("/tmp/elec.xlsx")

        result = _process_electrical_file(fp)

        assert result == []


# ---------------------------------------------------------------------------
# _process_production_file 测试
# ---------------------------------------------------------------------------


class TestProcessProductionFile:
    """_process_production_file 适配函数测试。"""

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    def test_calls_generic_with_production_params(self, mock_generic, mock_mapper_fn):
        """应调用 process_file_generic 并返回 production + operation 字典。"""
        expected = {"production": [{"p": 1}], "operation": [{"o": 2}]}
        mock_generic.return_value = expected
        fp = Path("/tmp/prod.xlsx")

        result = _process_production_file(fp)

        assert result == expected
        mock_generic.assert_called_once()
        call_kwargs = mock_generic.call_args
        assert call_kwargs[1]["module_type"] == "production"
        assert call_kwargs[1]["empty_result"] == {"production": [], "operation": []}

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    def test_returns_empty_dicts_on_failure(self, mock_generic, mock_mapper_fn):
        """处理器失败时返回空 production/operation 字典。"""
        mock_generic.return_value = {"production": [], "operation": []}
        fp = Path("/tmp/prod.xlsx")

        result = _process_production_file(fp)

        assert result == {"production": [], "operation": []}


# ---------------------------------------------------------------------------
# _process_work_efficiency_file 测试
# ---------------------------------------------------------------------------


class TestProcessWorkEfficiencyFile:
    """_process_work_efficiency_file 适配函数测试。"""

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.sync.file_processors.process_file_generic")
    @patch("func.config_loader.get_minebase_column_mapping")
    def test_uses_generic_when_year_month_provided(
        self, mock_config, mock_generic, mock_mapper_fn
    ):
        """有 year/month 时优先用 process_file_generic 路径。"""
        mock_config.return_value = {"work_efficiency": {"日期": "date"}}
        mock_mapper_fn.return_value = lambda df, m: [{"date": "2025-01-01"}]
        mock_generic.return_value = [{"date": "2025-01-01"}]
        fp = Path("/tmp/work.xlsx")

        result = _process_work_efficiency_file(fp, year=2025, month=1)

        assert result == [{"date": "2025-01-01"}]
        mock_generic.assert_called_once()

    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.config_loader.get_minebase_column_mapping")
    def test_returns_empty_when_mapping_missing(self, mock_config, mock_mapper_fn):
        """映射配置为空时直接返回空列表。"""
        mock_config.return_value = {}
        fp = Path("/tmp/work.xlsx")

        result = _process_work_efficiency_file(fp)

        assert result == []

    @patch("pandas.read_excel")
    @patch("func.sync.file_processors._get_df_to_mapped_rows")
    @patch("func.config_loader.get_minebase_column_mapping")
    def test_fallback_to_direct_read_when_no_year_month(
        self, mock_config, mock_mapper_fn, mock_read
    ):
        """无 year/month 时回退到直接读取 Excel。"""
        mock_config.return_value = {"work_efficiency": {"设备名称": "equipmentName"}}
        df = pd.DataFrame({"设备名称": ["Excavator-01"]})
        mock_read.return_value = df
        mock_mapper_fn.return_value = lambda d, m: [{"equipmentName": "Excavator-01"}]
        fp = Path("/tmp/work.xlsx")

        result = _process_work_efficiency_file(fp, apply_header_mapping=False)

        assert result == [{"equipmentName": "Excavator-01"}]
        mock_read.assert_called_once_with(fp, sheet_name=0)
