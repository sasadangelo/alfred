"""Tests for Google Calendar event operations."""

from datetime import date, datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import requests

from alfred.calendar import (
    CalendarError,
    check_availability,
    create_event,
    delete_event,
    end_recurring_series,
    get_event,
    list_calendars,
    list_events,
    search_events,
    update_event,
)

ROME = ZoneInfo("Europe/Rome")
START = datetime(2026, 11, 12, 9, 0, tzinfo=ROME)
END = datetime(2026, 11, 12, 10, 0, tzinfo=ROME)


def test_list_events_returns_normalized_events() -> None:
    session = Mock()
    response = Mock()
    response.json.return_value = {
        "items": [
            {
                "id": "event-1",
                "summary": "Riunione",
                "start": {"dateTime": "2026-11-12T09:00:00+01:00"},
                "end": {"dateTime": "2026-11-12T10:00:00+01:00"},
                "location": "Roma",
                "htmlLink": "https://calendar.google.com/event-1",
            }
        ]
    }
    session.get.return_value = response

    events = list_events(START, END, session=session)

    assert events == [
        {
            "id": "event-1",
            "recurring_event_id": "",
            "summary": "Riunione",
            "start": "2026-11-12T09:00:00+01:00",
            "end": "2026-11-12T10:00:00+01:00",
            "all_day": False,
            "description": "",
            "location": "Roma",
            "reminder_minutes": None,
            "busy": True,
            "event_type": "default",
            "html_link": "https://calendar.google.com/event-1",
        }
    ]
    session.get.assert_called_once()
    assert session.get.call_args.kwargs["params"]["orderBy"] == "startTime"
    response.raise_for_status.assert_called_once_with()


def test_list_events_supports_all_day_events() -> None:
    session = Mock()
    session.get.return_value.json.return_value = {
        "items": [{"start": {"date": "2026-11-12"}, "end": {"date": "2026-11-13"}}]
    }

    events = list_events(START, END, session=session)

    assert events[0]["start"] == "2026-11-12"
    assert events[0]["end"] == "2026-11-13"


def test_create_event_sends_event_and_returns_normalized_details() -> None:
    session = Mock()
    session.post.return_value.json.return_value = {
        "id": "event-2",
        "summary": "Dentista",
        "start": {"dateTime": "2026-11-12T09:00:00+01:00"},
        "end": {"dateTime": "2026-11-12T10:00:00+01:00"},
    }

    event = create_event(" Dentista ", START, END, location="Roma", session=session)

    assert event["id"] == "event-2"
    assert event["summary"] == "Dentista"
    assert session.post.call_args.kwargs["json"] == {
        "summary": "Dentista",
        "description": "",
        "location": "Roma",
        "start": {"dateTime": START.isoformat(), "date": None},
        "end": {"dateTime": END.isoformat(), "date": None},
    }


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (datetime(2026, 11, 12, 9), END, "start must include a timezone"),
        (START, datetime(2026, 11, 12, 10), "end must include a timezone"),
        (END, START, "end must be later than start"),
    ],
)
def test_create_event_rejects_invalid_time_range(start: datetime, end: datetime, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_event("Appuntamento", start, end, session=Mock())


def test_create_event_supports_all_day_events() -> None:
    session = Mock()
    session.post.return_value.json.return_value = {"start": {"date": "2026-12-21"}, "end": {"date": "2026-12-26"}}

    event = create_event("Ferie", date(2026, 12, 21), date(2026, 12, 26), session=session)

    assert session.post.call_args.kwargs["json"]["start"] == {"date": "2026-12-21", "dateTime": None}
    assert session.post.call_args.kwargs["json"]["end"] == {"date": "2026-12-26", "dateTime": None}
    assert event["start"] == "2026-12-21"
    assert event["all_day"] is True


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (date(2026, 12, 21), START, "both be dates or both be datetimes"),
        (date(2026, 12, 21), date(2026, 12, 21), "end must be later than start"),
    ],
)
def test_create_event_rejects_invalid_all_day_range(start: date, end: date, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_event("Ferie", start, end, session=Mock())


def test_create_event_rejects_empty_summary() -> None:
    with pytest.raises(ValueError, match="summary must not be empty"):
        create_event("  ", START, END, session=Mock())


def test_delete_event_sends_delete_request() -> None:
    session = Mock()

    delete_event("series-1", session=session)

    session.delete.assert_called_once()
    assert session.delete.call_args.args[0].endswith("/calendars/primary/events/series-1")
    session.delete.return_value.raise_for_status.assert_called_once_with()


def test_delete_event_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="event_id must not be empty"):
        delete_event("  ", session=Mock())


