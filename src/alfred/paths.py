"""Where Alfred keeps the user's data, and runtime settings passed in by the plugin.

Inside the Claude Code plugin, data lives in ``CLAUDE_PLUGIN_DATA``, which survives plugin
updates. ``ALFRED_DATA_DIR`` overrides it (useful for tests). When running from the repository,
the default is the same directory the installed plugin uses, so the data is already in place when
the plugin is installed.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DATA_DIR_ENV = "ALFRED_DATA_DIR"
PLUGIN_DATA_ENV = "CLAUDE_PLUGIN_DATA"
TIMEZONE_ENV = "ALFRED_TIMEZONE"
# Claude Code's data directory for the plugin "alfred" from the "sasadangelo" marketplace.
DEFAULT_DATA_DIR = Path.home() / ".claude" / "plugins" / "data" / "alfred-sasadangelo"
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


ENV_FILENAME = "alfred.env"


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines, ignoring comments, blank lines and surrounding quotes."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def secret(name: str) -> str:
    """Return a secret setting: the environment (plugin options) first, else ``alfred.env`` in the
    data directory. Returns an empty string when it is not configured."""
    return env_value(name) or _read_env_file(data_dir() / ENV_FILENAME).get(name, "")
