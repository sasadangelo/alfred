"""Google Tasks operations.

Google Tasks stores only the date of a due date: the API ignores any time of day, and it cannot
create reminders or recurring tasks. Due dates are therefore plain ``date`` values here.
"""

from datetime import date
from typing import Any
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession

from alfred.google_auth import REQUEST_TIMEOUT_SECONDS, TASKS_SCOPE, check_response, get_credentials

TASKS_API_URL = "https://tasks.googleapis.com/tasks/v1"
DEFAULT_LIST = "@default"
PAGE_SIZE = 100
MAX_TASKS = 1000


def _session(session: Any | None) -> Any:
    return session or AuthorizedSession(get_credentials(TASKS_SCOPE))


def _check(response: Any, what: str) -> None:
    check_response(response, what, "task or task list")


def _list_url(tasklist_id: str) -> str:
    if not tasklist_id.strip():
        raise ValueError("tasklist_id must not be empty")
    return f"{TASKS_API_URL}/lists/{quote(tasklist_id.strip(), safe='@')}/tasks"


def _task_url(tasklist_id: str, task_id: str) -> str:
    if not task_id.strip():
        raise ValueError("task_id must not be empty")
    return f"{_list_url(tasklist_id)}/{quote(task_id.strip(), safe='')}"


def _due_value(due: date) -> str:
    # Google keeps only the date part; midnight UTC is the documented convention.
    return f"{due.isoformat()}T00:00:00.000Z"


def _due_date(task: dict[str, Any]) -> date | None:
    due = task.get("due")
    return date.fromisoformat(str(due)[:10]) if due else None


def _format_task(task: dict[str, Any], tasklist_id: str, today: date) -> dict[str, Any]:
    due = _due_date(task)
    open_task = task.get("status", "needsAction") == "needsAction"
    return {
        "id": str(task.get("id", "")),
        "tasklist_id": tasklist_id,
        "title": str(task.get("title", "")) or "(senza titolo)",
        "notes": str(task.get("notes", "")),
        "due": due.isoformat() if due else "",
        "status": "open" if open_task else "completed",
        "completed_at": str(task.get("completed", "")),
        "overdue": bool(open_task and due and due < today),
        "parent_id": str(task.get("parent", "")),
        "web_link": str(task.get("webViewLink", "")),
    }


