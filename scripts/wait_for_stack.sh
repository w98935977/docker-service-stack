#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://localhost:8080/health}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SLEEP_SECONDS:-2}"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if curl -fsS "$URL" >/dev/null; then
    echo "Stack is healthy: $URL"
    exit 0
  fi
  echo "Waiting for stack healthcheck... ($attempt/$MAX_ATTEMPTS)"
  sleep "$SLEEP_SECONDS"
done

echo "Stack did not become healthy: $URL" >&2
exit 1
