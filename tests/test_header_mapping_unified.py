"""Tests for the unified apply_header_mapping in func.excel_utils."""

import pandas as pd
import pytest

from func.excel_utils import apply_header_mapping


# ---------------------------------------------------------------------------
# Exact matching (name mode, fuzzy=False)
# ---------------------------------------------------------------------------


class TestExactNameMatching:
    """Exact column-name matching without fuzzy."""

    def test_basic_exact_match(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        cfg = {
            "mode": "name",
            "fuzzy": False,
            "entries": [
                {"original": "A", "new": "Alpha"},
                {"original": "B", "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["Alpha", "Beta", "C"]

    def test_unmatched_columns_unchanged(self):
        df = pd.DataFrame({"X": [1], "Y": [2]})
        cfg = {
            "mode": "name",
            "fuzzy": False,
            "entries": [{"original": "Z", "new": "Zeta"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["X", "Y"]

    def test_exact_match_with_whitespace_cleaning(self):
        df = pd.DataFrame({"  A  ": [1], "B\n": [2]})
        cfg = {
            "mode": "name",
            "fuzzy": False,
            "entries": [
                {"original": "A", "new": "Alpha"},
                {"original": "B", "new": "Beta"},
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
# Fuzzy matching
# ---------------------------------------------------------------------------


class TestFuzzyFlagDeprecated:
    """fuzzy=True 时回退到精确匹配（rapidfuzz 已移除）"""

    def test_fuzzy_flag_falls_back_to_exact(self):
        df = pd.DataFrame({"Equipment Name": [1], "Company": [2]})
        cfg = {
            "mode": "name",
            "fuzzy": True,
            "entries": [
                {"original": "Equipment Name", "new": "设备名称"},
                {"original": "Company", "new": "公司"},
            ],
        }
        # 精确匹配应正常工作
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["设备名称", "公司"]

    def test_fuzzy_flag_no_partial_match(self):
        """fuzzy=True 不再进行模糊匹配，不精确的名称不会被重命名"""
        df = pd.DataFrame({"equipment name": [1]})
        cfg = {
            "mode": "name",
            "fuzzy": True,
            "entries": [{"original": "Equipment Name", "new": "设备名称"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["equipment name"]


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
            "entries": [{"original": "A", "new": "B"}],
        }
        result = apply_header_mapping(df, cfg)
        assert result.empty

    def test_entry_with_empty_new_is_skipped(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"original": "A", "new": ""},
                {"original": "B", "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Beta"]

    def test_entry_with_empty_original_is_skipped(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        cfg = {
            "mode": "name",
            "entries": [
                {"original": "", "new": "Nope"},
                {"original": "B", "new": "Beta"},
            ],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result.columns) == ["A", "Beta"]

    def test_does_not_mutate_original(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        original_cols = list(df.columns)
        cfg = {
            "mode": "name",
            "entries": [{"original": "A", "new": "Alpha"}],
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
            "fuzzy": False,
            "entries": [
                {"original": "A", "new": "Alpha"},
                {"original": "Z", "new": "Zeta"},
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
            "entries": [{"original": "A", "new": "Alpha"}],
        }
        result = apply_header_mapping(df, cfg)
        assert list(result["Alpha"]) == [1, 2, 3]
        assert list(result["B"]) == ["x", "y", "z"]
