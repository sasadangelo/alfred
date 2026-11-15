# Changelog

All notable changes to this plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Gmail tools in the `google-workspace` server and the `gmail` skill: search, read, create and apply labels, archive, mark read/unread, trash and restore, with the `gmail.modify` permission (no sending, no permanent deletion). Requires enabling the Gmail API and authorizing again.
- `traffic` MCP server and skill: car routes with live and predicted traffic from TomTom, departure times for appointments and the commute, and a `TomTom API key` plugin option.
- Secrets such as the TomTom key can also be read from `alfred.env` in the data directory.

### Removed

- The old WhatsApp morning report and its code (weather, traffic, almanac, news, WhatsApp, `config.yaml`). The `morning-report` skill is kept as a placeholder until the new morning routine is written.

## [0.1.0] - 2026-11-15

First public release.

### Added

- Claude Code plugin layout: `.claude-plugin/plugin.json`, marketplace, `userConfig` for timezone and the Google OAuth client.
- `google-workspace` MCP server and the `google-calendar` and `google-tasks` skills.
- `user-profile` MCP server and skill: a local profile with stable ids for people and vehicles.
- `weather` MCP server and skill, with running and commute advice.
- `morning-report` skill for the WhatsApp morning report.
- `connect-google` skill to set up and renew the Google authorization.
- Project pages (home, privacy policy, terms of use) in `docs/`.

[0.1.0]: https://github.com/sasadangelo/alfred/releases/tag/v0.1.0
