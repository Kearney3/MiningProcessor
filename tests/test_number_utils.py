"""Tests for func/number_utils.py decimal-semantic helpers."""

import math
from decimal import Decimal

import pytest

from func.number_utils import (
    decimal_add,
    decimal_divide,
    decimal_mod,
    decimal_multiply,
    decimal_power,
    decimal_subtract,
    decimal_sum,
    to_decimal,
)


# ---------------------------------------------------------------------------
# to_decimal
# ---------------------------------------------------------------------------

class TestToDecimal:
    """Tests for the to_decimal() conversion helper."""

    def test_integer_input(self):
        # Arrange & Act
        result = to_decimal(42)
        # Assert
        assert result == Decimal("42")

    def test_float_input_preserves_decimal_semantics(self):
        """0.1 + 0.2 should round-trip through decimal without binary drift."""
        # Arrange & Act
        result = to_decimal(0.1)
        # Assert -- str(0.1) is "0.1", so Decimal captures the intended value
        assert result == Decimal("0.1")

    def test_string_numeric(self):
        # Arrange & Act
        result = to_decimal("3.14")
        # Assert
        assert result == Decimal("3.14")

    def test_string_with_whitespace(self):
        # Arrange & Act
        result = to_decimal("  7.5  ")
        # Assert
        assert result == Decimal("7.5")

    def test_decimal_passthrough(self):
        # Arrange
        d = Decimal("99.99")
        # Act
        result = to_decimal(d)
        # Assert
        assert result == d

    def test_bool_true_returns_one(self):
        # Arrange & Act
        result = to_decimal(True)
        # Assert
        assert result == Decimal(1)

    def test_bool_false_returns_zero(self):
        # Arrange & Act
        result = to_decimal(False)
        # Assert
        assert result == Decimal(0)

    def test_none_returns_none(self):
        # Arrange & Act
        result = to_decimal(None)
        # Assert
        assert result is None

    def test_nan_returns_none(self):
        # Arrange & Act
        result = to_decimal(float("nan"))
        # Assert
        assert result is None

    def test_positive_infinity_returns_none(self):
        # Arrange & Act
        result = to_decimal(float("inf"))
        # Assert
        assert result is None

    def test_negative_infinity_returns_none(self):
        # Arrange & Act
        result = to_decimal(float("-inf"))
        # Assert
        assert result is None

    def test_non_numeric_string_returns_none(self):
        # Arrange & Act
        result = to_decimal("hello")
        # Assert
        assert result is None

    def test_empty_string_returns_none(self):
        # Arrange & Act
        result = to_decimal("")
        # Assert
        assert result is None

    def test_list_input_returns_none(self):
        # Arrange & Act
        result = to_decimal([1, 2])
        # Assert
        assert result is None

    def test_zero(self):
        # Arrange & Act
        result = to_decimal(0)
        # Assert
        assert result == Decimal(0)

    def test_negative_value(self):
        # Arrange & Act
        result = to_decimal(-42)
        # Assert
        assert result == Decimal("-42")

    def test_large_integer(self):
        # Arrange & Act
        result = to_decimal(10**18)
        # Assert
        assert result == Decimal(10**18)

    def test_very_small_float(self):
        # Arrange & Act
        result = to_decimal(1e-15)
        # Assert
        assert result is not None
        assert float(result) == pytest.approx(1e-15)

    def test_negative_infinity_string(self):
        # "Infinity" is a valid float literal
        # Arrange & Act
        result = to_decimal("Infinity")
        # Assert -- Decimal("Infinity") is not finite
        assert result is None


# ---------------------------------------------------------------------------
# Arithmetic helpers: decimal_add / subtract / multiply / divide / mod
# ---------------------------------------------------------------------------

