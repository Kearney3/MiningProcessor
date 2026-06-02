"""
测试字符串清理工具模块
"""
import pytest
import pandas as pd
import numpy as np

from func.string_utils import clean_string, clean_pandas_strings


class TestCleanString:
    """测试 clean_string 函数"""

    # --- 基本清理 ---

    def test_none_returns_empty(self):
        assert clean_string(None) == ""

    def test_nan_returns_empty(self):
        assert clean_string(np.nan) == ""

    def test_na_returns_empty(self):
        assert clean_string(pd.NA) == ""

    def test_nat_returns_empty(self):
        assert clean_string(pd.NaT) == ""

    def test_empty_string(self):
        assert clean_string("") == ""

    def test_whitespace_only(self):
        assert clean_string("   ") == ""

    # --- 两端空格 ---

    def test_leading_spaces(self):
        assert clean_string("  hello") == "hello"

    def test_trailing_spaces(self):
        assert clean_string("hello  ") == "hello"

    def test_both_sides_spaces(self):
        assert clean_string("  hello  ") == "hello"

    def test_leading_trailing_tabs(self):
        assert clean_string("\thello\t") == "hello"

    def test_leading_trailing_newlines(self):
        assert clean_string("\nhello\n") == "hello"

    # --- 内部换行 ---

    def test_internal_newline_lf(self):
        assert clean_string("hello\nworld") == "hello world"

    def test_internal_newline_cr(self):
        assert clean_string("hello\rworld") == "hello world"

    def test_internal_newline_crlf(self):
        assert clean_string("hello\r\nworld") == "hello world"

    def test_multiple_newlines(self):
        assert clean_string("a\n\n\nb") == "a b"

    # --- 内部制表符 ---

    def test_internal_tab(self):
        assert clean_string("hello\tworld") == "hello world"

    def test_multiple_tabs(self):
        assert clean_string("a\t\t\tb") == "a b"

    # --- 连续空格合并 ---

    def test_multiple_spaces_collapsed(self):
        assert clean_string("hello    world") == "hello world"

    def test_mixed_whitespace(self):
        assert clean_string("hello \t \n world") == "hello world"

    # --- 组合场景 ---

    def test_real_world_excel_cell(self):
        """模拟 Excel 单元格常见的脏数据"""
        assert clean_string("  NTE240 #1101\n  ") == "NTE240 #1101"

    def test_multiline_cell_content(self):
        """模拟多行文本合并为单行"""
        assert clean_string("第一行\n第二行\n第三行") == "第一行 第二行 第三行"

    def test_tab_separated_values(self):
        assert clean_string("A\tB\tC") == "A B C"

    def test_mixed_all_whitespace(self):
        assert clean_string(" \t\n\r\n hello \t\n world \r\n ") == "hello world"

    # --- 数值类型 ---

    def test_integer(self):
        assert clean_string(123) == "123"

    def test_float(self):
        assert clean_string(3.14) == "3.14"

    def test_zero(self):
        assert clean_string(0) == "0"

    # --- pd.Series ---

    def test_series_first_element(self):
        s = pd.Series(["  hello  ", "world"])
        assert clean_string(s) == "hello"

    def test_series_with_nan_first(self):
        s = pd.Series([np.nan, "world"])
        assert clean_string(s) == ""

    def test_empty_series(self):
        s = pd.Series([], dtype=object)
        assert clean_string(s) == ""

    # --- 中文/蒙古文内容 ---

    def test_chinese_with_whitespace(self):
        assert clean_string("  白班  ") == "白班"

    def test_mongolian_with_newline(self):
        assert clean_string("Мото цагийн\nзаалт") == "Мото цагийн заалт"


class TestCleanPandasStrings:
    """测试 clean_pandas_strings 函数"""

    def test_cleans_object_columns(self):
        df = pd.DataFrame({
            "name": ["  Alice  ", "Bob\nSmith", "Charlie\tJr"],
            "value": [1, 2, 3],
        })
        result = clean_pandas_strings(df)
        assert result["name"].tolist() == ["Alice", "Bob Smith", "Charlie Jr"]
        assert result["value"].tolist() == [1, 2, 3]  # 数值列不受影响

    def test_specific_columns(self):
        df = pd.DataFrame({
            "a": ["  hello  ", "  world  "],
            "b": ["  keep  spaces  ", "  as is  "],
        })
        result = clean_pandas_strings(df, columns=["a"])
        assert result["a"].tolist() == ["hello", "world"]
        # b 列未指定，保持原样
        assert result["b"].tolist() == ["  keep  spaces  ", "  as is  "]

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = clean_pandas_strings(df)
        assert result.empty

    def test_no_object_columns(self):
        df = pd.DataFrame({"x": [1, 2], "y": [3.0, 4.0]})
        result = clean_pandas_strings(df)
        assert result["x"].tolist() == [1, 2]

    def test_handles_nan_in_object_column(self):
        df = pd.DataFrame({"name": ["  Alice  ", np.nan, "  Bob  "]})
        result = clean_pandas_strings(df)
        assert result["name"].tolist() == ["Alice", "", "Bob"]

    def test_returns_same_reference(self):
        df = pd.DataFrame({"name": ["test"]})
        result = clean_pandas_strings(df)
        assert result is df  # 原地修改
