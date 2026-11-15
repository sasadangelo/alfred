#!/usr/bin/env bash
# Start one of the plugin's MCP servers over stdio.
# Usage: run-mcp.sh google-workspace|user-profile|weather
set -euo pipefail

# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

case "${1:-}" in
  google-workspace) alfred_python alfred.google_workspace_mcp ;;
  user-profile) alfred_python alfred.profile_mcp ;;
  weather) alfred_python alfred.weather_mcp ;;
  *)
    echo "Usage: $0 google-workspace|user-profile|weather" >&2
    exit 2
    ;;
esac
