"""Decimal-semantic helpers for numeric values read from Excel.

Excel stores decimal-looking values as binary floating-point numbers when
loaded by pandas/openpyxl.  These helpers convert operands through their
shortest decimal representation before arithmetic, so business calculations
do not expose binary floating-point tails such as ``0.30000000000000004``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


def to_decimal(value: Any) -> Decimal | None:
    """Convert a scalar to a finite ``Decimal`` using its decimal text form."""
    if value is None:
        return None
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, Decimal):
        number = value
    else:
        try:
            number = Decimal(str(value).strip())
        except (AttributeError, InvalidOperation, TypeError, ValueError):
            return None
    return number if number.is_finite() else None


def _binary_operation(left: Any, right: Any, operation) -> float:
    left_decimal = to_decimal(left)
    right_decimal = to_decimal(right)
    if left_decimal is None or right_decimal is None:
        return 0.0
    try:
        return float(operation(left_decimal, right_decimal))
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        return 0.0


def decimal_add(left: Any, right: Any) -> float:
    """Add two values using decimal semantics."""
    return _binary_operation(left, right, lambda a, b: a + b)


def decimal_subtract(end: Any, start: Any) -> float:
    """Subtract ``start`` from ``end`` using decimal semantics."""
    return _binary_operation(end, start, lambda a, b: a - b)


def decimal_multiply(left: Any, right: Any) -> float:
    """Multiply two values using decimal semantics."""
    return _binary_operation(left, right, lambda a, b: a * b)


def decimal_divide(numerator: Any, denominator: Any) -> float:
    """Divide two values using decimal semantics; zero/invalid input returns 0."""
    return _binary_operation(numerator, denominator, lambda a, b: a / b)


def decimal_mod(left: Any, right: Any) -> float:
    """Calculate a remainder using decimal semantics."""
    return _binary_operation(left, right, lambda a, b: a % b)


def decimal_power(left: Any, right: Any) -> float:
    """Raise a value to a power using decimal semantics where supported."""
    left_decimal = to_decimal(left)
    right_decimal = to_decimal(right)
    if left_decimal is None or right_decimal is None:
        return 0.0
    try:
        return float(left_decimal**right_decimal)
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        try:
            return float(left) ** float(right)
        except (ArithmeticError, TypeError, ValueError):
            return 0.0


def decimal_sum(values: Iterable[Any]) -> float:
    """Sum finite values with decimal semantics, skipping empty/invalid values."""
    total = Decimal(0)
    for value in values:
        number = to_decimal(value)
        if number is not None:
            total += number
    return float(total)
