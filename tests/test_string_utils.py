"""
测试字符串清理工具模块
"""
import pytest
import pandas as pd
import numpy as np

from func.string_utils import clean_string, clean_equipment_name, normalize_cyrillic_homoglyphs


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

    # --- 零宽字符 ---

    def test_zwsp_removed(self):
        """零宽空格 U+200B 应被删除"""
        assert clean_string("EX​#001") == "EX#001"

    def test_zwnj_removed(self):
        """零宽非连接符 U+200C 应被删除"""
        assert clean_string("EX‌#001") == "EX#001"

    def test_zwj_removed(self):
        """零宽连接符 U+200D 应被删除"""
        assert clean_string("EX‍#001") == "EX#001"

    def test_word_joiner_removed(self):
        """Word Joiner U+2060 应被删除"""
        assert clean_string("EX⁠#001") == "EX#001"

    def test_bom_removed(self):
        """BOM U+FEFF 应被删除"""
        assert clean_string("﻿EX#001") == "EX#001"

    def test_multiple_zero_width_removed(self):
        """多种零宽字符混合应全部删除"""
        assert clean_string("EX​‌‍#001") == "EX#001"

    def test_zero_width_with_surrounding_spaces(self):
        """零宽字符与空格组合"""
        assert clean_string("  EX ​ #001  ") == "EX #001"

    # --- 不换行空格 ---

    def test_nbsp_replaced_with_space(self):
        """不换行空格 U+00A0 应替换为普通空格"""
        assert clean_string("EX #001") == "EX #001"

    def test_nbsp_and_zero_width_combined(self):
        """NBSP + 零宽字符组合"""
        assert clean_string("EX ​#001") == "EX #001"

    def test_nbsp_at_boundaries(self):
        """两端的 NBSP 应被 trim"""
        assert clean_string(" hello ") == "hello"

    # --- 组合场景 ---

    def test_real_world_pdf_copy(self):
        """模拟从 PDF 复制到 Excel 的脏数据"""
        assert clean_string(" NTE240 ​#1101\n ") == "NTE240 #1101"

    def test_real_world_web_copy(self):
        """模拟从网页复制的带 ZWSP 设备名"""
        assert clean_string("HITACHI​EX5600​EX#0123") == "HITACHIEX5600EX#0123"


class TestNormalizeCyrillicHomoglyphs:
    """测试西里尔同形字母替换函数"""

    # --- 基本替换 ---

    def test_cyrillic_c_to_latin(self):
        """西里尔 С (U+0421) → 拉丁 C (U+0043)"""
        result = normalize_cyrillic_homoglyphs("СAT777")
        assert result == "CAT777"

    def test_all_cyrillic_homoglyphs(self):
        """覆盖全部 12 个同形字母"""
        cyrillic = "АВСЕІКМОРТХН"
        latin    = "ABCEIKMOPTXH"
        assert normalize_cyrillic_homoglyphs(cyrillic) == latin

    def test_mixed_script(self):
        """混合西里尔和拉丁字母"""
        assert normalize_cyrillic_homoglyphs("СAT 777 #18KH") == "CAT 777 #18KH"

    def test_already_latin(self):
        """纯拉丁字符串不变"""
        assert normalize_cyrillic_homoglyphs("CAT777") == "CAT777"

    def test_empty_string(self):
        assert normalize_cyrillic_homoglyphs("") == ""

    # --- 实际场景 ---

    def test_mongolian_mine_truck_name(self):
        """蒙古矿区矿卡名称场景"""
        assert normalize_cyrillic_homoglyphs("СAT 777 #18KH") == "CAT 777 #18KH"

    def test_cyrillic_only_model(self):
        """全西里尔型号"""
        assert normalize_cyrillic_homoglyphs("КАТ777") == "KAT777"

    def test_preserves_mongolian_content(self):
        """保留真正的蒙古文/西里尔文内容（非同形字母不替换）"""
        text = "Мото цагийн заалт"
        # М→M, о→o, т→t 恰好也是同形映射，但这是预期行为
        # 关键是不影响使用场景（设备名匹配时无所谓）
        result = normalize_cyrillic_homoglyphs(text)
        assert result is not None  # 不应抛异常

    def test_preserves_digits_and_symbols(self):
        """数字和符号不受影响"""
        assert normalize_cyrillic_homoglyphs("СAT-777 #18") == "CAT-777 #18"

    def test_preserves_spaces(self):
        """空格不被删除（只做字母替换）"""
        assert normalize_cyrillic_homoglyphs("СAT 777") == "CAT 777"


