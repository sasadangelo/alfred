# Changelog

All notable changes to this plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Utilities and subscriptions (luce, gas, internet, domini, abbonamenti) in `subscriptions.yaml`, with codes, billing frequency, renewals, the Gmail query for their emails and where their bills go; `list_subscriptions`, `save_subscription` and `forget_subscription` tools in the `user-profile` server and the `subscriptions` skill.
- Gmail: save email attachments (PDF by default) into a folder in the home directory, with clear names, duplicate detection by content and no overwriting.
- `fuel` MCP server and skill: prices of individual Italian stations from the Ministry's observatory (MIMIT), cheapest near a place for the fuel of the user's vehicles, with the time each price was communicated, with the stations within 5 km of home and work saved in `fuel-stations.yaml` closest first, the usual station marked, and live prices by distance or by price.
- Gmail tools in the `google-workspace` server and the `gmail` skill: search, read, create and apply labels, archive, mark read/unread, trash and restore, with the `gmail.modify` permission (no sending, no permanent deletion). Requires enabling the Gmail API and authorizing again.
- `traffic` MCP server and skill: car routes with live and predicted traffic from TomTom, departure times for appointments and the commute, and a `TomTom API key` plugin option.
- Secrets such as the TomTom key can also be read from `alfred.env` in the data directory.
- Vehicles can store yearly deadlines (e.g. bollo, assicurazione) as MM-DD; upcoming ones appear in the profile summary.
- Saved places can store verified coordinates, which traffic and weather use instead of looking up the address.
- Address lookup uses TomTom search, with OpenStreetMap as a fallback for streets TomTom does not know.

### Changed

- Profile entries no longer record their last update date; profiles saved with it still load.

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
