#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
POSTGRES_DB="$(docker compose exec -T db sh -c 'printf "%s" "$POSTGRES_DB"')"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/${POSTGRES_DB}-${TIMESTAMP}.sql.gz"
TMP_FILE="${BACKUP_FILE}.tmp"

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$TMP_FILE"' EXIT

echo "Creating PostgreSQL backup: $BACKUP_FILE"
docker compose exec -T db sh -c \
  'exec pg_dump --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$TMP_FILE"

mv "$TMP_FILE" "$BACKUP_FILE"
trap - EXIT

echo "Backup complete: $BACKUP_FILE"