def test_update_event_patches_only_given_fields() -> None:
    session = Mock()
    session.patch.return_value.json.return_value = {
        "id": "event-1",
        "summary": "Dentista",
        "start": {"dateTime": "2026-11-12T09:00:00+01:00"},
        "end": {"dateTime": "2026-11-12T10:00:00+01:00"},
    }

    event = update_event("event-1", summary=" Dentista ", session=session)

    assert session.patch.call_args.args[0].endswith("/calendars/primary/events/event-1")
    assert session.patch.call_args.kwargs["json"] == {"summary": "Dentista"}
    assert event["summary"] == "Dentista"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "no fields to update"),
        ({"start": START}, "start and end must be updated together"),
        ({"summary": " "}, "summary must not be empty"),
    ],
)
def test_update_event_rejects_invalid_changes(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        update_event("event-1", session=Mock(), **kwargs)  # type: ignore[arg-type]


def test_update_event_replaces_reminders() -> None:
    session = Mock()
    session.patch.return_value.json.return_value = {}

    update_event("event-1", reminder_minutes=[420], session=session)

    assert session.patch.call_args.kwargs["json"] == {
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 420}]}
    }


def test_update_event_rejects_invalid_reminder() -> None:
    with pytest.raises(ValueError, match="reminder minutes must be between"):
        update_event("event-1", reminder_minutes=[-1], session=Mock())


def test_list_events_reports_custom_reminders_and_event_type() -> None:
    session = Mock()
    session.get.return_value.json.return_value = {
        "items": [
            {
                "start": {"date": "2026-11-14"},
                "end": {"date": "2026-11-15"},
                "eventType": "birthday",
                "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 480}]},
            }
        ]
    }

    event = list_events(START, END, session=session)[0]

    assert event["reminder_minutes"] == [480]
    assert event["event_type"] == "birthday"


def test_get_event_returns_recurrence_and_metadata() -> None:
    session = Mock()
    session.get.return_value.json.return_value = {
        "id": "series-1",
        "summary": "Oliare serrature",
        "start": {"date": "2020-06-15"},
        "end": {"date": "2020-06-16"},
        "recurrence": ["RRULE:FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=15"],
        "created": "2020-06-01T10:00:00.000Z",
        "creator": {"email": "me@example.com"},
        "status": "confirmed",
    }

    event = get_event("series-1", session=session)

    assert session.get.call_args.args[0].endswith("/calendars/primary/events/series-1")
    assert event["recurrence"] == ["RRULE:FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=15"]
    assert event["creator"] == "me@example.com"
    assert event["created"] == "2020-06-01T10:00:00.000Z"


def test_create_event_sends_reminders_recurrence_and_time_zone() -> None:
    session = Mock()
    session.post.return_value.json.return_value = {}

    create_event(
        "Pulizia",
        START,
        END,
        reminder_minutes=[60],
        recurrence=["RRULE:FREQ=WEEKLY"],
        time_zone="Europe/Rome",
        session=session,
    )

    body = session.post.call_args.kwargs["json"]
    assert body["reminders"] == {"useDefault": False, "overrides": [{"method": "popup", "minutes": 60}]}
    assert body["recurrence"] == ["RRULE:FREQ=WEEKLY"]
    assert body["start"]["timeZone"] == "Europe/Rome"


def test_create_event_rejects_invalid_recurrence() -> None:
    with pytest.raises(ValueError, match="invalid recurrence rule"):
        create_event("Pulizia", START, END, recurrence=["FREQ=WEEKLY"], session=Mock())


def test_update_event_can_move_all_day_event() -> None:
    session = Mock()
    session.patch.return_value.json.return_value = {}

    update_event("event-1", start=date(2026, 12, 8), end=date(2026, 12, 9), session=session)

    assert session.patch.call_args.kwargs["json"] == {
        "start": {"date": "2026-12-08", "dateTime": None},
        "end": {"date": "2026-12-09", "dateTime": None},
    }


def _series_session(series: dict[str, object]) -> Mock:
    session = Mock()
    session.get.return_value.json.return_value = series
    session.patch.return_value.json.return_value = series
    return session


def test_end_recurring_series_sets_until_for_all_day_series() -> None:
    session = _series_session(
        {
            "start": {"date": "2022-06-15"},
            "recurrence": ["EXDATE;VALUE=DATE:20230215", "RRULE:FREQ=MONTHLY;BYMONTHDAY=15;COUNT=99"],
        }
    )

    end_recurring_series("series-1", date(2026, 10, 15), session=session)

    assert session.patch.call_args.kwargs["json"] == {
        "recurrence": ["EXDATE;VALUE=DATE:20230215", "RRULE:FREQ=MONTHLY;BYMONTHDAY=15;UNTIL=20261015"]
    }


