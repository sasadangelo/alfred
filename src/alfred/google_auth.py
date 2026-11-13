"""Shared Google OAuth credentials and API error handling for the Google integrations."""

import os
from pathlib import Path
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_LIST_SCOPE = "https://www.googleapis.com/auth/calendar.calendarlist.readonly"
TASKS_SCOPE = "https://www.googleapis.com/auth/tasks"
GOOGLE_SCOPES = [CALENDAR_EVENTS_SCOPE, CALENDAR_LIST_SCOPE, TASKS_SCOPE]

CONFIG_DIR_ENV = "ALFRED_CONFIG_DIR"
CLIENT_SECRET_FILE_ENV = "ALFRED_GOOGLE_CALENDAR_CLIENT_SECRET_FILE"  # pragma: allowlist secret
TOKEN_FILE_ENV = "ALFRED_GOOGLE_CALENDAR_TOKEN_FILE"
DEFAULT_CONFIG_DIR = Path.home() / ".claude" / "config"
LEGACY_CREDENTIALS_DIR = Path(__file__).resolve().parents[2] / "credentials"
CLIENT_SECRET_FILENAME = "google-oauth-client.json"  # pragma: allowlist secret
# Kept for compatibility with tokens saved before Tasks support; it now covers every Google scope.
TOKEN_FILENAME = "google-calendar-token.json"
AUTHORIZE_HINT = "Run `bash scripts/authorize-google.sh` to authorize Alfred again."
REQUEST_TIMEOUT_SECONDS = 15


class GoogleAPIError(RuntimeError):
    """A Google API failure explained in terms the user can act on."""


def _credential_file(env_name: str, filename: str) -> Path:
    """Resolve a credential file: explicit env var, then the config dir, then the legacy repo folder."""
    if explicit := os.environ.get(env_name):
        return Path(explicit).expanduser()
    preferred = Path(os.environ.get(CONFIG_DIR_ENV, DEFAULT_CONFIG_DIR)).expanduser() / filename
    legacy = LEGACY_CREDENTIALS_DIR / filename
    if not preferred.exists() and legacy.exists():
        return legacy
    return preferred


def client_secret_file() -> Path:
    """Return the path of the Google OAuth client JSON."""
    return _credential_file(CLIENT_SECRET_FILE_ENV, CLIENT_SECRET_FILENAME)


def token_file() -> Path:
    """Return the path of the saved Google OAuth token."""
    return _credential_file(TOKEN_FILE_ENV, TOKEN_FILENAME)


def authorize() -> None:
    """Run Google's consent flow for every scope the integrations use and save the token."""
    secret_file = client_secret_file()
    if not secret_file.is_file():
        raise FileNotFoundError(f"Google OAuth client file not found: {secret_file}")

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), GOOGLE_SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")
    path.chmod(mode=0o600)
    print(f"Saved Google token to {path}")


def get_credentials(required_scope: str) -> Credentials:
    """Load, refresh and validate the saved token, requiring ``required_scope``."""
    path = token_file()
    if not path.is_file():
        raise GoogleAPIError(f"Google is not authorized yet (no token at {path}). {AUTHORIZE_HINT}")

    # Load with the token's own scopes so older tokens keep working for the operations they cover.
    credentials = Credentials.from_authorized_user_file(str(path))
    if not credentials.has_scopes([required_scope]):
        raise GoogleAPIError(f"The saved Google authorization does not include {required_scope}. {AUTHORIZE_HINT}")
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        path.write_text(credentials.to_json(), encoding="utf-8")
        path.chmod(mode=0o600)
    if not credentials.valid:
        raise GoogleAPIError(f"Google credentials are invalid or expired. {AUTHORIZE_HINT}")
    return credentials


def _google_message(response: Any) -> str:
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return str(getattr(response, "text", "")).strip()[:200]


def check_response(response: Any, what: str, resource: str) -> None:
    """Raise a GoogleAPIError with a clear explanation when Google rejects a request.

    ``what`` completes "Could not ..." (e.g. "delete the task"); ``resource`` names what a 404
    refers to (e.g. "task or task list").
    """
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        status = response.status_code
        detail = _google_message(response)
        if status == 401:
            message = f"Google rejected the saved credentials. {AUTHORIZE_HINT}"
        elif status == 403 and ("insufficient" in detail.lower() or "scope" in detail.lower()):
            message = f"The saved Google authorization does not allow this operation. {AUTHORIZE_HINT}"
        elif status == 403 and "has not been used" in detail.lower():
            message = f"The Google API needed to {what} is not enabled for this OAuth client: {detail}"
        elif status == 403:
            message = f"Google refused to {what}: {detail}"
        elif status == 404:
            message = f"Could not {what}: the {resource} was not found (wrong id, or already deleted)."
        elif status == 410:
            message = f"Could not {what}: the {resource} has already been deleted."
        elif status == 429 or status >= 500:
            message = f"Google is temporarily unavailable ({status}); try again shortly."
        else:
            message = f"Google rejected the request to {what} ({status}): {detail}"
        raise GoogleAPIError(message) from error


if __name__ == "__main__":
    authorize()
