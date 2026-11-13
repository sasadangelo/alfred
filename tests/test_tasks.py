"""Tests for Google Tasks operations."""

from datetime import date
from typing import Any
from unittest.mock import Mock

import pytest

from alfred import tasks

TODAY = date(2026, 11, 13)


def _page(items: list[dict[str, Any]], next_page: str | None = None) -> Mock:
    response = Mock()
    response.json.return_value = {"items": items, **({"nextPageToken": next_page} if next_page else {})}
    return response


def _task(task_id: str, title: str, due: str | None = None, **extra: Any) -> dict[str, Any]:
    task: dict[str, Any] = {"id": task_id, "title": title, "status": "needsAction", **extra}
    if due:
        task["due"] = f"{due}T00:00:00.000Z"
    return task


def test_list_task_lists_follows_pages() -> None:
    session = Mock()
    session.get.side_effect = [_page([{"id": "a", "title": "Casa"}], "p2"), _page([{"id": "b", "title": "Auto"}])]

    lists = tasks.list_task_lists(session=session)

    assert lists == [{"id": "a", "title": "Casa"}, {"id": "b", "title": "Auto"}]
    assert session.get.call_args_list[1].kwargs["params"]["pageToken"] == "p2"


def test_list_tasks_formats_sorts_and_flags_overdue() -> None:
    session = Mock()
    session.get.return_value = _page(
        [
            _task("3", "Senza data"),
            _task("2", "Bollo auto", "2026-11-30", notes="Peugeot", webViewLink="https://tasks/2"),
            _task("1", "Assicurazione", "2026-11-10"),
        ]
    )

    result = tasks.list_tasks(today=TODAY, session=session)

    assert [task["id"] for task in result] == ["1", "2", "3"]
    assert result[0]["overdue"] is True
    assert result[1] == {
        "id": "2",
        "tasklist_id": "@default",
        "title": "Bollo auto",
        "notes": "Peugeot",
        "due": "2026-11-30",
        "status": "open",
        "completed_at": "",
        "overdue": False,
        "parent_id": "",
        "web_link": "https://tasks/2",
    }
    params = session.get.call_args.kwargs["params"]
    assert params["showCompleted"] == "false"
    assert session.get.call_args.args[0].endswith("/lists/@default/tasks")


def test_list_tasks_filters_by_due_range_and_query() -> None:
    session = Mock()
    session.get.return_value = _page(
        [
            _task("1", "Bollo auto", "2026-11-20"),
            _task("2", "Revisione", "2026-12-20", notes="auto Clio"),
            _task("3", "Spesa", "2026-11-21"),
            _task("4", "Auto senza data"),
        ]
    )

    result = tasks.list_tasks(due_from=date(2026, 11, 1), due_to=date(2026, 11, 30), query="AUTO", session=session)

    assert [task["id"] for task in result] == ["1"]


def test_list_tasks_includes_completed_and_hidden_on_request() -> None:
    session = Mock()
    session.get.return_value = _page([_task("1", "Fatto", status="completed", completed="2026-11-12T10:00:00Z")])

    result = tasks.list_tasks(include_completed=True, today=TODAY, session=session)

    assert result[0]["status"] == "completed"
    assert result[0]["overdue"] is False
    params = session.get.call_args.kwargs["params"]
    assert params["showCompleted"] == "true"
    assert params["showHidden"] == "true"


def test_list_tasks_across_all_lists_adds_list_title() -> None:
    session = Mock()
    session.get.side_effect = [
        _page([{"id": "casa", "title": "Casa"}, {"id": "auto", "title": "Auto"}]),
        _page([_task("1", "Lavatrice")]),
        _page([_task("2", "Gomme")]),
    ]

    result = tasks.list_tasks(tasklist_id=None, session=session)

    assert {(task["title"], task["tasklist_id"], task["tasklist_title"]) for task in result} == {
        ("Lavatrice", "casa", "Casa"),
        ("Gomme", "auto", "Auto"),
    }


