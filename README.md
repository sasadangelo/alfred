# Alfred 🎩 — Your personal assistant, inside Claude Code

<p align="center">
  <img src="docs/icon.png" alt="Alfred, a butler in a tuxedo" width="260">
</p>

Alfred is a personal-assistant plugin for [Claude Code](https://code.claude.com). It connects Claude to your Google Calendar, Google Tasks and Gmail, gives weather forecasts and travel times with live traffic, and keeps a local profile of you (family, places, habits) so every answer fits your life. All personal data stays on your machine.

<p align="center">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-0.1.0-22325a?style=flat-square" alt="Version 0.1.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-d4af37?style=flat-square" alt="MIT license"></a>
  <a href="https://code.claude.com/docs/en/plugins"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D97757?style=flat-square" alt="Claude Code plugin"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%E2%80%933.14-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10–3.14"></a>
  <a href="https://developers.google.com/workspace"><img src="https://img.shields.io/badge/Google-Calendar%20%C2%B7%20Tasks%20%C2%B7%20Gmail-4285F4?style=flat-square&logo=google&logoColor=white" alt="Google Calendar, Tasks and Gmail"></a>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#connect-google-calendar-and-google-tasks">Connect Google</a> ·
  <a href="#what-it-does">Features</a> ·
  <a href="#your-data">Your data</a> ·
  <a href="#development">Development</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

## What it does

| Skill | Ask things like |
|---|---|
| `google-calendar` | "What do I have this week?", "Add the dentist on Friday at 10", "Remove the recurring garden cleaning" |
| `google-tasks` | "What do I have to do this weekend?", "Add 'paint the garage' to the Home list", "Mark the cameras as done" |
| `gmail` | "What unread email do I have today?", "Find the invoice from Enel", "Label the OVH emails OVHCloud", "Trash the promotions older than 3 months" |
| `weather` | "What's the weather tomorrow?", "How should I dress for Sunday's run?", "Do I need an umbrella for the office?" |
| `traffic` | "How is the traffic to the office?", "When should I leave to be at the dentist at 10?" |
| `user-profile` | "Remember my wife's birthday is July 4", "What do you know about me?", "Forget my old car" |
| `morning-report` | Being rewritten: not working in this version |

Behind the skills, the plugin starts three MCP servers:

- **google-workspace**: Google Calendar (events, recurring series, reminders, availability, calendars), Google Tasks (lists, tasks, subtasks, due dates) and Gmail (search, read, create and apply labels, archive, mark read or unread, trash and restore).
- **user-profile**: your local profile, with people identified by name, surname and birth date.
- **weather**: forecasts and place search from [Open-Meteo](https://open-meteo.com) (free, no API key).
- **traffic**: car routes with live and predicted traffic, and address search, from [TomTom](https://developer.tomtom.com) (free key required).

## Requirements

- Claude Code
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs the Python runtime and dependencies on first use
- A Google account, for Calendar, Tasks and Gmail

## Install

In Claude Code:

```text
/plugin marketplace add sasadangelo/alfred
/plugin install alfred@sasadangelo
```

When the plugin is enabled, Claude Code asks for two options, which you can change later in `/config`:

- **Timezone**: defaults to `Europe/Rome`.
- **Google OAuth client file**: see below.
- **TomTom API key**: for traffic and travel times. Create a free key at [developer.tomtom.com](https://developer.tomtom.com) and enable the Search, Routing and Traffic APIs for it. It is stored in your system keychain.

## Connect Google Calendar and Google Tasks

1. In [Google Cloud Console](https://console.cloud.google.com), create a project and enable the **Google Calendar API**, the **Google Tasks API** and the **Gmail API**.
2. Configure the OAuth consent screen with user type **External** and set its publishing status to **In production**. In *Testing* status Google makes the authorization [expire after 7 days](https://developers.google.com/identity/protocols/oauth2#expiration). Because the app is not verified by Google, the consent page shows an "unverified app" warning: for your own use, continue past it.
3. Create an OAuth client ID of type **Desktop app** and download its JSON.
4. Set the plugin option **Google OAuth client file** to that JSON (`/config`), or save it as `google-oauth-client.json` in the plugin data directory (`~/.claude/plugins/data/alfred-sasadangelo/`).
5. Ask Claude to "connect Google" (or run `/alfred:connect-google`). It gives you a command to run in your terminal; the command opens Google's consent page and waits up to 5 minutes.
6. Reconnect the `google-workspace` server with `/mcp`.

Access tokens are refreshed automatically. Authorize again only if you revoke access, change OAuth client, or a plugin update adds a new Google permission.

The token is saved next to the client file with owner-only permissions. Alfred requests these scopes:

- `calendar.events`: read and manage events
- `calendar.calendarlist.readonly`: list your calendars
- `tasks`: read and manage tasks
- `gmail.modify`: read and organize email (labels, archive, trash). Alfred cannot send email or delete it permanently.

## Your data

Alfred stores everything in the plugin data directory, `~/.claude/plugins/data/alfred-sasadangelo/`, which survives plugin updates:

| File | Contents |
|---|---|
| `profile.yaml` | Your profile: family, places, vehicles, preferences |
| `google-oauth-client.json`, `google-token.json` | Google credentials |
| `venv/` | The Python environment |

Files are created with owner-only permissions. Nothing is sent anywhere except the requests each feature needs: Google APIs for Calendar, Tasks and Gmail, coordinates or the town name (never your address or name) to Open-Meteo, the coordinates of a trip to TomTom, and an address to look up only when a place has no saved coordinates yet (TomTom, or OpenStreetMap for streets TomTom does not know).

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
