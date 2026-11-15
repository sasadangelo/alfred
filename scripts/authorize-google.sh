#!/usr/bin/env bash
# Authorize Alfred to use Google Calendar and Google Tasks. Opens Google's consent page in the
# browser and saves the token in the data directory with owner-only permissions.
#
# The OAuth client JSON (a "Desktop app" client from Google Cloud Console) is read from
# ALFRED_GOOGLE_OAUTH_CLIENT_FILE, or from google-oauth-client.json in the data directory.
set -euo pipefail

# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

alfred_python alfred.google_auth