class TestDecimalArithmetic:
    """Tests for the four basic arithmetic operations + mod."""

    # -- decimal_add --------------------------------------------------------

    def test_add_two_integers(self):
        assert decimal_add(2, 3) == 5.0

    def test_add_two_floats_no_drift(self):
        """The canonical 0.1 + 0.2 case must equal 0.3 exactly."""
        result = decimal_add(0.1, 0.2)
        assert result == 0.3

    def test_add_string_operands(self):
        assert decimal_add("1.5", "2.5") == 4.0

    def test_add_with_none_returns_zero(self):
        assert decimal_add(None, 5) == 0.0
        assert decimal_add(5, None) == 0.0

    def test_add_with_nan_returns_zero(self):
        assert decimal_add(float("nan"), 1) == 0.0

    def test_add_with_inf_returns_zero(self):
        assert decimal_add(float("inf"), 1) == 0.0

    def test_add_negative_values(self):
        assert decimal_add(-3, -7) == -10.0

    def test_add_mixed_types(self):
        assert decimal_add(1, "2") == 3.0

    def test_add_booleans(self):
        """Booleans are coerced to ints: True + True = 2."""
        assert decimal_add(True, True) == 2.0

    # -- decimal_subtract ---------------------------------------------------

    def test_subtract_two_integers(self):
        assert decimal_subtract(10, 3) == 7.0

    def test_subtract_reversed_gives_negative(self):
        assert decimal_subtract(3, 10) == -7.0

    def test_subtract_no_drift(self):
        result = decimal_subtract(1.0, 0.9)
        assert result == pytest.approx(0.1)
        # Ensure it's *exactly* 0.1 via decimal round-trip
        assert result == 0.1

    def test_subtract_with_none_returns_zero(self):
        assert decimal_subtract(None, 5) == 0.0
        assert decimal_subtract(5, None) == 0.0

    # -- decimal_multiply ---------------------------------------------------

    def test_multiply_two_integers(self):
        assert decimal_multiply(4, 5) == 20.0

    def test_multiply_floats_no_drift(self):
        """0.1 * 0.2 should be exactly 0.02 (not 0.020000000000000004)."""
        result = decimal_multiply(0.1, 0.2)
        assert result == 0.02

    def test_multiply_by_zero(self):
        assert decimal_multiply(999, 0) == 0.0

    def test_multiply_negative(self):
        assert decimal_multiply(-3, 4) == -12.0

    def test_multiply_with_none_returns_zero(self):
        assert decimal_multiply(None, 5) == 0.0

    # -- decimal_divide -----------------------------------------------------

    def test_divide_two_integers(self):
        assert decimal_divide(10, 2) == 5.0

    def test_divide_with_repeating_decimal(self):
        """10 / 3 is a repeating decimal; result should be close but finite."""
        result = decimal_divide(10, 3)
        assert result == pytest.approx(3.3333333333333335)

    def test_divide_by_zero_returns_zero(self):
        assert decimal_divide(10, 0) == 0.0

    def test_divide_zero_by_number(self):
        assert decimal_divide(0, 10) == 0.0

    def test_divide_with_none_returns_zero(self):
        assert decimal_divide(None, 5) == 0.0
        assert decimal_divide(5, None) == 0.0

    def test_divide_both_none_returns_zero(self):
        assert decimal_divide(None, None) == 0.0

    def test_divide_no_drift(self):
        result = decimal_divide(0.3, 0.1)
        assert result == 3.0

    # -- decimal_mod --------------------------------------------------------

    def test_mod_basic(self):
        assert decimal_mod(10, 3) == 1.0

    def test_mod_evenly_divisible(self):
        assert decimal_mod(9, 3) == 0.0

    def test_mod_with_none_returns_zero(self):
        assert decimal_mod(None, 3) == 0.0
        assert decimal_mod(10, None) == 0.0

    def test_mod_by_zero_returns_zero(self):
        assert decimal_mod(10, 0) == 0.0

    def test_mod_floats(self):
        result = decimal_mod(5.5, 2.0)
        assert result == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# decimal_power
# ---------------------------------------------------------------------------