def list_task_lists(*, session: Any | None = None) -> list[dict[str, str]]:
    """Return the user's task lists with the id to pass as ``tasklist_id``."""
    authorized_session = _session(session)
    lists: list[dict[str, str]] = []
    params: dict[str, str | int] = {"maxResults": PAGE_SIZE}
    while True:
        response = authorized_session.get(
            f"{TASKS_API_URL}/users/@me/lists", params=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
        _check(response, "list task lists")
        page = response.json()
        lists.extend({"id": str(item["id"]), "title": str(item.get("title", ""))} for item in page.get("items", []))
        if not (next_page := page.get("nextPageToken")):
            return lists
        params["pageToken"] = next_page


def create_task_list(title: str, *, session: Any | None = None) -> dict[str, str]:
    """Create a task list and return its id and title."""
    if not title.strip():
        raise ValueError("title must not be empty")
    response = _session(session).post(
        f"{TASKS_API_URL}/users/@me/lists", json={"title": title.strip()}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    _check(response, "create the task list")
    created = response.json()
    return {"id": str(created["id"]), "title": str(created.get("title", ""))}


def _tasklist_url(tasklist_id: str) -> str:
    if not tasklist_id.strip():
        raise ValueError("tasklist_id must not be empty")
    return f"{TASKS_API_URL}/users/@me/lists/{quote(tasklist_id.strip(), safe='@')}"


def rename_task_list(tasklist_id: str, title: str, *, session: Any | None = None) -> dict[str, str]:
    """Rename a task list (the default list can be renamed but not deleted)."""
    if not title.strip():
        raise ValueError("title must not be empty")
    response = _session(session).patch(
        _tasklist_url(tasklist_id), json={"title": title.strip()}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    _check(response, "rename the task list")
    renamed = response.json()
    return {"id": str(renamed["id"]), "title": str(renamed.get("title", ""))}


def delete_task_list(tasklist_id: str, *, session: Any | None = None) -> None:
    """Delete a task list and all its tasks. Google refuses to delete the default list."""
    if tasklist_id.strip() == DEFAULT_LIST:
        raise ValueError("the default task list cannot be deleted; rename it instead")
    response = _session(session).delete(_tasklist_url(tasklist_id), timeout=REQUEST_TIMEOUT_SECONDS)
    _check(response, "delete the task list")


def _fetch_tasks(session: Any, tasklist_id: str, include_completed: bool) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {
        "maxResults": PAGE_SIZE,
        "showCompleted": "true" if include_completed else "false",
        # Tasks completed from the mobile apps are "hidden"; include them when asked for completed ones.
        "showHidden": "true" if include_completed else "false",
    }
    items: list[dict[str, Any]] = []
    while len(items) < MAX_TASKS:
        response = session.get(_list_url(tasklist_id), params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        _check(response, "list tasks")
        page = response.json()
        items.extend(page.get("items", []))
        if not (next_page := page.get("nextPageToken")):
            break
        params["pageToken"] = next_page
    return items


def list_tasks(
    *,
    tasklist_id: str | None = DEFAULT_LIST,
    include_completed: bool = False,
    due_from: date | None = None,
    due_to: date | None = None,
    query: str | None = None,
    today: date | None = None,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """List tasks, optionally across every list (``tasklist_id=None``).

    ``due_from``/``due_to`` keep tasks due within that inclusive range (tasks without a due date are
    dropped when either bound is set); ``query`` matches title or notes case-insensitively. Results
    are ordered by due date (undated last), then title.
    """
    today = today or date.today()
    authorized_session = _session(session)
    if tasklist_id is None:
        lists = [(item["id"], item["title"]) for item in list_task_lists(session=authorized_session)]
    else:
        lists = [(tasklist_id, "")]

    needle = (query or "").strip().casefold()
    results: list[dict[str, Any]] = []
    for list_id, list_title in lists:
        for raw in _fetch_tasks(authorized_session, list_id, include_completed):
            if raw.get("deleted"):
                continue
            task = _format_task(raw, list_id, today)
            if list_title:
                task["tasklist_title"] = list_title
            due = date.fromisoformat(task["due"]) if task["due"] else None
            if (due_from or due_to) and due is None:
                continue
            if due_from and due and due < due_from:
                continue
            if due_to and due and due > due_to:
                continue
            if needle and needle not in f"{task['title']}\n{task['notes']}".casefold():
                continue
            results.append(task)
    return sorted(results, key=lambda task: (task["due"] == "", task["due"], task["title"].casefold()))


def create_task(
    title: str,
    *,
    notes: str = "",
    due: date | None = None,
    tasklist_id: str = DEFAULT_LIST,
    parent_id: str | None = None,
    today: date | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Create a task (optionally as a subtask of ``parent_id``) and return it."""
    if not title.strip():
        raise ValueError("title must not be empty")
    body: dict[str, Any] = {"title": title.strip(), "notes": notes}
    if due is not None:
        body["due"] = _due_value(due)
    params = {"parent": parent_id} if parent_id else {}
    response = _session(session).post(_list_url(tasklist_id), json=body, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    _check(response, "create the task")
    return _format_task(response.json(), tasklist_id, today or date.today())


def _patch_task(
    tasklist_id: str, task_id: str, changes: dict[str, Any], what: str, today: date | None, session: Any | None
) -> dict[str, Any]:
    response = _session(session).patch(_task_url(tasklist_id, task_id), json=changes, timeout=REQUEST_TIMEOUT_SECONDS)
    _check(response, what)
    return _format_task(response.json(), tasklist_id, today or date.today())


def update_task(
    task_id: str,
    *,
    tasklist_id: str = DEFAULT_LIST,
    title: str | None = None,
    notes: str | None = None,
    due: date | None = None,
    clear_due: bool = False,
    today: date | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Change only the given fields of a task; ``clear_due`` removes its due date."""
    if due is not None and clear_due:
        raise ValueError("pass either due or clear_due, not both")
    if title is not None and not title.strip():
        raise ValueError("title must not be empty")
    changes: dict[str, Any] = {}
    if title is not None:
        changes["title"] = title.strip()
    if notes is not None:
        changes["notes"] = notes
    if due is not None:
        changes["due"] = _due_value(due)
    if clear_due:
        changes["due"] = None
    if not changes:
        raise ValueError("no fields to update")
    return _patch_task(tasklist_id, task_id, changes, "update the task", today, session)


def complete_task(
    task_id: str, *, tasklist_id: str = DEFAULT_LIST, today: date | None = None, session: Any | None = None
) -> dict[str, Any]:
    """Mark a task as completed."""
    return _patch_task(tasklist_id, task_id, {"status": "completed"}, "complete the task", today, session)


def reopen_task(
    task_id: str, *, tasklist_id: str = DEFAULT_LIST, today: date | None = None, session: Any | None = None
) -> dict[str, Any]:
    """Mark a completed task as open again."""
    changes = {"status": "needsAction", "completed": None}
    return _patch_task(tasklist_id, task_id, changes, "reopen the task", today, session)


def move_task(
    task_id: str,
    *,
    tasklist_id: str = DEFAULT_LIST,
    destination_tasklist_id: str | None = None,
    parent_id: str | None = None,
    today: date | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Move a task to another list and/or under a parent task (``parent_id``)."""
    if not destination_tasklist_id and not parent_id:
        raise ValueError("pass destination_tasklist_id and/or parent_id")
    params: dict[str, str] = {}
    if destination_tasklist_id:
        params["destinationTasklist"] = destination_tasklist_id
    if parent_id:
        params["parent"] = parent_id
    response = _session(session).post(
        f"{_task_url(tasklist_id, task_id)}/move", params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    _check(response, "move the task")
    return _format_task(response.json(), destination_tasklist_id or tasklist_id, today or date.today())


def delete_task(task_id: str, *, tasklist_id: str = DEFAULT_LIST, session: Any | None = None) -> None:
    """Delete a task permanently (its subtasks are deleted too)."""
    response = _session(session).delete(_task_url(tasklist_id, task_id), timeout=REQUEST_TIMEOUT_SECONDS)
    _check(response, "delete the task")


def clear_completed_tasks(tasklist_id: str = DEFAULT_LIST, *, session: Any | None = None) -> None:
    """Hide every completed task of a list, as "Clear completed" does in the Google apps."""
    if not tasklist_id.strip():
        raise ValueError("tasklist_id must not be empty")
    response = _session(session).post(
        f"{TASKS_API_URL}/lists/{quote(tasklist_id.strip(), safe='@')}/clear", timeout=REQUEST_TIMEOUT_SECONDS
    )
    _check(response, "clear completed tasks")
