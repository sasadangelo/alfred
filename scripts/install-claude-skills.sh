#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ROOT="$REPOSITORY_ROOT/skills"
TARGET_ROOT="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

mkdir -p "$TARGET_ROOT"

for source_dir in "$SOURCE_ROOT"/*; do
  [ -d "$source_dir" ] || continue

  skill_name="$(basename "$source_dir")"
  target_path="$TARGET_ROOT/$skill_name"

  if [ -e "$target_path" ] && [ ! -L "$target_path" ]; then
    echo "Error: '$target_path' exists and is not a symbolic link." >&2
    exit 1
  fi

  ln -sfn "$source_dir" "$target_path"
  echo "Installed $skill_name -> $source_dir"
done
