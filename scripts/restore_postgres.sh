#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup-file.sql.gz|backup-file.sql>" >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_FILE="$1"
POSTGRES_DB="$(docker compose exec -T db sh -c 'printf "%s" "$POSTGRES_DB"' </dev/null)"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

read -r -p "This will replace objects in database '$POSTGRES_DB'. Continue? [y/N] " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "Restore cancelled."
  exit 0
fi

echo "Stopping application services before restore..."
docker compose stop nginx app >/dev/null

restore_stream() {
  docker compose exec -T db sh -c \
    'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
}

if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" | restore_stream
else
  cat "$BACKUP_FILE" | restore_stream
fi

echo "Database restore completed. Starting application services..."
docker compose up -d app nginx
./scripts/wait_for_stack.sh

echo "Restore complete from: $BACKUP_FILE"
