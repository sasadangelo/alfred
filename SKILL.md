---
name: alfred
description: Use when the user asks Alfred to generate or send the current weather report through WhatsApp.
---

# Alfred

Generate and send Alfred's current weather report through WhatsApp.

## Steps

1. Run the bundled command from any directory:

   ```bash
   ~/.claude/skills/alfred/run.sh
   ```

2. Report whether WhatsApp authentication and delivery succeeded.
3. If the command fails, report the error without retrying automatically to avoid duplicate messages.

## Current capability

Alfred sends current weather information only. Do not claim that traffic or news are included.

## Safety

- Read the recipient only from the private Alfred configuration; never hard-code or reveal it.
- Never send more than one message per invocation.
- Never delete the WhatsApp session database.
- Do not expose session files, credentials, API keys, or personal phone numbers in output.
- Do not modify application code as part of a normal report invocation.
