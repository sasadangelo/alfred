"""Basic Gmail operations: search, read, label, archive, mark read or unread, trash and restore.

Uses the ``gmail.modify`` scope: Alfred can read and organize mail but cannot send it or delete it
permanently. Trashed messages stay recoverable in Gmail's trash for 30 days.
"""

import base64
import hashlib
import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession

from alfred.google_auth import GMAIL_MODIFY_SCOPE, REQUEST_TIMEOUT_SECONDS, check_response, get_credentials

GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_SEARCH_RESULTS = 100
MAX_MESSAGES_PER_ACTION = 1000
MAX_BODY_CHARS = 20000
SUMMARY_HEADERS = ("From", "To", "Subject", "Date")
# Labels that have dedicated operations, so they cannot be added or removed as plain labels.
RESERVED_LABELS = {"TRASH", "SPAM", "DRAFT", "SENT", "CHAT"}


def _session(session: Any | None) -> Any:
    return session or AuthorizedSession(get_credentials(GMAIL_MODIFY_SCOPE))


def _check(response: Any, what: str) -> None:
    check_response(response, what, "message or label")


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {str(header["name"]).lower(): str(header["value"]) for header in payload.get("headers", [])}


def _summary(message: dict[str, Any]) -> dict[str, Any]:
    headers = _headers(message.get("payload", {}))
    labels = list(message.get("labelIds", []))
    return {
        "id": str(message.get("id", "")),
        "thread_id": str(message.get("threadId", "")),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "") or "(senza oggetto)",
        "date": headers.get("date", ""),
        "snippet": html.unescape(str(message.get("snippet", ""))),
        "labels": labels,
        "unread": "UNREAD" in labels,
        "in_inbox": "INBOX" in labels,
    }


def list_labels(*, session: Any | None = None) -> list[dict[str, str]]:
    """Return the mailbox labels with their ids; system labels have ids such as INBOX or UNREAD."""
    response = _session(session).get(f"{GMAIL_API_URL}/labels", timeout=REQUEST_TIMEOUT_SECONDS)
    _check(response, "list the labels")
    return [
        {"id": str(label["id"]), "name": str(label.get("name", "")), "type": str(label.get("type", "")).lower()}
        for label in response.json().get("labels", [])
    ]


