"""Google Calendar event operations."""

from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

from alfred.google_auth import (
    CALENDAR_EVENTS_SCOPE,
    CALENDAR_LIST_SCOPE,
    REQUEST_TIMEOUT_SECONDS,
    GoogleAPIError,
    check_response,
    get_credentials,
)

GOOGLE_API_URL = "https://www.googleapis.com/calendar/v3"
CALENDAR_API_URL = f"{GOOGLE_API_URL}/calendars"
CALENDAR_LIST_URL = f"{GOOGLE_API_URL}/users/me/calendarList"
EVENTS_SCOPE = CALENDAR_EVENTS_SCOPE
MAX_EVENTS = 10000
PAGE_SIZE = 2500

# Calendar failures are GoogleAPIError; the old name is kept for callers.
CalendarError = GoogleAPIError


def _get_credentials(required_scope: str = EVENTS_SCOPE) -> Credentials:
    return get_credentials(required_scope)


def _check_response(response: Any, what: str) -> None:
    check_response(response, what, "event or calendar")


def _calendar_url(calendar_id: str) -> str:
    return f"{CALENDAR_API_URL}/{quote(calendar_id, safe='')}/events"


def _event_url(calendar_id: str, event_id: str) -> str:
    if not event_id.strip():
        raise ValueError("event_id must not be empty")
    return f"{_calendar_url(calendar_id)}/{quote(event_id.strip(), safe='')}"


