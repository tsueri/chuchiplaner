from app.services.duration_serializer import DurationSerializer


def test_to_iso_duration_minutes_only() -> None:
    assert DurationSerializer.to_iso_duration(45) == "PT45M"


def test_to_iso_duration_hours_only() -> None:
    assert DurationSerializer.to_iso_duration(60) == "PT1H"


def test_to_iso_duration_hours_and_minutes() -> None:
    assert DurationSerializer.to_iso_duration(90) == "PT1H30M"


def test_to_iso_duration_zero() -> None:
    assert DurationSerializer.to_iso_duration(0) == "PT0M"


def test_to_iso_duration_none_returns_none() -> None:
    assert DurationSerializer.to_iso_duration(None) is None


def test_from_iso_duration_minutes_only() -> None:
    assert DurationSerializer.from_iso_duration("PT45M") == 45


def test_from_iso_duration_hours_only() -> None:
    assert DurationSerializer.from_iso_duration("PT1H") == 60


def test_from_iso_duration_hours_and_minutes() -> None:
    assert DurationSerializer.from_iso_duration("PT1H30M") == 90


def test_from_iso_duration_seconds_truncates_to_zero_minutes() -> None:
    assert DurationSerializer.from_iso_duration("PT45S") == 0


def test_from_iso_duration_garbage_returns_none() -> None:
    assert DurationSerializer.from_iso_duration("not-a-duration") is None


def test_from_iso_duration_none_returns_none() -> None:
    assert DurationSerializer.from_iso_duration(None) is None


def test_format_human_minutes_only() -> None:
    assert DurationSerializer.format_human(45) == "45 min"


def test_format_human_one_hour() -> None:
    assert DurationSerializer.format_human(60) == "1 Std."


def test_format_human_hours_and_minutes() -> None:
    assert DurationSerializer.format_human(90) == "1 Std. 30 min"


def test_format_human_zero() -> None:
    assert DurationSerializer.format_human(0) == "0 min"


def test_format_human_none_returns_none() -> None:
    assert DurationSerializer.format_human(None) is None


def test_parse_human_hours_and_minutes_compact() -> None:
    assert DurationSerializer.parse_human("1h 30m") == 90


def test_parse_human_minutes_with_unit() -> None:
    assert DurationSerializer.parse_human("90 min") == 90


def test_parse_human_clock_format() -> None:
    assert DurationSerializer.parse_human("1:30") == 90


def test_parse_human_german_stunden() -> None:
    assert DurationSerializer.parse_human("2 Std.") == 120


def test_parse_human_decimal_hours() -> None:
    assert DurationSerializer.parse_human("2.5h") == 150


def test_parse_human_garbage_returns_none() -> None:
    assert DurationSerializer.parse_human("garbage") is None


def test_parse_human_empty_returns_none() -> None:
    assert DurationSerializer.parse_human("") is None


def test_parse_human_none_returns_none() -> None:
    assert DurationSerializer.parse_human(None) is None


def test_to_iso_and_from_iso_round_trip() -> None:
    for minutes in [0, 30, 60, 90, 125, 240]:
        assert (
            DurationSerializer.from_iso_duration(
                DurationSerializer.to_iso_duration(minutes)
            )
            == minutes
        )
