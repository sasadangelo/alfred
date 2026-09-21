#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ALFRED_ENV_FILE:-$HOME/.claude/config/alfred.env}"
CONFIG_FILE="${ALFRED_CONFIG_FILE:-$HOME/.claude/config/config.yaml}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing Alfred configuration: $ENV_FILE" >&2
  echo "Copy '$PROJECT_DIR/.env.example' to '$ENV_FILE' and configure it." >&2
  exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Missing Alfred application configuration: $CONFIG_FILE" >&2
  echo "Copy '$PROJECT_DIR/config.example.yaml' to '$CONFIG_FILE' and configure it." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${ALFRED_WHATSAPP_RECIPIENT:?Missing ALFRED_WHATSAPP_RECIPIENT in $ENV_FILE}"
export ALFRED_CONFIG_FILE="$CONFIG_FILE"

cd "$PROJECT_DIR"
exec uv run python -m alfred.alfred