def _validate_time_range(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("start must include a timezone")
    if end.tzinfo is None or end.utcoffset() is None:
        raise ValueError("end must include a timezone")
    if end <= start:
        raise ValueError("end must be later than start")


def _validate_event_range(start: date, end: date) -> None:
    start_is_datetime = isinstance(start, datetime)
    if start_is_datetime != isinstance(end, datetime):
        raise ValueError("start and end must both be dates or both be datetimes")
    if start_is_datetime:
        _validate_time_range(start, end)  # type: ignore[arg-type]
    elif end <= start:
        raise ValueError("end must be later than start")


def _event_time(value: date, time_zone: str | None = None) -> dict[str, str | None]:
    """Build a Google start/end object, clearing the other field so a PATCH can switch kinds."""
    if isinstance(value, datetime):
        event_time: dict[str, str | None] = {"dateTime": value.isoformat(), "date": None}
        if time_zone:
            event_time["timeZone"] = time_zone
        return event_time
    return {"date": value.isoformat(), "dateTime": None}


def _reminders(reminder_minutes: list[int]) -> dict[str, Any]:
    if any(not 0 <= minutes <= 40320 for minutes in reminder_minutes):
        raise ValueError("reminder minutes must be between 0 and 40320")
    return {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": minutes} for minutes in reminder_minutes],
    }


def _validate_recurrence(recurrence: list[str]) -> None:
    for rule in recurrence:
        if not rule.startswith(("RRULE:", "EXDATE", "RDATE")):
            raise ValueError(f"invalid recurrence rule: {rule!r}")


def _event_times(event: dict[str, Any]) -> tuple[str, str]:
    start = event.get("start", {})
    end = event.get("end", {})
    return str(start.get("dateTime", start.get("date", ""))), str(end.get("dateTime", end.get("date", "")))


def _reminder_minutes(event: dict[str, Any]) -> list[int] | None:
    """Return popup reminder minutes, or None when the calendar's default reminders apply."""
    reminders = event.get("reminders", {})
    if reminders.get("useDefault", True):
        return None
    return sorted(int(override["minutes"]) for override in reminders.get("overrides", []))


def _format_event(event: dict[str, Any]) -> dict[str, Any]:
    start, end = _event_times(event)
    return {
        "id": str(event.get("id", "")),
        "recurring_event_id": str(event.get("recurringEventId", "")),
        "summary": str(event.get("summary", "Senza titolo")),
        "start": start,
        "end": end,
        "all_day": "date" in event.get("start", {}),
        "description": str(event.get("description", "")),
        "location": str(event.get("location", "")),
        "reminder_minutes": _reminder_minutes(event),
        "busy": event.get("transparency", "opaque") != "transparent",
        "event_type": str(event.get("eventType", "default")),
        "html_link": str(event.get("htmlLink", "")),
    }


def _format_event_details(event: dict[str, Any]) -> dict[str, Any]:
    details = _format_event(event)
    details.update(
        {
            "recurrence": list(event.get("recurrence", [])),
            "status": str(event.get("status", "")),
            "created": str(event.get("created", "")),
            "updated": str(event.get("updated", "")),
            "creator": str(event.get("creator", {}).get("email", "")),
        }
    )
    return details


def list_events(
    start: datetime,
    end: datetime,
    *,
    query: str | None = None,
    calendar_id: str = "primary",
    max_results: int = 20,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """List calendar events in the timezone-aware interval [start, end)."""
    events: list[dict[str, Any]] = search_events(
        start, end, query=query, calendar_id=calendar_id, max_results=max_results, session=session
    )["events"]
    return events


def search_events(
    start: datetime,
    end: datetime,
    *,
    query: str | None = None,
    calendar_id: str = "primary",
    max_results: int = 20,
    session: Any | None = None,
) -> dict[str, Any]:
    """Return ``{"events": [...], "truncated": bool}`` for [start, end), following result pages.

    ``query`` is Google's free-text search over title, description, location and attendees.
    ``truncated`` is true when more matching events exist beyond ``max_results``.
    """
    _validate_time_range(start, end)
    if not 1 <= max_results <= MAX_EVENTS:
        raise ValueError(f"max_results must be between 1 and {MAX_EVENTS}")

    authorized_session = session or AuthorizedSession(_get_credentials())
    params: dict[str, str | int] = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    if query and query.strip():
        params["q"] = query.strip()

    items: list[dict[str, Any]] = []
    truncated = False
    while True:
        # Ask for one extra event so we can tell whether the result was cut off.
        params["maxResults"] = min(PAGE_SIZE, max_results + 1 - len(items))
        response = authorized_session.get(
            _calendar_url(calendar_id),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _check_response(response, "list events")
        page = response.json()
        items.extend(page.get("items", []))
        if len(items) > max_results:
            truncated = True
            break
        next_page = page.get("nextPageToken")
        if not next_page:
            break
        params["pageToken"] = next_page

    return {"events": [_format_event(event) for event in items[:max_results]], "truncated": truncated}


def check_availability(
    start: datetime,
    end: datetime,
    *,
    calendar_id: str = "primary",
    session: Any | None = None,
) -> dict[str, Any]:
    """Report whether [start, end) is free, listing overlapping busy and free-marked events."""
    events = list_events(start, end, calendar_id=calendar_id, max_results=250, session=session)
    busy = [event for event in events if event["busy"]]
    return {
        "free": not busy,
        "conflicts": busy,
        "other_events": [event for event in events if not event["busy"]],
    }


def list_calendars(*, session: Any | None = None) -> list[dict[str, Any]]:
    """List the calendars the user can see, with the id to pass as ``calendar_id``."""
    authorized_session = session or AuthorizedSession(_get_credentials(CALENDAR_LIST_SCOPE))
    calendars: list[dict[str, Any]] = []
    params: dict[str, str | int] = {"maxResults": 250}
    while True:
        response = authorized_session.get(CALENDAR_LIST_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        _check_response(response, "list calendars")
        page = response.json()
        calendars.extend(
            {
                "id": str(item.get("id", "")),
                "summary": str(item.get("summaryOverride", item.get("summary", ""))),
                "primary": bool(item.get("primary", False)),
                "access_role": str(item.get("accessRole", "")),
                "time_zone": str(item.get("timeZone", "")),
            }
            for item in page.get("items", [])
        )
        next_page = page.get("nextPageToken")
        if not next_page:
            return calendars
        params["pageToken"] = next_page


def _get_raw_event(event_id: str, calendar_id: str, session: Any) -> dict[str, Any]:
    response = session.get(_event_url(calendar_id, event_id), timeout=REQUEST_TIMEOUT_SECONDS)
    _check_response(response, "read the event")
    event: dict[str, Any] = response.json()
    return event


def get_event(
    event_id: str,
    *,
    calendar_id: str = "primary",
    session: Any | None = None,
) -> dict[str, Any]:
    """Return an event's full details, including recurrence rules for a series id."""
    authorized_session = session or AuthorizedSession(_get_credentials())
    return _format_event_details(_get_raw_event(event_id, calendar_id, authorized_session))


def create_event(
    summary: str,
    start: date,
    end: date,
    *,
    description: str = "",
    location: str = "",
    reminder_minutes: list[int] | None = None,
    recurrence: list[str] | None = None,
    time_zone: str | None = None,
    calendar_id: str = "primary",
    session: Any | None = None,
) -> dict[str, Any]:
    """Create a Google Calendar event and return its normalized details.

    Pass datetimes for a timed event, or dates for an all-day event (end date exclusive).
    ``recurrence`` takes RFC 5545 lines such as ``RRULE:FREQ=WEEKLY``; ``time_zone`` is an IANA
    name and is required by Google for recurring timed events.
    """
    _validate_event_range(start, end)
    if not summary.strip():
        raise ValueError("summary must not be empty")

    event: dict[str, Any] = {
        "summary": summary.strip(),
        "description": description,
        "location": location,
        "start": _event_time(start, time_zone),
        "end": _event_time(end, time_zone),
    }
    if reminder_minutes is not None:
        event["reminders"] = _reminders(reminder_minutes)
    if recurrence:
        _validate_recurrence(recurrence)
        event["recurrence"] = recurrence
    authorized_session = session or AuthorizedSession(_get_credentials())
    response = authorized_session.post(
        _calendar_url(calendar_id),
        json=event,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _check_response(response, "create the event")
    return _format_event(response.json())


def update_event(
    event_id: str,
    *,
    summary: str | None = None,
    start: date | None = None,
    end: date | None = None,
    description: str | None = None,
    location: str | None = None,
    reminder_minutes: list[int] | None = None,
    time_zone: str | None = None,
    calendar_id: str = "primary",
    session: Any | None = None,
) -> dict[str, Any]:
    """Update only the given fields of a Google Calendar event and return its normalized details.

    ``start``/``end`` may be datetimes (timed event) or dates (all-day event, end exclusive).
    """
    url = _event_url(calendar_id, event_id)
    if (start is None) != (end is None):
        raise ValueError("start and end must be updated together")
    if start is not None and end is not None:
        _validate_event_range(start, end)
    if summary is not None and not summary.strip():
        raise ValueError("summary must not be empty")

    changes: dict[str, Any] = {}
    if summary is not None:
        changes["summary"] = summary.strip()
    if description is not None:
        changes["description"] = description
    if location is not None:
        changes["location"] = location
    if reminder_minutes is not None:
        changes["reminders"] = _reminders(reminder_minutes)
    if start is not None and end is not None:
        changes["start"] = _event_time(start, time_zone)
        changes["end"] = _event_time(end, time_zone)
    if not changes:
        raise ValueError("no fields to update")

    authorized_session = session or AuthorizedSession(_get_credentials())
    response = authorized_session.patch(url, json=changes, timeout=REQUEST_TIMEOUT_SECONDS)
    _check_response(response, "update the event")
    return _format_event(response.json())


def _rrule_until(series: dict[str, Any], last_day: date) -> str:
    """Return the UNTIL value that keeps occurrences up to and including ``last_day``."""
    series_start = series.get("start", {})
    if "date" in series_start:
        return last_day.strftime("%Y%m%d")
    time_zone = series_start.get("timeZone")
    end_of_day = datetime.combine(last_day, datetime.max.time().replace(microsecond=0))
    if time_zone:
        end_of_day = end_of_day.replace(tzinfo=ZoneInfo(time_zone))
    else:
        end_of_day = end_of_day.replace(tzinfo=datetime.fromisoformat(series_start["dateTime"]).tzinfo)
    return end_of_day.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def end_recurring_series(
    series_id: str,
    last_day: date,
    *,
    calendar_id: str = "primary",
    session: Any | None = None,
) -> dict[str, Any]:
    """Stop a recurring series after ``last_day``, keeping earlier occurrences."""
    authorized_session = session or AuthorizedSession(_get_credentials())
    series = _get_raw_event(series_id, calendar_id, authorized_session)
    recurrence: list[str] = list(series.get("recurrence", []))
    if not any(rule.startswith("RRULE:") for rule in recurrence):
        raise ValueError("event is not a recurring series; pass its recurring_event_id")
    first_day = date.fromisoformat(_event_times(series)[0][:10])
    if last_day < first_day:
        raise ValueError("last_day is before the series starts; delete the series instead")

    until = _rrule_until(series, last_day)
    new_recurrence = []
    for rule in recurrence:
        if rule.startswith("RRULE:"):
            parts = [p for p in rule[len("RRULE:") :].split(";") if not p.startswith(("UNTIL=", "COUNT="))]
            rule = "RRULE:" + ";".join([*parts, f"UNTIL={until}"])
        new_recurrence.append(rule)

    response = authorized_session.patch(
        _event_url(calendar_id, series_id),
        json={"recurrence": new_recurrence},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _check_response(response, "end the recurring series")
    return _format_event_details(response.json())


def delete_event(
    event_id: str,
    *,
    calendar_id: str = "primary",
    session: Any | None = None,
) -> None:
    """Delete a Google Calendar event; a recurring event's series id deletes every occurrence.

    Contact birthdays (``event_type == "birthday"``) cannot be deleted here: remove the
    birthday from Google Contacts instead.
    """
    url = _event_url(calendar_id, event_id)
    authorized_session = session or AuthorizedSession(_get_credentials())
    response = authorized_session.delete(url, timeout=REQUEST_TIMEOUT_SECONDS)
    _check_response(response, "delete the event")
