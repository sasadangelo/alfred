#!/usr/bin/env bash
# Start one of the plugin's MCP servers over stdio.
# Usage: run-mcp.sh google-workspace|user-profile|weather|traffic|fuel
set -euo pipefail

# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

case "${1:-}" in
  google-workspace) alfred_python alfred.google_workspace_mcp ;;
  user-profile) alfred_python alfred.profile_mcp ;;
  weather) alfred_python alfred.weather_mcp ;;
  traffic) alfred_python alfred.traffic_mcp ;;
  fuel) alfred_python alfred.fuel_mcp ;;
  *)
    echo "Usage: $0 google-workspace|user-profile|weather|traffic|fuel" >&2
    exit 2
    ;;
esac
