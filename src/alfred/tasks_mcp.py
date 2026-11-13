"""Google Tasks tools, mounted into the google-workspace MCP server."""

from datetime import date
from typing import Any

from fastmcp import FastMCP

from alfred import tasks

INSTRUCTIONS = (
    "Google Tasks: tools use the default task list unless a tasklist_id from list_task_lists is given. "
    "Due dates are dates only (YYYY-MM-DD): the Tasks API ignores times and cannot set reminders "
    "or recurrence."
)

mcp = FastMCP(name="tasks", instructions=INSTRUCTIONS)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@mcp.tool
def list_task_lists() -> list[dict[str, str]]:
    """List the user's Google Tasks lists with the id to pass as tasklist_id."""
    return tasks.list_task_lists()


@mcp.tool
def list_tasks(
    tasklist_id: str = tasks.DEFAULT_LIST,
    all_lists: bool = False,
    include_completed: bool = False,
    due_from: str | None = None,
    due_to: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """List tasks ordered by due date; all_lists searches every list.

    due_from/due_to (YYYY-MM-DD, inclusive) keep only tasks due in that range; query matches title
    or notes. Each task has status "open"/"completed" and overdue=true when open and past due.
    """
    return tasks.list_tasks(
        tasklist_id=None if all_lists else tasklist_id,
        include_completed=include_completed,
        due_from=_date(due_from),
        due_to=_date(due_to),
        query=query,
    )


@mcp.tool
def create_task(
    title: str,
    notes: str = "",
    due: str | None = None,
    tasklist_id: str = tasks.DEFAULT_LIST,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Create a task; due is YYYY-MM-DD; parent_id makes it a subtask."""
    return tasks.create_task(title, notes=notes, due=_date(due), tasklist_id=tasklist_id, parent_id=parent_id)


@mcp.tool
def update_task(
    task_id: str,
    tasklist_id: str = tasks.DEFAULT_LIST,
    title: str | None = None,
    notes: str | None = None,
    due: str | None = None,
    clear_due: bool = False,
) -> dict[str, Any]:
    """Change only the given fields of a task; clear_due removes the due date."""
    return tasks.update_task(
        task_id, tasklist_id=tasklist_id, title=title, notes=notes, due=_date(due), clear_due=clear_due
    )


@mcp.tool
def complete_task(task_id: str, tasklist_id: str = tasks.DEFAULT_LIST) -> dict[str, Any]:
    """Mark a task as completed."""
    return tasks.complete_task(task_id, tasklist_id=tasklist_id)


@mcp.tool
def reopen_task(task_id: str, tasklist_id: str = tasks.DEFAULT_LIST) -> dict[str, Any]:
    """Mark a completed task as open again."""
    return tasks.reopen_task(task_id, tasklist_id=tasklist_id)


@mcp.tool
def move_task(
    task_id: str,
    tasklist_id: str = tasks.DEFAULT_LIST,
    destination_tasklist_id: str | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Move a task to another list (destination_tasklist_id) and/or under a parent task."""
    return tasks.move_task(
        task_id, tasklist_id=tasklist_id, destination_tasklist_id=destination_tasklist_id, parent_id=parent_id
    )


@mcp.tool
def delete_task(task_id: str, tasklist_id: str = tasks.DEFAULT_LIST) -> dict[str, str]:
    """Delete a task permanently, including its subtasks."""
    tasks.delete_task(task_id, tasklist_id=tasklist_id)
    return {"deleted": task_id}


@mcp.tool
def create_task_list(title: str) -> dict[str, str]:
    """Create a new task list."""
    return tasks.create_task_list(title)


@mcp.tool
def clear_completed_tasks(tasklist_id: str = tasks.DEFAULT_LIST) -> dict[str, str]:
    """Hide every completed task of a list, like "Clear completed" in the Google apps."""
    tasks.clear_completed_tasks(tasklist_id)
    return {"cleared": tasklist_id}


@mcp.tool
def rename_task_list(tasklist_id: str, title: str) -> dict[str, str]:
    """Rename a task list; the default list can be renamed but not deleted."""
    return tasks.rename_task_list(tasklist_id, title)


@mcp.tool
def delete_task_list(tasklist_id: str) -> dict[str, str]:
    """Delete a task list and all of its tasks permanently. The default list cannot be deleted."""
    tasks.delete_task_list(tasklist_id)
    return {"deleted": tasklist_id}
