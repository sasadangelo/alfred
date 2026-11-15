---
name: connect-google
description: Use when the user wants to connect, authorize, or reconnect Alfred to Google Calendar or Google Tasks, change the Google OAuth client, or when a Google tool reports that Alfred is not authorized, lacks a permission, or that a Google API is not enabled.
---

# Connect Google

Alfred uses one Google authorization for Calendar and Tasks. Guide the user through it; never ask them to paste OAuth files or tokens into chat, and never print them.

## 1. OAuth client (once)

Skip this step if the user already has a client file. Otherwise, explain these steps in Google Cloud Console (https://console.cloud.google.com):

1. Create a project, then enable the **Google Calendar API** and the **Google Tasks API**.
2. Configure the OAuth consent screen with user type **External**, then set its publishing status to **In production**. In "Testing" status Google makes the authorization expire every 7 days. An app in production that Google has not verified shows an "unverified app" warning on the consent page: for personal use the user can continue past it (Advanced → go to the app).
3. Create an OAuth client ID of type **Desktop app** and download its JSON.
4. Set the plugin option **Google OAuth client file** to that JSON with `/config`, or save it as `${CLAUDE_PLUGIN_DATA}/google-oauth-client.json`.

## 2. Authorize

The authorization opens Google's consent page in the browser and waits up to 5 minutes for the user, which is longer than a tool call may block. Ask the user to run it in their own terminal, and give them this exact command:

```bash
CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" ALFRED_GOOGLE_OAUTH_CLIENT_FILE="${user_config.google_oauth_client}" bash "${CLAUDE_PLUGIN_ROOT}/skills/connect-google/scripts/authorize-google.sh"
```

When it prints "Saved Google token", the token is in `${CLAUDE_PLUGIN_DATA}/google-token.json` with owner-only permissions.

## 3. Reconnect

Ask the user to reconnect the `google-workspace` server with `/mcp`, then check the connection with a read-only call such as `list_task_lists`.

## When to authorize again

- A tool reports that the token was rejected, revoked, or lacks a permission (for example after a plugin update adds a new Google service): repeat steps 2 and 3.
- The user changes OAuth client: update the plugin option, then repeat steps 2 and 3.
- Expired access tokens are refreshed automatically: no action is needed.
