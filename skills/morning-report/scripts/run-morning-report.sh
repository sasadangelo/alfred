#!/usr/bin/env bash
# Send Alfred's morning report through WhatsApp.
#
# Reads alfred.env (WhatsApp recipient, TomTom key) and config.yaml from the data directory, and
# keeps the WhatsApp session database there too.
set -euo pipefail

# shellcheck source=../../../scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../../../scripts/lib.sh"

ENV_FILE="${ALFRED_ENV_FILE:-$ALFRED_DATA/alfred.env}"
CONFIG_FILE="${ALFRED_CONFIG_FILE:-$ALFRED_DATA/config.yaml}"

for required in "$ENV_FILE" "$CONFIG_FILE"; do
  if [ ! -f "$required" ]; then
    echo "Missing $required. Copy the example from the plugin (.env.example, config.yaml.example) and fill it in." >&2
    exit 1
  fi
done

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${ALFRED_WHATSAPP_RECIPIENT:?Missing ALFRED_WHATSAPP_RECIPIENT in $ENV_FILE}"
export ALFRED_CONFIG_FILE="$CONFIG_FILE"

# The WhatsApp library stores its session in the working directory.
cd "$ALFRED_DATA"
alfred_python alfred.alfred
