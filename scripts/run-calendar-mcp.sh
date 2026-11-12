#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ALFRED_ENV_FILE:-$HOME/.claude/config/alfred.env}"
CONFIG_FILE="${ALFRED_CONFIG_FILE:-$HOME/.claude/config/config.yaml}"
if [ ! -f "$CONFIG_FILE" ] && [ -f "$PROJECT_ROOT/config.yaml" ]; then
  CONFIG_FILE="$PROJECT_ROOT/config.yaml"
fi

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export ALFRED_CONFIG_FILE="$CONFIG_FILE"
cd "$PROJECT_ROOT"
exec uv run python -m alfred.calendar_mcp