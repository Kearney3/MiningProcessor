"""Tests for the unified apply_header_mapping in func.excel_utils."""

import pandas as pd

from func.excel_utils import apply_header_mapping

# ---------------------------------------------------------------------------
# Exact matching (name mode, single keyword = substring)
# ---------------------------------------------------------------------------


class TestExactNameMatching:
    """Single-keyword name matching (substring OR logic)."""

    def test_basic_exact_match(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["A"], "new": "Alpha"},
                {"keywords": ["B"], "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["Alpha", "Beta", "C"]

    def test_unmatched_columns_unchanged(self):
        df = pd.DataFrame({"X": [1], "Y": [2]})
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["Z"], "new": "Zeta"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["X", "Y"]

    def test_exact_match_with_whitespace_cleaning(self):
        df = pd.DataFrame({"  A  ": [1], "B\n": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["A"], "new": "Alpha"},
                {"keywords": ["B"], "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["Alpha", "Beta"]


# ---------------------------------------------------------------------------
# Position mode
# ---------------------------------------------------------------------------


class TestPositionMatching:
    """Column renaming by 1-based index."""

    def test_basic_position_match(self):
        df = pd.DataFrame({"col1": [1], "col2": [2], "col3": [3]})
        cfg = {
            "mode": "position",
            "entries": [
                {"index": 1, "new": "First"},
                {"index": 3, "new": "Third"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["First", "col2", "Third"]

    def test_position_index_out_of_range_ignored(self):
        df = pd.DataFrame({"A": [1]})
        cfg = {
            "mode": "position",
            "entries": [{"index": 99, "new": "Nope"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A"]

    def test_position_zero_index_ignored(self):
        df = pd.DataFrame({"A": [1]})
        cfg = {
            "mode": "position",
            "entries": [{"index": 0, "new": "Nope"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A"]

    def test_position_non_integer_index_ignored(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "position",
            "entries": [
                {"index": "abc", "new": "Nope"},
                {"index": 2, "new": "Second"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Second"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Empty, None, and missing inputs."""

    def test_empty_config_returns_original(self):
        df = pd.DataFrame({"A": [1]})
        result = apply_header_mapping(df, {})
        assert list(result.columns) == ["A"]

    def test_none_config_returns_original(self):
        df = pd.DataFrame({"A": [1]})
        result = apply_header_mapping(df, None)
        assert list(result.columns) == ["A"]

    def test_empty_entries_returns_original(self):
        df = pd.DataFrame({"A": [1]})
        result = apply_header_mapping(df, {"mode": "name", "entries": []})
        assert list(result.columns) == ["A"]

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["A"], "new": "B"}],
        }
        result = apply_header_mapping(df, cfg)
        assert result.empty

    def test_entry_with_empty_new_is_skipped(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["A"], "new": ""},
                {"keywords": ["B"], "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Beta"]

    def test_entry_with_empty_keywords_is_skipped(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": [], "new": "Nope"},
                {"keywords": ["B"], "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Beta"]

    def test_does_not_mutate_original(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        original_cols = list(df.columns)
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["A"], "new": "Alpha"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(df.columns) == original_cols
        assert list(result.columns) == ["Alpha", "B"]

    def test_position_with_none_index_skipped(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "position",
            "entries": [
                {"index": None, "new": "Nope"},
                {"index": 2, "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Beta"]


# ---------------------------------------------------------------------------
# Partial matches
# ---------------------------------------------------------------------------


class TestPartialMatches:
    """Only some columns match."""

    def test_partial_exact_match(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["A"], "new": "Alpha"},
                {"keywords": ["Z"], "new": "Zeta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["Alpha", "B", "C"]

    def test_partial_position_match(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        cfg = {
            "mode": "position",
            "entries": [
                {"index": 2, "new": "Second"},
                {"index": 99, "new": "Nope"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Second", "C"]


# ---------------------------------------------------------------------------
# Data preservation
# ---------------------------------------------------------------------------


class TestDataPreservation:
    """Verify column data is preserved after renaming."""

    def test_data_values_preserved(self):
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["A"], "new": "Alpha"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result["Alpha"]) == [1, 2, 3]
        assert list(result["B"]) == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# Substring matching (single keyword)
# ---------------------------------------------------------------------------


class TestSubstringMatch:
    """Name matching with single keyword = substring containment."""

    def test_substring_single_match(self):
        """Entry '设备种类' matches column '设备种类 Техникийн төрөл'."""
        df = pd.DataFrame({
            "设备种类                             Техникийн төрөл ": ["EX5600"],
            "公司 Компани": ["Normount"],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["设备种类"], "new": "EquipmentType"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "EquipmentType" in result.columns
        assert "公司 Компани" in result.columns

    def test_substring_ambiguous_picks_first_column(self):
        """Ambiguous substring match picks the first matching column."""
        df = pd.DataFrame({
            "运行分钟 总计": [100],
            "运行分钟 计划": [80],
            "其他": [20],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["运行分钟"], "new": "RunMin"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "RunMin" in result.columns
        assert result.columns.tolist() == ["RunMin", "运行分钟 计划", "其他"]

    def test_substring_first_column_in_df_order_wins(self):
        """When multiple columns match, the first in DataFrame order wins."""
        df = pd.DataFrame({
            "A": [1],
            "A extended": [2],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["A"], "new": "Alpha"}],
        }
        result = apply_header_mapping(df, cfg)
        assert result.columns.tolist() == ["Alpha", "A extended"]


# ---------------------------------------------------------------------------
# Multi-keyword matching (OR logic with keywords list)
# ---------------------------------------------------------------------------


class TestMultiKeywordMatch:
    """Name matching with keyword list (OR logic)."""

    def test_multi_keyword_or_match(self):
        """Entry ['应运行', 'мин'] matches '应运行分钟 Ажиллах мин' (either keyword)."""
        df = pd.DataFrame({
            "应运行分钟 Ажиллах мин": [720],
            "公司 Компани": ["Normount"],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["应运行", "мин"], "new": "RequiredMin"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "RequiredMin" in result.columns
        assert "公司 Компани" in result.columns

    def test_multi_keyword_any_order_matches(self):
        """OR logic: keyword order in config doesn't matter."""
        df = pd.DataFrame({
            "应运行分钟 Ажиллах мин": [720],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["мин", "应运行"], "new": "Matched"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "Matched" in result.columns

    def test_multi_keyword_with_whitespace(self):
        """Keywords with surrounding whitespace are trimmed."""
        df = pd.DataFrame({
            "停车/换班/ Сул Зогсолт": [30],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["停车", "Зогсолт"], "new": "Downtime"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "Downtime" in result.columns

    def test_single_keyword_works(self):
        """Single keyword entry works as substring match."""
        df = pd.DataFrame({
            "应运行分钟 Ажиллах мин": [720],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["应运行"], "new": "Required"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "Required" in result.columns

    def test_multi_keyword_real_worktime_headers(self):
        """Real-world worktime column names with multi-keyword matching."""
        df = pd.DataFrame({
            "序号 Д/д": [1],
            "设备种类 Техникийн төрөл": ["EX5600"],
            "公司 Компани": ["Normount"],
            "应运行分钟 Ажиллах мин": [720],
            "应运行小时数 Ажиллах мот цаг": [12],
        })
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["序号", "Д/д"], "new": "序号"},
                {"keywords": ["设备种类", "төрөл"], "new": "设备种类"},
                {"keywords": ["应运行分钟", "мин"], "new": "应运行分钟"},
                {"keywords": ["应运行小时", "мот цаг"], "new": "应运行小时"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert result.columns.tolist() == [
            "序号", "设备种类", "公司 Компани", "应运行分钟", "应运行小时",
        ]

    def test_multi_keyword_first_match_wins(self):
        """When multiple entries could match the same column, first entry wins."""
        df = pd.DataFrame({
            "应运行分钟 Ажиллах мин": [720],
        })
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["应运行"], "new": "First"},
                {"keywords": ["мин"], "new": "Second"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert result.columns.tolist() == ["First"]

    def test_plus_in_keywords_matched_literally(self):
        """Keywords containing special chars match literally."""
        df = pd.DataFrame({
            "柴油 Түлш Fuel": [100],
            "其他列": [200],
        })
        cfg = {
            "mode": "name",
            "entries": [{"keywords": ["柴油", "Fuel"], "new": "FuelCol"}],
        }
        result = apply_header_mapping(df, cfg)
        assert "FuelCol" in result.columns


# ---------------------------------------------------------------------------
# First-match-wins semantics
# ---------------------------------------------------------------------------


class TestFirstMatchWins:
    """Verify that once a column is matched, it can't be re-matched."""

    def test_column_excluded_after_first_match(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["A"], "new": "First"},
                {"keywords": ["A"], "new": "Second"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert result.columns.tolist() == ["First", "B"]

    def test_no_match_entry_ignored(self):
        """Entries that match nothing are silently ignored."""
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"keywords": ["NONEXISTENT"], "new": "Nope"},
                {"keywords": ["A"], "new": "Alpha"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert result.columns.tolist() == ["Alpha", "B"]

    def test_entry_without_keywords_skipped(self):
        """Entry with no keywords list is skipped."""
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"new": "Nope"},
                {"keywords": ["A"], "new": "Alpha"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert result.columns.tolist() == ["Alpha", "B"]
