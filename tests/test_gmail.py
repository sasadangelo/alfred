"""Tests for basic Gmail operations."""

import base64
from typing import Any
from unittest.mock import Mock

import pytest

from alfred import gmail

LABELS = {
    "labels": [
        {"id": "INBOX", "name": "INBOX", "type": "system"},
        {"id": "UNREAD", "name": "UNREAD", "type": "system"},
        {"id": "TRASH", "name": "TRASH", "type": "system"},
        {"id": "Label_7", "name": "Newsletter", "type": "user"},
    ]
}


def _response(payload: dict[str, Any] | None = None, status: int = 200) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload or {}
    return response


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode().rstrip("=")


def _metadata(message_id: str, subject: str, labels: list[str]) -> dict[str, Any]:
    return {
        "id": message_id,
        "threadId": f"t-{message_id}",
        "labelIds": labels,
        "snippet": "Offerta &amp; sconti",
        "payload": {
            "headers": [
                {"name": "From", "value": "Shop <news@shop.example>"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Sat, 14 Nov 2026 09:00:00 +0100"},
            ]
        },
    }


def test_search_messages_returns_summaries_and_truncation() -> None:
    session = Mock()
    session.get.side_effect = [
        _response({"messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]}),
        _response(_metadata("m1", "Saldi", ["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"])),
        _response(_metadata("m2", "", ["INBOX"])),
    ]

    result = gmail.search_messages(" category:promotions ", max_results=2, session=session)

    assert result["truncated"] is True
    first, second = result["messages"]
    assert first == {
        "id": "m1",
        "thread_id": "t-m1",
        "from": "Shop <news@shop.example>",
        "to": "me@example.com",
        "subject": "Saldi",
        "date": "Sat, 14 Nov 2026 09:00:00 +0100",
        "snippet": "Offerta & sconti",
        "labels": ["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        "unread": True,
        "in_inbox": True,
    }
    assert second["subject"] == "(senza oggetto)"
    assert second["unread"] is False
    list_params = session.get.call_args_list[0].kwargs["params"]
    assert list_params["q"] == "category:promotions"
    assert session.get.call_args_list[1].kwargs["params"]["format"] == "metadata"


def test_search_rejects_too_many_results() -> None:
    with pytest.raises(ValueError, match="max_results"):
        gmail.search_messages("", max_results=101, session=Mock())


def test_get_message_prefers_plain_text_and_lists_attachments() -> None:
    session = Mock()
    session.get.return_value = _response(
        {
            "id": "m1",
            "labelIds": ["INBOX"],
            "payload": {
                "mimeType": "multipart/mixed",
                "headers": [{"name": "Subject", "value": "Fattura"}, {"name": "Cc", "value": "a@example.com"}],
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "headers": [{"name": "Content-Type", "value": 'text/plain; charset="UTF-8"'}],
                                "body": {"data": _b64("Ciao, ecco la fattura.")},
                            },
                            {"mimeType": "text/html", "body": {"data": _b64("<p>Ciao</p>")}},
                        ],
                    },
                    {"mimeType": "application/pdf", "filename": "fattura.pdf", "body": {"attachmentId": "a1"}},
                ],
            },
        }
    )

    message = gmail.get_message("m1", session=session)

    assert message["body"] == "Ciao, ecco la fattura."
    assert message["attachments"] == ["fattura.pdf"]
    assert message["cc"] == "a@example.com"
    assert message["body_truncated"] is False


def test_get_message_converts_html_only_bodies() -> None:
    session = Mock()
    session.get.return_value = _response(
        {
            "id": "m1",
            "payload": {
                "mimeType": "text/html",
                "body": {
                    "data": _b64(
                        "<html><head><style>p{}</style></head>"
                        "<body><p>Primo</p><p>Secondo &amp; ultimo</p></body></html>"
                    )
                },
            },
        }
    )

    assert gmail.get_message("m1", session=session)["body"] == "Primo\nSecondo & ultimo"


