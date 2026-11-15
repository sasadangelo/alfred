"""Where Alfred keeps the user's data, and runtime settings passed in by the plugin.

Inside the Claude Code plugin, data lives in ``CLAUDE_PLUGIN_DATA``, which survives plugin
updates. ``ALFRED_DATA_DIR`` overrides it (useful for tests and development); outside the plugin
the default is ``~/.claude/config``.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DATA_DIR_ENV = "ALFRED_DATA_DIR"
PLUGIN_DATA_ENV = "CLAUDE_PLUGIN_DATA"
TIMEZONE_ENV = "ALFRED_TIMEZONE"
DEFAULT_DATA_DIR = Path.home() / ".claude" / "config"
DEFAULT_TIMEZONE = "Europe/Rome"


def env_value(name: str) -> str:
    """Return an environment variable, treating unset plugin placeholders (``${...}``) as empty."""
    value = os.environ.get(name, "").strip()
    return "" if value.startswith("${") else value


def data_dir() -> Path:
    """Return the directory holding the profile and Google credentials."""
    for name in (DATA_DIR_ENV, PLUGIN_DATA_ENV):
        if value := env_value(name):
            return Path(value).expanduser()
    return DEFAULT_DATA_DIR


def timezone() -> str:
    """Return the IANA timezone used to read local dates and times (default Europe/Rome)."""
    name = env_value(TIMEZONE_ENV) or DEFAULT_TIMEZONE
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"unknown timezone {name!r}; use an IANA name such as Europe/Rome") from error
    return name
