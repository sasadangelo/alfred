---
name: google-tasks
description: Use when the user asks Alfred about to-dos, tasks, things to do, deadlines without a time, shopping or errand lists, or to add, complete, change, move, or delete a Google Tasks item.
---

# Google Tasks

Use the `google-workspace` MCP task tools to manage the user's Google Tasks. Tools use the default list unless you pass a `tasklist_id` from `list_task_lists`; pass `all_lists=true` to `list_tasks` when the user does not name a list.

## What Google Tasks can and cannot do

- Due dates are dates only (`YYYY-MM-DD`). The API ignores times and cannot set reminders or recurrence.
- When the user wants a time of day or a notification ("ricordami alle 18"), propose an event on Google Calendar with a reminder instead, using the `google-calendar` skill, or both a task and an event.
- Recurring tasks created in the Google apps are visible, but new recurring tasks cannot be created here.

## List tasks

1. Interpret relative dates in Alfred's timezone (`Europe/Rome`).
2. Call `list_tasks`. Use `due_from`/`due_to` for periods ("cosa devo fare questa settimana"), `query` to find tasks by text, and `include_completed=true` only when the user asks about completed tasks.
3. Summarize in Italian, grouped as: overdue (`overdue=true`), due today, upcoming, without a due date. Mention the list name when tasks come from several lists. Say clearly when there is nothing to do.

## Create a task

1. Collect the title and, if given, a due date, notes, list, and parent task. Do not invent a due date.
2. Check with `list_tasks` (and `query`) that an open task with the same title does not already exist.
3. For a simple task the user dictated explicitly ("aggiungi comprare il latte"), create it directly. For several tasks at once, or when you inferred details, list them and get confirmation first.
4. When the task relates to the user (car, family, home), read `get_user_profile` from the `user-profile` server to fill in details such as which car, instead of asking again.
5. Confirm what was created using the returned details.

## Complete, update, or move

1. Find the task with `list_tasks` (use `query`). If several tasks match, ask which one.
2. Completing a task the user names explicitly needs no extra confirmation; confirm afterwards.
3. Use `update_task` with only the fields that change (`clear_due=true` removes the due date), `reopen_task` to undo a completion, and `move_task` to change list or parent.

## Delete

1. Prefer completing over deleting when the user says a task is done.
2. State exactly what will be deleted (deleting a task also deletes its subtasks) and get explicit confirmation before `delete_task`.
3. `clear_completed_tasks` hides all completed tasks of a list: confirm the list first.
4. `delete_task_list` deletes a whole list with all its tasks: list how many open tasks it contains and get explicit confirmation. The default list cannot be deleted; offer `rename_task_list` instead.

## Authorization

If a tool reports that Google is not authorized, that the authorization lacks a permission, or that the Tasks API is not enabled, follow the "Initial setup" steps of the `google-calendar` skill: one authorization covers both Calendar and Tasks.
