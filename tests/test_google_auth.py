"""Tests for shared Google OAuth credentials and error handling."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from alfred import google_auth, paths
from alfred.google_auth import GoogleAPIError, check_response


def test_credential_files_live_in_the_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(google_auth.TOKEN_FILE_ENV, raising=False)
    monkeypatch.delenv(google_auth.CLIENT_SECRET_FILE_ENV, raising=False)
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))

    assert google_auth.token_file() == tmp_path / "google-token.json"
    assert google_auth.client_secret_file() == tmp_path / "google-oauth-client.json"


def test_unsubstituted_plugin_placeholder_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(google_auth.CLIENT_SECRET_FILE_ENV, "${user_config.google_oauth_client}")
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))

    assert google_auth.client_secret_file() == tmp_path / "google-oauth-client.json"


def test_credential_files_honour_explicit_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(google_auth.TOKEN_FILE_ENV, str(tmp_path / "token.json"))

    assert google_auth.token_file() == tmp_path / "token.json"


def test_missing_token_raises_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(google_auth.TOKEN_FILE_ENV, str(tmp_path / "missing.json"))

    with pytest.raises(GoogleAPIError, match="not authorized yet"):
        google_auth.get_credentials(google_auth.TASKS_SCOPE)


def _error_response(status: int, message: str) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = {"error": {"message": message}}
    response.raise_for_status.side_effect = requests.HTTPError(str(status))
    return response


@pytest.mark.parametrize(
    ("status", "google_message", "expected"),
    [
        (404, "Not Found", "the task or task list was not found"),
        (410, "Deleted", "the task or task list has already been deleted"),
        (403, "Request had insufficient authentication scopes.", "authorize-google.sh"),
        (403, "Google Tasks API has not been used in project 123 before or it is disabled.", "not enabled"),
    ],
)
def test_check_response_names_the_resource(status: int, google_message: str, expected: str) -> None:
    with pytest.raises(GoogleAPIError, match=expected):
        check_response(_error_response(status, google_message), "complete the task", "task or task list")


def test_check_response_accepts_success() -> None:
    check_response(Mock(), "list tasks", "task list")


def test_authorization_requests_every_scope() -> None:
    assert google_auth.TASKS_SCOPE in google_auth.GOOGLE_SCOPES
    assert google_auth.CALENDAR_EVENTS_SCOPE in google_auth.GOOGLE_SCOPES
