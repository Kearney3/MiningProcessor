"""Tests for get_load_capacity substring model matching with length-descending sort."""
from func.excel_production_enhanced import MiningDataProcessor


def _make_processor(load_map):
    """Create a MiningDataProcessor with a custom device_load_map, bypassing config files."""
    return MiningDataProcessor(device_load_map=load_map)


class TestGetLoadCapacity:
    def test_longer_model_matches_before_shorter(self):
        """TR600 should match TR600, not TR60."""
        load_map = {"TR60": 220, "TR600": 320}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity("TR600") == 320

    def test_mt4400ac_matches_before_mt4400(self):
        """MT4400AC should match MT4400AC, not MT4400."""
        load_map = {"MT4400": 220, "MT4400AC": 290}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity("MT4400AC") == 290

    def test_shorter_model_still_matches_when_no_longer_key(self):
        """TR60 should still match when only TR60 is in the map."""
        load_map = {"TR60": 220}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity("TR60") == 220

    def test_substring_match_with_prefix(self):
        """Model embedded in a longer truck name should match."""
        load_map = {"TR60": 220, "TR600": 320}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity("SomeMine TR600 Unit07") == 320

    def test_no_match_returns_zero(self):
        """When the truck name matches nothing, return 0."""
        load_map = {"TR60": 220}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity("CAT994") == 0

    def test_nan_input_returns_zero(self):
        """NaN truck name should return 0."""
        import pandas as pd
        load_map = {"TR600": 320}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity(pd.NA) == 0
        assert proc.get_load_capacity(float("nan")) == 0

    def test_case_insensitive_matching(self):
        """Matching should be case-insensitive."""
        load_map = {"tr600": 320}
        proc = _make_processor(load_map)
        assert proc.get_load_capacity("TR600") == 320