def test_end_recurring_series_uses_utc_until_for_timed_series() -> None:
    session = _series_session(
        {
            "start": {"dateTime": "2022-06-15T10:00:00+02:00", "timeZone": "Europe/Rome"},
            "recurrence": ["RRULE:FREQ=MONTHLY;BYMONTHDAY=15"],
        }
    )

    end_recurring_series("series-1", date(2026, 10, 15), session=session)

    assert session.patch.call_args.kwargs["json"] == {
        "recurrence": ["RRULE:FREQ=MONTHLY;BYMONTHDAY=15;UNTIL=20261015T215959Z"]
    }


@pytest.mark.parametrize(
    ("series", "last_day", "message"),
    [
        ({"start": {"date": "2022-06-15"}}, date(2026, 10, 15), "not a recurring series"),
        (
            {"start": {"date": "2022-06-15"}, "recurrence": ["RRULE:FREQ=YEARLY"]},
            date(2021, 1, 1),
            "before the series starts",
        ),
    ],
)
def test_end_recurring_series_rejects_invalid_requests(series: dict[str, object], last_day: date, message: str) -> None:
    session = _series_session(series)

    with pytest.raises(ValueError, match=message):
        end_recurring_series("series-1", last_day, session=session)

    session.patch.assert_not_called()


def _page(items: list[dict[str, object]], next_page: str | None = None) -> Mock:
    response = Mock()
    response.json.return_value = {"items": items, **({"nextPageToken": next_page} if next_page else {})}
    return response


def _timed(event_id: str, **extra: object) -> dict[str, object]:
    return {
        "id": event_id,
        "start": {"dateTime": "2026-11-12T09:00:00+01:00"},
        "end": {"dateTime": "2026-11-12T10:00:00+01:00"},
        **extra,
    }


def test_search_events_follows_pages_and_sends_query() -> None:
    session = Mock()
    session.get.side_effect = [_page([_timed("a")], next_page="p2"), _page([_timed("b")])]

    result = search_events(START, END, query=" Dentista ", max_results=50, session=session)

    assert [event["id"] for event in result["events"]] == ["a", "b"]
    assert result["truncated"] is False
    second_params = session.get.call_args_list[1].kwargs["params"]
    assert second_params["pageToken"] == "p2"
    assert second_params["q"] == "Dentista"


def test_search_events_reports_truncation() -> None:
    session = Mock()
    session.get.return_value = _page([_timed("a"), _timed("b"), _timed("c")])

    result = search_events(START, END, max_results=2, session=session)

    assert [event["id"] for event in result["events"]] == ["a", "b"]
    assert result["truncated"] is True
    assert session.get.call_args.kwargs["params"]["maxResults"] == 3


def test_check_availability_separates_busy_and_free_events() -> None:
    session = Mock()
    session.get.return_value = _page([_timed("meeting"), _timed("birthday", transparency="transparent")])

    result = check_availability(START, END, session=session)

    assert result["free"] is False
    assert [event["id"] for event in result["conflicts"]] == ["meeting"]
    assert [event["id"] for event in result["other_events"]] == ["birthday"]


def test_check_availability_is_free_without_busy_events() -> None:
    session = Mock()
    session.get.return_value = _page([])

    assert check_availability(START, END, session=session)["free"] is True


def test_list_calendars_returns_ids_and_names() -> None:
    session = Mock()
    session.get.return_value.json.return_value = {
        "items": [
            {"id": "me@example.com", "summary": "Me", "primary": True, "accessRole": "owner"},
            {"id": "family", "summary": "Famiglia", "summaryOverride": "Casa", "accessRole": "writer"},
        ]
    }

    calendars = list_calendars(session=session)

    assert [(c["id"], c["summary"], c["primary"]) for c in calendars] == [
        ("me@example.com", "Me", True),
        ("family", "Casa", False),
    ]


def _http_error_response(status: int, message: str = "") -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = {"error": {"message": message}}
    response.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    return response


@pytest.mark.parametrize(
    ("status", "google_message", "expected"),
    [
        (404, "Not Found", "not found"),
        (410, "Resource has been deleted", "already been deleted"),
        (403, "Request had insufficient authentication scopes.", "authorize-google.sh"),
        (401, "Invalid Credentials", "authorize-google.sh"),
        (400, "Invalid recurrence rule", "Invalid recurrence rule"),
        (503, "Backend Error", "temporarily unavailable"),
    ],
)
def test_google_errors_become_clear_calendar_errors(status: int, google_message: str, expected: str) -> None:
    session = Mock()
    session.delete.return_value = _http_error_response(status, google_message)

    with pytest.raises(CalendarError, match=expected):
        delete_event("event-1", session=session)
