"""Tests for path-traversal sanitization in func/excel_utils.py and func/excel_merger.py"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func.excel_utils import sanitize_filename


class TestSanitizeFilename:
    """sanitize_filename should strip path separators and .. sequences."""

    def test_normal_keyword_passes_through(self):
        """A plain keyword with no special characters is unchanged."""
        assert sanitize_filename("柴油") == "柴油"

    def test_alphanumeric_keyword(self):
        """A simple alphanumeric keyword passes through unchanged."""
        assert sanitize_filename("fuel_data") == "fuel_data"

    def test_removes_forward_slash(self):
        """Forward slashes are removed."""
        assert sanitize_filename("../etc/evil") == "etcevil"

    def test_removes_backslash(self):
        """Backslashes are removed."""
        assert sanitize_filename("..\\etc\\evil") == "etcevil"

    def test_removes_dot_dot(self):
        """Double-dot sequences are removed."""
        assert sanitize_filename("../../secret") == "secret"

    def test_mixed_attack(self):
        """A realistic path-traversal attack vector is fully sanitized."""
        result = sanitize_filename("../../etc/passwd")
        # No path separators or .. sequences should survive
        assert "/" not in result
        assert ".." not in result
        assert "\\" not in result

    def test_underscore_and_dots_preserved(self):
        """Single dots and underscores in legitimate names are kept."""
        assert sanitize_filename("report.2024") == "report.2024"

    def test_empty_string(self):
        """An empty string is handled without error."""
        assert sanitize_filename("") == ""

    def test_only_separators(self):
        """A string of only path separators becomes empty."""
        assert sanitize_filename("///\\\\//") == ""