class TestDecimalPower:
    """Tests for decimal_power() which has its own implementation (not _binary_operation)."""

    def test_basic_square(self):
        assert decimal_power(3, 2) == 9.0

    def test_zero_exponent(self):
        assert decimal_power(5, 0) == 1.0

    def test_zero_base(self):
        assert decimal_power(0, 5) == 0.0

    def test_negative_exponent(self):
        result = decimal_power(2, -1)
        assert result == pytest.approx(0.5)

    def test_fractional_exponent(self):
        """Square root via 0.5 exponent."""
        result = decimal_power(4, 0.5)
        assert result == pytest.approx(2.0)

    def test_with_none_returns_zero(self):
        assert decimal_power(None, 2) == 0.0
        assert decimal_power(2, None) == 0.0

    def test_large_exponent(self):
        result = decimal_power(2, 10)
        assert result == 1024.0

    def test_both_none_returns_zero(self):
        assert decimal_power(None, None) == 0.0


# ---------------------------------------------------------------------------
# decimal_sum
# ---------------------------------------------------------------------------

class TestDecimalSum:
    """Tests for decimal_sum() that operates on iterables."""

    def test_sum_integers(self):
        assert decimal_sum([1, 2, 3, 4]) == 10.0

    def test_sum_floats_no_drift(self):
        """Summing 0.1 ten times should equal 1.0, not 0.9999..."""
        result = decimal_sum([0.1] * 10)
        assert result == 1.0

    def test_sum_empty_iterable(self):
        assert decimal_sum([]) == 0.0

    def test_sum_skips_none(self):
        assert decimal_sum([1, None, 3]) == 4.0

    def test_sum_skips_nan(self):
        assert decimal_sum([1, float("nan"), 3]) == 4.0

    def test_sum_skips_inf(self):
        assert decimal_sum([1, float("inf"), 3]) == 4.0

    def test_sum_skips_non_numeric(self):
        assert decimal_sum([1, "abc", 3]) == 4.0

    def test_sum_single_value(self):
        assert decimal_sum([42]) == 42.0

    def test_sum_all_invalid_returns_zero(self):
        assert decimal_sum([None, "abc", float("nan")]) == 0.0

    def test_sum_mixed_types(self):
        assert decimal_sum([1, "2", 3.0, Decimal("4")]) == 10.0

    def test_sum_negative_values(self):
        assert decimal_sum([-1, -2, -3]) == -6.0

    def test_sum_generator(self):
        # Arrange
        gen = (x for x in [1, 2, 3])
        # Act & Assert
        assert decimal_sum(gen) == 6.0

    def test_sum_tuple(self):
        assert decimal_sum((10, 20, 30)) == 60.0


# ---------------------------------------------------------------------------
# Precision / floating-point drift tests
# ---------------------------------------------------------------------------

class TestPrecision:
    """Verify decimal arithmetic eliminates classic floating-point drift."""

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            (0.1, 0.2, 0.3),
            (0.1, 0.7, 0.8),
            (0.15, 0.15, 0.3),
            (0.3, 0.6, 0.9),
            (1.0, 2.2, 3.2),
        ],
        ids=["0.1+0.2", "0.1+0.7", "0.15+0.15", "0.3+0.6", "1.0+2.2"],
    )
    def test_addition_no_drift(self, a, b, expected):
        assert decimal_add(a, b) == expected

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            (0.3, 0.1, 0.2),
            (1.0, 0.7, 0.3),
            (2.0, 1.1, 0.9),
        ],
        ids=["0.3-0.1", "1.0-0.7", "2.0-1.1"],
    )
    def test_subtraction_no_drift(self, a, b, expected):
        assert decimal_subtract(a, b) == expected

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            (0.1, 0.2, 0.02),
            (0.1, 3, 0.3),
            (1.5, 1.5, 2.25),
        ],
        ids=["0.1*0.2", "0.1*3", "1.5*1.5"],
    )
    def test_multiplication_no_drift(self, a, b, expected):
        assert decimal_multiply(a, b) == expected

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            (0.3, 0.1, 3.0),
            (0.7, 0.1, 7.0),
            (1.5, 0.5, 3.0),
        ],
        ids=["0.3/0.1", "0.7/0.1", "1.5/0.5"],
    )
    def test_division_no_drift(self, a, b, expected):
        assert decimal_divide(a, b) == expected
