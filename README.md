# Alfred

Alfred is a personal-assistant plugin for [Claude Code](https://code.claude.com). It connects Claude to your Google Calendar and Google Tasks, gives weather and running forecasts, and keeps a local profile of you (family, places, habits) so every answer fits your life.

All personal data stays on your machine.

## What it does

| Skill | Ask things like |
|---|---|
| `google-calendar` | "What do I have this week?", "Add the dentist on Friday at 10", "Remove the recurring garden cleaning" |
| `google-tasks` | "What do I have to do this weekend?", "Add 'paint the garage' to the Home list", "Mark the cameras as done" |
| `weather` | "What's the weather tomorrow?", "How should I dress for Sunday's run?", "Do I need an umbrella for the office?" |
| `user-profile` | "Remember my wife's birthday is July 4", "What do you know about me?", "Forget my old car" |
| `morning-report` | "Send me the morning report" (weather, traffic and an almanac entry through WhatsApp) |

Behind the skills, the plugin starts three MCP servers:

- **google-workspace**: Google Calendar (events, recurring series, reminders, availability, calendars) and Google Tasks (lists, tasks, subtasks, due dates).
- **user-profile**: your local profile, with people identified by name, surname and birth date.
- **weather**: forecasts and place search from [Open-Meteo](https://open-meteo.com) (free, no API key).

## Requirements

- Claude Code
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs the Python runtime and dependencies on first use
- A Google account, for Calendar and Tasks

## Install

In Claude Code:

```text
/plugin marketplace add sasadangelo/alfred
/plugin install alfred@sasadangelo
```

When the plugin is enabled, Claude Code asks for two options, which you can change later in `/config`:

- **Timezone**: defaults to `Europe/Rome`.
- **Google OAuth client file**: see below.

## Connect Google Calendar and Google Tasks

1. In [Google Cloud Console](https://console.cloud.google.com), create a project and enable the **Google Calendar API** and the **Google Tasks API**.
2. Configure the OAuth consent screen (type *External*, add yourself as a test user) and create an OAuth client of type **Desktop app**. Download its JSON.
3. Set the plugin option **Google OAuth client file** to that JSON, or save it as `google-oauth-client.json` in the plugin data directory (`~/.claude/plugins/data/alfred-sasadangelo/`).
4. Ask Claude to "connect Google Calendar": it runs the authorization, which opens Google's consent page in your browser.

The token is saved next to the client file with owner-only permissions. Alfred requests these scopes:

- `calendar.events`: read and manage events
- `calendar.calendarlist.readonly`: list your calendars
- `tasks`: read and manage tasks

## Morning report (optional)

The WhatsApp morning report reads two files from the plugin data directory. Copy the templates and fill them in:

- `.env.example` → `alfred.env`: WhatsApp recipient and, for traffic, a TomTom API key.
- `config.yaml.example` → `config.yaml`: your name, home, work days and news feeds.

## Your data

Alfred stores everything in the plugin data directory, `~/.claude/plugins/data/alfred-sasadangelo/`, which survives plugin updates:

| File | Contents |
|---|---|
| `profile.yaml` | Your profile: family, places, vehicles, preferences |
| `google-oauth-client.json`, `google-token.json` | Google credentials |
| `venv/` | The Python environment |

Files are created with owner-only permissions. Nothing is sent anywhere except the requests each feature needs: Google APIs for Calendar and Tasks, and the town name (never your address or name) to Open-Meteo.

Uninstalling the plugin deletes this directory. To keep your profile, uninstall with `--keep-data`.

## Development

```bash
uv sync --group dev
uv run pytest
pre-commit run --all-files
```

Load the plugin from your working copy, so edits apply on the next session:

```bash
claude --plugin-dir .
claude plugin validate --strict .
```

Code lives in `src/alfred/` (one module per integration, plus `*_mcp.py` servers), skills in `skills/`, and the plugin manifest in `.claude-plugin/`.

## License

[MIT](LICENSE)