def test_create_task_sends_date_only_due_and_parent() -> None:
    session = Mock()
    session.post.return_value.json.return_value = _task("9", "Bollo", "2026-11-30")

    task = tasks.create_task(
        " Bollo ", notes="Peugeot", due=date(2026, 11, 30), parent_id="p1", today=TODAY, session=session
    )

    assert session.post.call_args.kwargs["json"] == {
        "title": "Bollo",
        "notes": "Peugeot",
        "due": "2026-11-30T00:00:00.000Z",
    }
    assert session.post.call_args.kwargs["params"] == {"parent": "p1"}
    assert task["due"] == "2026-11-30"


def test_create_task_rejects_empty_title() -> None:
    with pytest.raises(ValueError, match="title must not be empty"):
        tasks.create_task("  ", session=Mock())


def test_update_task_patches_only_given_fields_and_can_clear_due() -> None:
    session = Mock()
    session.patch.return_value.json.return_value = _task("9", "Bollo")

    tasks.update_task("9", title="Bollo Peugeot", clear_due=True, session=session)

    assert session.patch.call_args.args[0].endswith("/lists/@default/tasks/9")
    assert session.patch.call_args.kwargs["json"] == {"title": "Bollo Peugeot", "due": None}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "no fields to update"),
        ({"due": date(2026, 11, 30), "clear_due": True}, "either due or clear_due"),
        ({"title": " "}, "title must not be empty"),
    ],
)
def test_update_task_rejects_invalid_changes(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        tasks.update_task("9", session=Mock(), **kwargs)


def test_complete_and_reopen_task() -> None:
    session = Mock()
    session.patch.return_value.json.return_value = _task("9", "Bollo")

    tasks.complete_task("9", tasklist_id="auto", session=session)
    assert session.patch.call_args.kwargs["json"] == {"status": "completed"}
    assert "/lists/auto/tasks/9" in session.patch.call_args.args[0]

    tasks.reopen_task("9", session=session)
    assert session.patch.call_args.kwargs["json"] == {"status": "needsAction", "completed": None}


def test_move_task_to_another_list() -> None:
    session = Mock()
    session.post.return_value.json.return_value = _task("9", "Bollo")

    task = tasks.move_task("9", destination_tasklist_id="auto", session=session)

    assert session.post.call_args.args[0].endswith("/lists/@default/tasks/9/move")
    assert session.post.call_args.kwargs["params"] == {"destinationTasklist": "auto"}
    assert task["tasklist_id"] == "auto"


def test_move_task_requires_a_destination() -> None:
    with pytest.raises(ValueError, match="destination_tasklist_id and/or parent_id"):
        tasks.move_task("9", session=Mock())


def test_delete_and_clear_completed() -> None:
    session = Mock()

    tasks.delete_task("9", session=session)
    tasks.clear_completed_tasks("auto", session=session)

    assert session.delete.call_args.args[0].endswith("/lists/@default/tasks/9")
    assert session.post.call_args.args[0].endswith("/lists/auto/clear")


def test_create_task_list() -> None:
    session = Mock()
    session.post.return_value.json.return_value = {"id": "new", "title": "Auto"}

    assert tasks.create_task_list(" Auto ", session=session) == {"id": "new", "title": "Auto"}
    assert session.post.call_args.kwargs["json"] == {"title": "Auto"}


def test_rename_task_list() -> None:
    session = Mock()
    session.patch.return_value.json.return_value = {"id": "l1", "title": "Lavoro"}

    assert tasks.rename_task_list("l1", " Lavoro ", session=session) == {"id": "l1", "title": "Lavoro"}
    assert session.patch.call_args.args[0].endswith("/users/@me/lists/l1")
    assert session.patch.call_args.kwargs["json"] == {"title": "Lavoro"}


def test_delete_task_list() -> None:
    session = Mock()

    tasks.delete_task_list("l1", session=session)

    assert session.delete.call_args.args[0].endswith("/users/@me/lists/l1")


def test_delete_task_list_refuses_default_list() -> None:
    with pytest.raises(ValueError, match="cannot be deleted"):
        tasks.delete_task_list("@default", session=Mock())