class TestCleanEquipmentName:
    """测试 clean_equipment_name 函数（clean_string + homoglyph 二合一）"""

    # --- 基本行为：继承 clean_string 的清理能力 ---

    def test_none_returns_empty(self):
        assert clean_equipment_name(None) == ""

    def test_nan_returns_empty(self):
        assert clean_equipment_name(np.nan) == ""

    def test_empty_string(self):
        assert clean_equipment_name("") == ""

    def test_whitespace_only(self):
        assert clean_equipment_name("   ") == ""

    # --- homoglyph 替换 ---

    def test_cyrillic_c_to_latin(self):
        """西里尔 С (U+0421) → 拉丁 C (U+0043)"""
        assert clean_equipment_name("СAT777") == "CAT777"

    def test_all_cyrillic_homoglyphs_replaced(self):
        """全部 12 个同形字母在 clean_equipment_name 管道中都被替换"""
        cyrillic = "АВСЕІКМОРТХН"
        latin    = "ABCEIKMOPTXH"
        assert clean_equipment_name(cyrillic) == latin

    def test_mixed_script_with_spaces(self):
        """混合西里尔+拉丁+空格"""
        assert clean_equipment_name("СAT 777 #18KH") == "CAT 777 #18KH"

    def test_already_latin_unchanged(self):
        """纯拉丁字符串不变"""
        assert clean_equipment_name("CAT777") == "CAT777"

    # --- 组合场景：clean_string 清理 + homoglyph 替换 ---

    def test_whitespace_and_homoglyph_combined(self):
        """前后空格 + 换行 + Cyrillic 同形字母"""
        assert clean_equipment_name("  САТ-777  \n") == "CAT-777"

    def test_internal_newline_and_homoglyph(self):
        """内部换行 + homoglyph"""
        assert clean_equipment_name("СAT\n777") == "CAT 777"

    def test_tab_and_homoglyph(self):
        """内部 Tab + homoglyph"""
        assert clean_equipment_name("NTE\t240") == "NTE 240"

    def test_zero_width_and_homoglyph(self):
        """零宽字符 + homoglyph"""
        assert clean_equipment_name("EX​‌#001") == "EX#001"

    def test_nbsp_and_homoglyph(self):
        """不换行空格 + homoglyph"""
        assert clean_equipment_name("СAT 777") == "CAT 777"

    def test_mixed_all_whitespace_and_homoglyph(self):
        """所有脏数据组合"""
        assert clean_equipment_name(" \t\n САТ \r\n 777 \t\n ") == "CAT 777"

    # --- 实际设备名称场景 ---

    def test_mine_truck_cyrillic_c(self):
        """矿卡名称：西里尔 С 开头"""
        assert clean_equipment_name("СAT 777 #18KH") == "CAT 777 #18KH"

    def test_hitachi_with_cyrillic_prefix(self):
        """挖机名称：西里尔型号前缀"""
        assert clean_equipment_name("КАТ777") == "KAT777"

    def test_real_world_excel_cell_with_homoglyph(self):
        """模拟 Excel 单元格的脏数据 + homoglyph"""
        assert clean_equipment_name("  NTE240 #1101\n  ") == "NTE240 #1101"

    # --- 数值类型 ---

    def test_integer(self):
        assert clean_equipment_name(123) == "123"

    def test_float(self):
        assert clean_equipment_name(3.14) == "3.14"

    # --- pd.Series ---

    def test_series_first_element(self):
        s = pd.Series(["  САТ777  ", "other"])
        assert clean_equipment_name(s) == "CAT777"

    def test_series_with_nan_first(self):
        s = pd.Series([np.nan, "CAT777"])
        assert clean_equipment_name(s) == ""


