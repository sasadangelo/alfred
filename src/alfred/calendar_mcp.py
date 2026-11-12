"""Google Calendar tools, mounted into the google-workspace MCP server."""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

from alfred.calendar import (
    check_availability,
    create_event,
    delete_event,
    end_recurring_series,
    get_event,
    list_calendars,
    search_events,
    update_event,
)
from alfred.core.config import get_settings

INSTRUCTIONS = (
    "Google Calendar: every tool works on the primary calendar unless a calendar_id from "
    "list_google_calendars is given. Events with event_type 'birthday' come from Google Contacts "
    "and cannot be deleted through the Calendar API."
)

mcp = FastMCP(name="calendar", instructions=INSTRUCTIONS)


def _parse_datetime(value: str, timezone: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed


def _parse_event_time(value: str, timezone: str) -> date:
    """Parse YYYY-MM-DD as an all-day date, anything else as a datetime."""
    if len(value) == 10:
        return date.fromisoformat(value)
    return _parse_datetime(value, timezone)


def _parse_range_bound(value: str, timezone: str) -> datetime:
    """Parse a range bound; a plain YYYY-MM-DD means local midnight of that day."""
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=ZoneInfo(timezone))
    return _parse_datetime(value, timezone)


@mcp.tool
def list_calendar_events(
    start: str,
    end: str,
    query: str | None = None,
    max_results: int = 100,
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """List events overlapping [start, end); dates (YYYY-MM-DD) mean local midnight.

    query filters by free text (title, description, location), e.g. "Dentista".
    Returns {"events": [...], "truncated": bool}; when truncated, narrow the range or raise max_results.
    In each event, reminder_minutes is null when the calendar's default reminders apply and
    busy is false for events marked as "free".
    """
    timezone = get_settings().calendar.timezone
    return search_events(
        _parse_range_bound(start, timezone),
        _parse_range_bound(end, timezone),
        query=query,
        max_results=max_results,
        calendar_id=calendar_id,
    )


@mcp.tool
def check_calendar_availability(start: str, end: str, calendar_id: str = "primary") -> dict[str, Any]:
    """Check whether [start, end) is free: returns {"free", "conflicts", "other_events"}.

    conflicts are overlapping busy events (all-day ones included, e.g. holidays);
    other_events overlap but are marked free, such as contact birthdays.
    """
    timezone = get_settings().calendar.timezone
    return check_availability(
        _parse_range_bound(start, timezone),
        _parse_range_bound(end, timezone),
        calendar_id=calendar_id,
    )


@mcp.tool
def list_google_calendars() -> list[dict[str, Any]]:
    """List the user's calendars with the id to pass as calendar_id to the other tools."""
    return list_calendars()


@mcp.tool
def get_calendar_event(event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
    """Get an event's full details; pass a recurring_event_id to see the series' recurrence rules."""
    return get_event(event_id, calendar_id=calendar_id)


@mcp.tool
def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    reminder_minutes: list[int] | None = None,
    recurrence: list[str] | None = None,
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """Create a Google Calendar event from ISO-8601 times; naive times use the configured timezone.

    For an all-day event pass YYYY-MM-DD dates; end is exclusive (the day after the last day).
    reminder_minutes sets popup notifications (minutes before start; for all-day events start is
    local midnight, so 480 means 16:00 the day before); omit it for the calendar defaults.
    recurrence takes RFC 5545 lines, e.g. ["RRULE:FREQ=MONTHLY;BYMONTHDAY=15"].
    """
    timezone = get_settings().calendar.timezone
    return create_event(
        summary,
        _parse_event_time(start, timezone),
        _parse_event_time(end, timezone),
        description=description,
        location=location,
        reminder_minutes=reminder_minutes,
        recurrence=recurrence,
        time_zone=timezone,
        calendar_id=calendar_id,
    )


@mcp.tool
def update_calendar_event(
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
    reminder_minutes: list[int] | None = None,
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """Update only the given fields of a Google Calendar event; start and end must be given together.

    start/end accept YYYY-MM-DD for all-day events (end exclusive) or ISO-8601 datetimes.
    reminder_minutes replaces the event's popup notifications (minutes before start; for all-day
    events start is local midnight, so 420 means 17:00 the day before). Pass [] to remove them.
    """
    timezone = get_settings().calendar.timezone
    return update_event(
        event_id,
        summary=summary,
        start=_parse_event_time(start, timezone) if start else None,
        end=_parse_event_time(end, timezone) if end else None,
        description=description,
        location=location,
        reminder_minutes=reminder_minutes,
        time_zone=timezone,
        calendar_id=calendar_id,
    )


@mcp.tool
def end_calendar_series(recurring_event_id: str, last_day: str, calendar_id: str = "primary") -> dict[str, Any]:
    """Stop a recurring series after last_day (YYYY-MM-DD), keeping that day and earlier occurrences."""
    return end_recurring_series(recurring_event_id, date.fromisoformat(last_day), calendar_id=calendar_id)


@mcp.tool
def delete_calendar_event(event_id: str, calendar_id: str = "primary") -> dict[str, str]:
    """Delete a Google Calendar event by id; pass a recurring_event_id to delete the whole series."""
    delete_event(event_id, calendar_id=calendar_id)
    return {"deleted": event_id}
