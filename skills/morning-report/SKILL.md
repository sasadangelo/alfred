---
name: morning-report
description: Use when the user asks to generate or send Alfred's morning weather report through WhatsApp.
---

# Morning Report

Generate and send Alfred's morning weather report from the repository's Python application.

## Steps

1. Confirm the repository root contains `pyproject.toml` and `src/alfred/`.
2. Confirm `ALFRED_WHATSAPP_RECIPIENT` is set in the execution environment. Never print its value.
3. Run the report command from the repository root:

   ```bash
   uv run python -m alfred.alfred
   ```

4. Report whether WhatsApp authentication and delivery succeeded.
5. If the command fails, report the error without retrying automatically to avoid duplicate messages.

## Current capability

The Python application sends the daily weather bulletin and one short historical curiosity from Wikipedia. On configured
workdays, it also includes the current home-to-work traffic situation when `ALFRED_TOMTOM_API_KEY` is configured.
News is not included.

## Safety

- Read the recipient and TomTom API key only from environment variables; never hard-code or reveal them.
- Never send more than one message per invocation.
- Never delete the WhatsApp session database.
- Do not expose session files, credentials, API keys, or personal phone numbers in output.
- Do not modify application code as part of a normal report invocation.
