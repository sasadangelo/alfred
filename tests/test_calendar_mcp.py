"""Tests for the Google Calendar MCP tool helpers."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from alfred.calendar_mcp import _parse_datetime, _parse_event_time, _parse_range_bound


def test_parse_event_time_treats_plain_dates_as_all_day() -> None:
    parsed = _parse_event_time("2026-12-21", "Europe/Rome")

    assert parsed == date(2026, 12, 21)
    assert not isinstance(parsed, datetime)


def test_parse_event_time_applies_configured_timezone_to_naive_datetimes() -> None:
    parsed = _parse_event_time("2026-12-21T10:00:00", "Europe/Rome")

    assert parsed == datetime(2026, 12, 21, 10, 0, tzinfo=ZoneInfo("Europe/Rome"))


def test_parse_datetime_keeps_explicit_offsets() -> None:
    parsed = _parse_datetime("2026-12-21T09:00:00Z", "Europe/Rome")

    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_parse_range_bound_turns_dates_into_local_midnight() -> None:
    assert _parse_range_bound("2026-12-01", "Europe/Rome") == datetime(2026, 12, 1, tzinfo=ZoneInfo("Europe/Rome"))
