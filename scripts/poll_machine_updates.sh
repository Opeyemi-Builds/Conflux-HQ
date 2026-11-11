#!/usr/bin/env bash
# ConfluxHQ Lightweight Shell Poller
# Usage: CONFLUX_API_KEY="cfx_api_..." ./poll_machine_updates.sh

set -euo pipefail

API_BASE="${CONFLUX_API_BASE:-http://127.0.0.1:8000/api/v1}"
API_KEY="${CONFLUX_API_KEY:-}"

if [[ -z "$API_KEY" ]]; then
  echo "Error: Set CONFLUX_API_KEY environment variable." >&2
  exit 1
fi

CURSOR=""
echo "Starting 5s poll against $API_BASE..."

while true; do
  URL="$API_BASE/machine/updates?collections=complaints,incidents&limit=20"
  if [[ -n "$CURSOR" ]]; then
    URL="$URL&since=$CURSOR"
  fi

  RESPONSE=$(curl -sS "$URL" -H "Authorization: Bearer $API_KEY" -H "Accept: application/json")
  COUNT=$(echo "$RESPONSE" | grep -o '"count":[0-9]*' | cut -d: -f2 || echo "0")
  NEW_CURSOR=$(echo "$RESPONSE" | grep -o '"cursor":"[^"]*"' | cut -d'"' -f4 || echo "")

  echo "[$(date +'%T')] Fetched $COUNT updates (cursor: ${NEW_CURSOR:-initial})"
  if [[ -n "$NEW_CURSOR" ]]; then
    CURSOR="$NEW_CURSOR"
  fi

  sleep 5
done
