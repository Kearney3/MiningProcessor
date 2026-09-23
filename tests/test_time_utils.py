from func.time_utils import (
    local_datetime_from_timestamp,
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
