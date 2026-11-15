---
name: morning-report
description: Use when the user asks to generate or send Alfred's morning report (weather, traffic, almanac) through WhatsApp.
---

# Morning Report

Send Alfred's morning report through WhatsApp with the plugin's Python application.

## Steps

1. Run the report:

   ```bash
   CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/run-morning-report.sh"
   ```

2. Report whether WhatsApp authentication and delivery succeeded.
3. If the command fails, report the error without retrying automatically, to avoid duplicate messages.

## Setup

The script reads two files from `${CLAUDE_PLUGIN_DATA}` and stops with a clear message if one is missing:

- `alfred.env`: `ALFRED_WHATSAPP_RECIPIENT` and, for traffic, `ALFRED_TOMTOM_API_KEY`. Template: `${CLAUDE_PLUGIN_ROOT}/.env.example`.
- `config.yaml`: name, home, work and news feeds. Template: `${CLAUDE_PLUGIN_ROOT}/config.yaml.example`.

The first run shows a WhatsApp pairing code or QR code in the output; the user links the device from WhatsApp. The session is then kept in `${CLAUDE_PLUGIN_DATA}`.

## Current capability

The report contains the daily weather bulletin and one short historical curiosity from Wikipedia. On configured workdays it also includes the home-to-work traffic when `ALFRED_TOMTOM_API_KEY` is set. News is not included.

## Safety

- Never print the WhatsApp recipient, the TomTom API key, or the contents of `alfred.env`.
- Never send more than one message per request.
- Never delete the WhatsApp session database.
- Do not modify application code as part of a normal report request.
