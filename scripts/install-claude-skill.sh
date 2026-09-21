#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_ROOT="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
CONFIG_ROOT="${CLAUDE_CONFIG_DIR:-$HOME/.claude/config}"
TARGET_PATH="$SKILLS_ROOT/alfred"
ENV_PATH="$CONFIG_ROOT/alfred.env"
CONFIG_PATH="$CONFIG_ROOT/config.yaml"

mkdir -p "$SKILLS_ROOT" "$CONFIG_ROOT"

if [ -e "$TARGET_PATH" ] && [ ! -L "$TARGET_PATH" ]; then
  echo "Error: '$TARGET_PATH' exists and is not a symbolic link." >&2
  exit 1
fi

ln -sfn "$REPOSITORY_ROOT" "$TARGET_PATH"
chmod +x "$REPOSITORY_ROOT/run.sh"

echo "Installed alfred -> $REPOSITORY_ROOT"

if [ ! -f "$ENV_PATH" ]; then
  cp "$REPOSITORY_ROOT/.env.example" "$ENV_PATH"
  chmod 600 "$ENV_PATH"
  echo "Created secret configuration template: $ENV_PATH"
  echo "Configure ALFRED_WHATSAPP_RECIPIENT before running Alfred."
else
  echo "Kept existing secret configuration: $ENV_PATH"
fi

if [ ! -f "$CONFIG_PATH" ]; then
  cp "$REPOSITORY_ROOT/config.example.yaml" "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
  echo "Created application configuration: $CONFIG_PATH"
else
  echo "Kept existing application configuration: $CONFIG_PATH"
fi
