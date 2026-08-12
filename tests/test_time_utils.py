from datetime import date, datetime

from func.time_utils import (
    local_datetime_from_timestamp,
    local_midnight,
    local_now,
    local_today,
)


def test_local_now_is_aware_and_matches_local_today():
    now = local_now()

    assert now.tzinfo is not None
    assert now.date() == local_today()


def test_local_timestamp_round_trip_uses_local_timezone():
    source = local_now()
    restored = local_datetime_from_timestamp(source.timestamp())

    assert restored.tzinfo is not None
    assert restored.utcoffset() == source.utcoffset()
    assert abs(restored.timestamp() - source.timestamp()) < 0.001


def test_local_midnight_preserves_calendar_date():
    midnight = local_midnight(date(2026, 8, 12))

    assert isinstance(midnight, datetime)
    assert midnight.date() == date(2026, 8, 12)
    assert midnight.hour == 0
    assert midnight.tzinfo is not None
