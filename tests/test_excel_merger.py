"""excel_merger 模块测试"""
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.excel_merger import find_first_datetime_column, merge_excel_files


class TestFindFirstDatetimeColumn:
    def test_returns_datetime_column(self):
        df = pd.DataFrame({
            "名称": ["a", "b"],
            "日期": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "数值": [1, 2],
        })
        result = find_first_datetime_column(df)
        assert result == "日期"

    def test_returns_none_for_empty_df(self):
        df = pd.DataFrame()
        result = find_first_datetime_column(df)
        assert result is None

    def test_returns_first_if_multiple(self):
        df = pd.DataFrame({
            "创建时间": pd.to_datetime(["2025-01-01"]),
            "更新时间": pd.to_datetime(["2025-01-02"]),
        })
        result = find_first_datetime_column(df)
        assert result == "创建时间"

    def test_handles_string_dates(self):
        """字符串格式的日期也应被识别"""
        df = pd.DataFrame({"日期": ["2025-01-01", "2025-02-01"], "值": [1, 2]})
        result = find_first_datetime_column(df)
        assert result == "日期"

    def test_skips_all_nan_column(self):
        df = pd.DataFrame({
            "空列": [None, None],
            "日期": pd.to_datetime(["2025-01-01", "2025-01-02"]),
        })
        result = find_first_datetime_column(df)
        assert result == "日期"

    def test_integer_column_not_parsed_as_datetime(self):
        """纯整数列不应被误判为日期列"""
        df = pd.DataFrame({"数值": [1, 2, 3]})
        result = find_first_datetime_column(df)
        assert result is None


def _make_excel(path, data_dict, sheet_name="Sheet1"):
    """辅助：创建简单 Excel 文件"""
    df = pd.DataFrame(data_dict)
    df.to_excel(path, sheet_name=sheet_name, index=False)


class TestMergeExcelFiles:
    def test_merges_two_files(self, tmp_path):
        _make_excel(tmp_path / "数据_A.xlsx", {"日期": ["2025-01-01", "2025-01-02"], "值": [10, 20]})
        _make_excel(tmp_path / "数据_B.xlsx", {"日期": ["2025-01-03"], "值": [30]})

        out = merge_excel_files(str(tmp_path), "数据")
        assert pathlib.Path(out).exists()

        result = pd.read_excel(out)
        assert len(result) == 3

    def test_excludes_non_matching_files(self, tmp_path):
        _make_excel(tmp_path / "数据_A.xlsx", {"日期": ["2025-01-01"], "值": [1]})
        _make_excel(tmp_path / "其他_B.xlsx", {"日期": ["2025-01-02"], "值": [2]})

        out = merge_excel_files(str(tmp_path), "数据")
        result = pd.read_excel(out)
        assert len(result) == 1

    def test_excludes_merged_output_files(self, tmp_path):
        """_合并.xlsx 文件应被排除"""
        _make_excel(tmp_path / "数据_A.xlsx", {"日期": ["2025-01-01"], "值": [1]})
        _make_excel(tmp_path / "数据_合并.xlsx", {"日期": ["2025-01-02"], "值": [99]})

        out = merge_excel_files(str(tmp_path), "数据")
        result = pd.read_excel(out)
        assert len(result) == 1
        assert result["值"].iloc[0] == 1

    def test_raises_on_no_matching_files(self, tmp_path):
        _make_excel(tmp_path / "其他.xlsx", {"值": [1]})
        with pytest.raises(FileNotFoundError, match="未找到"):
            merge_excel_files(str(tmp_path), "不存在")

    def test_strip_time(self, tmp_path):
        _make_excel(tmp_path / "数据_A.xlsx", {"日期": ["2025-01-01 08:00:00"], "值": [1]})

        out = merge_excel_files(str(tmp_path), "数据", strip_time=True)
        result = pd.read_excel(out)
        # strip_time 后日期应为纯日期
        date_val = str(result["日期"].iloc[0])
        assert "08:00" not in date_val

    def test_sort_configs(self, tmp_path):
        _make_excel(tmp_path / "数据_A.xlsx", {"日期": ["2025-01-03", "2025-01-01"], "值": [30, 10]})
        _make_excel(tmp_path / "数据_B.xlsx", {"日期": ["2025-01-02"], "值": [20]})

        out = merge_excel_files(
            str(tmp_path), "数据",
            sort_configs=[{"column": "日期", "ascending": True}],
        )
        result = pd.read_excel(out)
        dates = result["日期"].tolist()
        assert dates == sorted(dates)

    def test_sort_descending(self, tmp_path):
        _make_excel(tmp_path / "数据_A.xlsx", {"值": [1, 3]})
        _make_excel(tmp_path / "数据_B.xlsx", {"值": [2]})

        out = merge_excel_files(
            str(tmp_path), "数据",
            sort_configs=[{"column": "值", "ascending": False}],
        )
        result = pd.read_excel(out)
        assert result["值"].iloc[0] == 3

    def test_header_mismatch_raises(self, tmp_path):
        """表头不一致应报错"""
        _make_excel(tmp_path / "数据_A.xlsx", {"日期": ["2025-01-01"], "值": [1]})
        _make_excel(tmp_path / "数据_B.xlsx", {"时间": ["2025-01-02"], "金额": [2]})

        with pytest.raises(ValueError, match="表头不一致"):
            merge_excel_files(str(tmp_path), "数据")

    def test_custom_output_path(self, tmp_path):
        _make_excel(tmp_path / "数据_A.xlsx", {"值": [1]})
        custom_out = str(tmp_path / "custom_out.xlsx")

        result_path = merge_excel_files(str(tmp_path), "数据", output_file=custom_out)
        assert result_path == custom_out
        assert pathlib.Path(custom_out).exists()

    def test_keyword_case_insensitive(self, tmp_path):
        """关键字匹配应不区分大小写"""
        _make_excel(tmp_path / "Report_A.xlsx", {"值": [1]})
        _make_excel(tmp_path / "report_B.xlsx", {"值": [2]})

        out = merge_excel_files(str(tmp_path), "report")
        result = pd.read_excel(out)
        assert len(result) == 2

    def test_multiple_sheets(self, tmp_path):
        """多个 sheet 合并"""
        df1 = pd.DataFrame({"值": [1]})
        df2 = pd.DataFrame({"值": [2]})
        with pd.ExcelWriter(tmp_path / "数据_A.xlsx") as w:
            df1.to_excel(w, sheet_name="表1", index=False)
            df1.to_excel(w, sheet_name="表2", index=False)
        with pd.ExcelWriter(tmp_path / "数据_B.xlsx") as w:
            df2.to_excel(w, sheet_name="表1", index=False)
            df2.to_excel(w, sheet_name="表2", index=False)

        out = merge_excel_files(str(tmp_path), "数据")
        xl = pd.ExcelFile(out)
        assert "表1" in xl.sheet_names
        assert "表2" in xl.sheet_names
        assert len(pd.read_excel(out, sheet_name="表1")) == 2
