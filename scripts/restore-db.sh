#!/usr/bin/env bash
# PhotosApp database restore script.
#
# Usage:
#   ./scripts/restore-db.sh <backup_file.sql.gz>
#
# This script:
#   1. Enables the pgvector extension (needed after a fresh postgres volume)
#   2. Drops and recreates the target database
#   3. Restores the dump
#   4. Restarts the backend so it picks up the restored data

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <backup_file.sql.gz>" >&2
    echo ""
    echo "Available backups:"
    ls -lht "$PROJECT_DIR/backups"/photosapp_db_*.sql.gz 2>/dev/null | head -10 || echo "  (none found in $PROJECT_DIR/backups)"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

# Load .env (handles values with spaces)
ENV_FILE="$PROJECT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        key="${key// /}"
        value="${value%%#*}"
        value="${value#"${value%%[! ]*}"}"
        value="${value%"${value##*[! ]}"}"
        export "$key=$value"
    done < "$ENV_FILE"
fi

PG_CONTAINER="photosapp-postgres-1"
PG_USER="${POSTGRES_USER:-photosapp}"
PG_DB="${POSTGRES_DB:-photosapp}"

# ── Pre-flight checks ─────────────────────────────────────────────────────────

if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "ERROR: Backup file appears corrupt (failed gzip integrity check)." >&2
    exit 1
fi

if ! docker inspect "$PG_CONTAINER" > /dev/null 2>&1; then
    echo "ERROR: Container '$PG_CONTAINER' not found. Start the stack first:" >&2
    echo "       docker compose up -d postgres" >&2
    exit 1
fi

echo "Backup file : $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"
echo "Target DB   : $PG_DB on $PG_CONTAINER"
echo ""
echo "WARNING: This will DROP and recreate the '$PG_DB' database."
read -r -p "Type 'yes' to continue: " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

# ── Restore ───────────────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Enabling pgvector extension..."
docker exec "$PG_CONTAINER" \
    psql -U "$PG_USER" -d postgres \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Dropping and recreating database '$PG_DB'..."
docker exec "$PG_CONTAINER" \
    psql -U "$PG_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $PG_DB;" > /dev/null
docker exec "$PG_CONTAINER" \
    psql -U "$PG_USER" -d postgres \
    -c "CREATE DATABASE $PG_DB OWNER $PG_USER;" > /dev/null

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Enabling pgvector in restored database..."
docker exec "$PG_CONTAINER" \
    psql -U "$PG_USER" -d "$PG_DB" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restoring data (this may take a moment)..."
gunzip -c "$BACKUP_FILE" \
    | docker exec -i "$PG_CONTAINER" \
        psql -U "$PG_USER" -d "$PG_DB" -q

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restore complete."

# ── Restart backend ───────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarting backend to pick up restored data..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" restart backend > /dev/null
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. PhotosApp should be working normally."