def test_modify_messages_resolves_label_names() -> None:
    session = Mock()
    session.get.return_value = _response(LABELS)
    session.post.return_value = _response(status=204)

    result = gmail.modify_messages(
        ["m1", "m2", "m1"], add_labels=["newsletter"], remove_labels=["INBOX"], session=session
    )

    assert result == {"updated": 2}
    assert session.post.call_args.args[0].endswith("/messages/batchModify")
    assert session.post.call_args.kwargs["json"] == {
        "ids": ["m1", "m2"],
        "addLabelIds": ["Label_7"],
        "removeLabelIds": ["INBOX"],
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"add_labels": ["Sconosciuta"]}, "unknown label"),
        ({"add_labels": ["TRASH"]}, "dedicated operation"),
        ({}, "add_labels and/or remove_labels"),
    ],
)
def test_modify_messages_rejects_invalid_labels(kwargs: dict[str, Any], message: str) -> None:
    session = Mock()
    session.get.return_value = _response(LABELS)

    with pytest.raises(ValueError, match=message):
        gmail.modify_messages(["m1"], session=session, **kwargs)
    session.post.assert_not_called()


def test_archive_and_mark_read_unread() -> None:
    session = Mock()
    session.get.return_value = _response(LABELS)
    session.post.return_value = _response(status=204)

    gmail.archive_messages(["m1"], session=session)
    assert session.post.call_args.kwargs["json"]["removeLabelIds"] == ["INBOX"]

    gmail.mark_messages_read(["m1"], session=session)
    assert session.post.call_args.kwargs["json"]["removeLabelIds"] == ["UNREAD"]

    gmail.mark_messages_read(["m1"], read=False, session=session)
    assert session.post.call_args.kwargs["json"]["addLabelIds"] == ["UNREAD"]


def test_trash_and_restore_each_message() -> None:
    session = Mock()
    session.post.return_value = _response()

    assert gmail.trash_messages(["m1", "m2"], session=session) == {"updated": 2}
    assert [call.args[0].rsplit("/", 2)[-2:] for call in session.post.call_args_list] == [
        ["m1", "trash"],
        ["m2", "trash"],
    ]

    gmail.untrash_messages(["m1"], session=session)
    assert session.post.call_args.args[0].endswith("/messages/m1/untrash")


@pytest.mark.parametrize("ids", [[], ["  "]])
def test_actions_require_message_ids(ids: list[str]) -> None:
    with pytest.raises(ValueError, match="message_ids must not be empty"):
        gmail.trash_messages(ids, session=Mock())


def test_actions_limit_batch_size() -> None:
    with pytest.raises(ValueError, match="at most 1000"):
        gmail.archive_messages([f"m{i}" for i in range(1001)], session=Mock())


def test_gmail_scope_is_requested() -> None:
    from alfred import google_auth

    assert google_auth.GMAIL_MODIFY_SCOPE in google_auth.GOOGLE_SCOPES


def test_create_label_returns_existing_one() -> None:
    session = Mock()
    session.get.return_value = _response(LABELS)

    assert gmail.create_label("newsletter", session=session) == {"id": "Label_7", "name": "Newsletter", "type": "user"}
    session.post.assert_not_called()


def test_create_label_creates_nested_label() -> None:
    session = Mock()
    session.get.return_value = _response(LABELS)
    session.post.return_value = _response({"id": "Label_9", "name": "Arte/Pittura"})

    label = gmail.create_label(" Arte / Pittura ", session=session)

    assert label == {"id": "Label_9", "name": "Arte/Pittura", "type": "user"}
    assert session.post.call_args.kwargs["json"]["name"] == "Arte/Pittura"


@pytest.mark.parametrize("name", ["", "Arte/", "/Pittura"])
def test_create_label_rejects_empty_parts(name: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        gmail.create_label(name, session=Mock())
