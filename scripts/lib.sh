#!/usr/bin/env bash
# Shared helpers for the plugin's scripts. Source it; do not run it.
#
# Inside the Claude Code plugin, code lives in CLAUDE_PLUGIN_ROOT (replaced on every update) and
# everything written at runtime lives in CLAUDE_PLUGIN_DATA (kept across updates): the Python
# virtual environment, the user profile and the Google credentials. Outside the plugin, the
# repository is the root and the data directory is the one the installed plugin will use.

ALFRED_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ALFRED_DATA="${ALFRED_DATA_DIR:-${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/alfred-sasadangelo}}"
export ALFRED_DATA_DIR="$ALFRED_DATA"

# Run a Python module of the alfred package with the project's locked dependencies.
alfred_python() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "Alfred needs uv (https://docs.astral.sh/uv/) to run its Python tools." >&2
    exit 1
  fi
  mkdir -p "$ALFRED_DATA"
  chmod 700 "$ALFRED_DATA"
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    # Keep the virtual environment out of the plugin directory, which is replaced on updates.
    export UV_PROJECT_ENVIRONMENT="$CLAUDE_PLUGIN_DATA/venv"
  fi
  exec uv run --quiet --frozen --no-dev --project "$ALFRED_ROOT" python -m "$@"
}
