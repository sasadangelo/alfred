#!/usr/bin/env bash
# Start one of the project's MCP servers over stdio: run-mcp.sh google-workspace|user-profile|weather
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ALFRED_ENV_FILE:-$HOME/.claude/config/alfred.env}"
CONFIG_FILE="${ALFRED_CONFIG_FILE:-$HOME/.claude/config/config.yaml}"
if [ ! -f "$CONFIG_FILE" ] && [ -f "$PROJECT_ROOT/config.yaml" ]; then
  CONFIG_FILE="$PROJECT_ROOT/config.yaml"
fi

case "${1:-}" in
  google-workspace) MODULE="alfred.google_workspace_mcp" ;;
  user-profile) MODULE="alfred.profile_mcp" ;;
  weather) MODULE="alfred.weather_mcp" ;;
  *)
    echo "Usage: $0 google-workspace|user-profile|weather" >&2
    exit 2
    ;;
esac

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export ALFRED_CONFIG_FILE="$CONFIG_FILE"
cd "$PROJECT_ROOT"
exec uv run python -m "$MODULE"