def create_label(name: str, *, session: Any | None = None) -> dict[str, str]:
    """Create a user label, or return it if it already exists. Use "/" to nest, e.g. "Arte/Pittura"."""
    clean = "/".join(part.strip() for part in name.split("/"))
    if not clean or any(not part for part in clean.split("/")):
        raise ValueError("label name must not be empty or contain empty parts")
    authorized_session = _session(session)
    for label in list_labels(session=authorized_session):
        if label["name"].casefold() == clean.casefold():
            return label
    response = authorized_session.post(
        f"{GMAIL_API_URL}/labels",
        json={"name": clean, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _check(response, "create the label")
    created = response.json()
    return {"id": str(created["id"]), "name": str(created.get("name", clean)), "type": "user"}


def search_messages(
    query: str = "",
    *,
    max_results: int = 25,
    include_spam_trash: bool = False,
    session: Any | None = None,
) -> dict[str, Any]:
    """Search with Gmail's query syntax (e.g. ``is:unread category:promotions newer_than:7d``).

    Returns ``{"messages": [...], "truncated": bool}``, newest first, with sender, subject, date,
    snippet and labels for each message.
    """
    if not 1 <= max_results <= MAX_SEARCH_RESULTS:
        raise ValueError(f"max_results must be between 1 and {MAX_SEARCH_RESULTS}")
    authorized_session = _session(session)
    params: dict[str, Any] = {"maxResults": min(max_results + 1, 500), "q": query.strip()}
    if include_spam_trash:
        params["includeSpamTrash"] = "true"
    response = authorized_session.get(f"{GMAIL_API_URL}/messages", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    _check(response, "search the mailbox")
    ids = [str(item["id"]) for item in response.json().get("messages", [])]
    truncated = len(ids) > max_results or bool(response.json().get("nextPageToken"))

    messages = []
    for message_id in ids[:max_results]:
        detail = authorized_session.get(
            f"{GMAIL_API_URL}/messages/{quote(message_id, safe='')}",
            params={"format": "metadata", "metadataHeaders": list(SUMMARY_HEADERS)},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _check(detail, "read a message")
        messages.append(_summary(detail.json()))
    return {"messages": messages, "truncated": truncated}


class _TextExtractor(HTMLParser):
    """Collect the visible text of an HTML email."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _html_to_text(markup: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(markup)
    text = "".join(extractor.parts)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t\r\f\v]+", " ", text)).strip()


def _decode(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    content_type = _headers(part).get("content-type", "")
    charset = re.search(r'charset="?([\w-]+)', content_type)
    try:
        return raw.decode(charset.group(1) if charset else "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _walk(part: dict[str, Any]) -> list[dict[str, Any]]:
    parts = [part]
    for child in part.get("parts", []) or []:
        parts.extend(_walk(child))
    return parts


def get_message(message_id: str, *, session: Any | None = None) -> dict[str, Any]:
    """Return one message with its plain-text body (HTML converted to text) and attachment names."""
    if not message_id.strip():
        raise ValueError("message_id must not be empty")
    response = _session(session).get(
        f"{GMAIL_API_URL}/messages/{quote(message_id.strip(), safe='')}",
        params={"format": "full"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _check(response, "read the message")
    message = response.json()
    parts = _walk(message.get("payload", {}))
    plain = [_decode(part) for part in parts if part.get("mimeType") == "text/plain" and not part.get("filename")]
    rich = [_decode(part) for part in parts if part.get("mimeType") == "text/html" and not part.get("filename")]
    body = "\n\n".join(text for text in plain if text.strip()) or _html_to_text("\n".join(rich))
    result = _summary(message)
    headers = _headers(message.get("payload", {}))
    result.update(
        {
            "cc": headers.get("cc", ""),
            "reply_to": headers.get("reply-to", ""),
            "body": body[:MAX_BODY_CHARS],
            "body_truncated": len(body) > MAX_BODY_CHARS,
            "attachments": [str(part["filename"]) for part in parts if part.get("filename")],
        }
    )
    return result


def _safe_filename(name: str) -> str:
    """Keep a readable file name without path separators or odd characters."""
    stem, dot, extension = name.strip().rpartition(".")
    if not dot:
        stem, extension = extension, ""
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._") or "allegato"
    extension = re.sub(r"[^\w]+", "", extension).lower()
    return f"{stem[:120]}.{extension}" if extension else stem[:120]


def _target_folder(folder: str) -> Path:
    path = Path(folder).expanduser().resolve()
    home = Path.home().resolve()
    if path != home and home not in path.parents:
        raise ValueError("attachments can only be saved inside the user's home folder")
    return path


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_attachments(
    message_id: str,
    folder: str,
    *,
    name: str | None = None,
    extensions: tuple[str, ...] = ("pdf",),
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Save a message's attachments into ``folder`` (inside the home folder), creating it if needed.

    Only files with the given ``extensions`` are saved. ``name`` replaces the original file name
    (a counter is added when there are several). A file whose content already exists in the
    folder is skipped, and an existing file is never overwritten.
    """
    if not message_id.strip():
        raise ValueError("message_id must not be empty")
    target = _target_folder(folder)
    allowed = {extension.lower().lstrip(".") for extension in extensions}
    authorized_session = _session(session)
    response = authorized_session.get(
        f"{GMAIL_API_URL}/messages/{quote(message_id.strip(), safe='')}",
        params={"format": "full"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    _check(response, "read the message")
    parts = [
        part
        for part in _walk(response.json().get("payload", {}))
        if part.get("filename") and part["filename"].rsplit(".", 1)[-1].lower() in allowed
    ]
    target.mkdir(parents=True, exist_ok=True)
    existing = {_digest(path.read_bytes()) for path in target.iterdir() if path.is_file()}
    results: list[dict[str, Any]] = []
    for number, part in enumerate(parts, 1):
        body = part.get("body", {})
        data = body.get("data")
        if not data and body.get("attachmentId"):
            attachment = authorized_session.get(
                f"{GMAIL_API_URL}/messages/{quote(message_id.strip(), safe='')}/attachments/"
                f"{quote(str(body['attachmentId']), safe='')}",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _check(attachment, "download the attachment")
            data = attachment.json().get("data", "")
        content = base64.urlsafe_b64decode((data or "") + "=" * (-len(data or "") % 4))
        original = str(part["filename"])
        extension = original.rsplit(".", 1)[-1].lower()
        wanted = f"{name}{'-' + str(number) if len(parts) > 1 else ''}.{extension}" if name else original
        filename = _safe_filename(wanted)
        digest = _digest(content)
        if digest in existing:
            results.append({"attachment": original, "status": "duplicate", "path": ""})
            continue
        path = target / filename
        counter = 2
        while path.exists():
            path = target / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
            counter += 1
        path.write_bytes(content)
        existing.add(digest)
        results.append({"attachment": original, "status": "saved", "path": str(path), "bytes": len(content)})
    return results


def _ids(message_ids: list[str]) -> list[str]:
    ids = [message_id.strip() for message_id in message_ids if message_id.strip()]
    if not ids:
        raise ValueError("message_ids must not be empty")
    if len(ids) > MAX_MESSAGES_PER_ACTION:
        raise ValueError(f"at most {MAX_MESSAGES_PER_ACTION} messages per action")
    return list(dict.fromkeys(ids))


def _label_ids(names: list[str], labels: list[dict[str, str]]) -> list[str]:
    by_name = {label["name"].casefold(): label["id"] for label in labels}
    by_id = {label["id"].casefold(): label["id"] for label in labels}
    resolved = []
    for name in names:
        key = name.strip().casefold()
        label_id = by_id.get(key) or by_name.get(key)
        if label_id is None:
            raise ValueError(f"unknown label {name!r}; see list_labels for the available labels")
        if label_id in RESERVED_LABELS:
            raise ValueError(f"{label_id} cannot be changed as a label; use the dedicated operation")
        resolved.append(label_id)
    return resolved


def modify_messages(
    message_ids: list[str],
    *,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
    session: Any | None = None,
) -> dict[str, int]:
    """Add and remove labels (by name or id) on many messages at once."""
    ids = _ids(message_ids)
    if not add_labels and not remove_labels:
        raise ValueError("pass add_labels and/or remove_labels")
    authorized_session = _session(session)
    labels = list_labels(session=authorized_session)
    body = {
        "ids": ids,
        "addLabelIds": _label_ids(add_labels or [], labels),
        "removeLabelIds": _label_ids(remove_labels or [], labels),
    }
    response = authorized_session.post(
        f"{GMAIL_API_URL}/messages/batchModify", json=body, timeout=REQUEST_TIMEOUT_SECONDS
    )
    _check(response, "update the messages")
    return {"updated": len(ids)}


def archive_messages(message_ids: list[str], *, session: Any | None = None) -> dict[str, int]:
    """Remove messages from the inbox; they stay in "All Mail" and in search."""
    return modify_messages(message_ids, remove_labels=["INBOX"], session=session)


def mark_messages_read(message_ids: list[str], *, read: bool = True, session: Any | None = None) -> dict[str, int]:
    """Mark messages as read (or unread with ``read=False``)."""
    if read:
        return modify_messages(message_ids, remove_labels=["UNREAD"], session=session)
    return modify_messages(message_ids, add_labels=["UNREAD"], session=session)


def _per_message(message_ids: list[str], action: str, what: str, session: Any | None) -> dict[str, int]:
    ids = _ids(message_ids)
    authorized_session = _session(session)
    for message_id in ids:
        response = authorized_session.post(
            f"{GMAIL_API_URL}/messages/{quote(message_id, safe='')}/{action}", timeout=REQUEST_TIMEOUT_SECONDS
        )
        _check(response, what)
    return {"updated": len(ids)}


def trash_messages(message_ids: list[str], *, session: Any | None = None) -> dict[str, int]:
    """Move messages to the trash; Gmail deletes them for good after 30 days."""
    return _per_message(message_ids, "trash", "move the message to the trash", session)


def untrash_messages(message_ids: list[str], *, session: Any | None = None) -> dict[str, int]:
    """Restore messages from the trash."""
    return _per_message(message_ids, "untrash", "restore the message", session)
