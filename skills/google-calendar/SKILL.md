---
name: google-calendar
description: Use when the user asks Alfred to check, create, change, or delete Google Calendar appointments, reminders, or recurring events.
---

# Google Calendar

Use the `google-workspace` MCP tools to read, create, update, and delete events in the user's Google Calendar. Every tool uses the primary calendar unless you pass a `calendar_id`; get the ids with `list_google_calendars` when the user names another calendar (for example "Famiglia").

Event results include `all_day`, `reminder_minutes` (`null` means the calendar defaults), `busy` (false for events marked free), `event_type`, and `recurring_event_id` (set when the event is one occurrence of a series). Use `get_calendar_event` with a `recurring_event_id` to read the series' `recurrence` rules, creator, and creation date.

Reminder minutes count back from the event start. For all-day events the start is local midnight, so 480 means 16:00 the day before and 420 means 17:00 the day before.

Create, update, or delete events only at the user's explicit request. When an appointment needs a personal detail (for example travel from home, or whose birthday it is), read it with `get_user_profile` from the `user-profile` server instead of asking again.

## List appointments

1. Interpret relative dates in the timezone configured in Alfred, currently `Europe/Rome`.
2. Call `list_calendar_events` with a start and end that cover the requested period; `YYYY-MM-DD` means local midnight. For a day, use that day to the next day. To find events by name (for example "tutti i Dentista del 2026"), pass `query`.
3. The result is `{"events": [...], "truncated": bool}`. If `truncated` is true, say so and narrow the range or raise `max_results` instead of presenting a partial list as complete.
4. Summarize the returned appointments in Italian, including local start/end time, title, and location when present. Mark recurring events and custom reminders when relevant. Say clearly when there are no events.

## Check availability

1. For questions like "sono libero venerdì alle 10?", call `check_calendar_availability` with the slot; with no duration given, assume one hour and say so.
2. Report `conflicts` (busy events, including all-day ones such as Ferie). Mention `other_events` (for example birthdays) only as information: they do not make the slot busy.

## Create an event

1. Collect or infer the title, start, end, and optional location/description. Interpret local times in Alfred's configured timezone.
2. If the date, time, or duration is ambiguous, ask a clarifying question instead of guessing.
3. Call `check_calendar_availability` for timed events and mention any conflict. Call `list_calendar_events` for the target days and skip any event that already exists with the same title and date, to avoid duplicates.
4. For all-day events pass `YYYY-MM-DD` dates; `end` is exclusive (the day after the last day).
5. Set `reminder_minutes` at creation. Check the user's reminder preferences in `get_user_profile` (for example `important_event_reminders` for appointments like the dentist) and propose them; otherwise the calendar defaults apply, which may add several popups. Never treat reminders that match a saved preference as duplicates to clean up. For a repeating event pass `recurrence`, for example `["RRULE:FREQ=MONTHLY;BYMONTHDAY=15"]`.
6. State the event details and obtain explicit confirmation before calling `create_calendar_event`.
7. After success, confirm the created event using the returned details. Never claim success if the tool call failed.

## Update an event

1. Find the event with `list_calendar_events` and use its `id` (or `recurring_event_id` to change the whole series, after asking which one the user means).
2. Call `update_calendar_event` with only the fields that change; `start` and `end` must be passed together, as `YYYY-MM-DD` for all-day events. `reminder_minutes` replaces all existing notifications; `[]` removes them.
3. For a simple rename or detail the user stated explicitly, proceed directly; for time changes, state the new details and get confirmation first.
4. Confirm the result using the returned details.

## Delete an event

1. Find the event with `list_calendar_events`. If `event_type` is `birthday`, it comes from Google Contacts and cannot be deleted here: tell the user to remove the birthday from the contact instead.
2. If it has a `recurring_event_id`, it is one occurrence of a series. Use `get_calendar_event` to describe the series, then ask whether to delete only that occurrence (`id`), stop the series from a date onward, or delete the whole series (`recurring_event_id`). Deleting the series also removes past occurrences.
3. To stop a series while keeping its history, call `end_calendar_series` with the `recurring_event_id` and the last day to keep.
4. State exactly what will be deleted or stopped and obtain explicit confirmation before calling `delete_calendar_event` or `end_calendar_series`.
5. After success, verify with `list_calendar_events` that the event is gone. Never claim success if the tool call failed.

## Initial setup

If a tool reports that Google is not authorized, that the authorization lacks a permission, or that a Google API is not enabled, follow the `connect-google` skill.
