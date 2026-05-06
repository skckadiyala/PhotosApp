#!/usr/bin/env bash
# PhotosApp database backup script.
#
# Usage:
#   ./scripts/backup-db.sh [backup_dir]
#
# Environment variables (all optional, defaults read from .env):
#   BACKUP_DIR   — where to write backups (default: ./backups)
#   KEEP_LAST    — number of backups to retain before rotating (default: 12)
#
# Recommended cron (weekly on Sunday at 2 AM):
#   0 2 * * 0 cd /path/to/PhotosApp && ./scripts/backup-db.sh >> /tmp/photosapp-backup.log 2>&1
#
# Recommended cron (monthly on 1st at 2 AM):
#   0 2 1 * * cd /path/to/PhotosApp && ./scripts/backup-db.sh >> /tmp/photosapp-backup.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env so DB credentials are available (handles values with spaces)
ENV_FILE="$PROJECT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    while IFS='=' read -r key value; do
        # Skip comments and blank lines
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        key="${key// /}"          # strip spaces around key
        value="${value%%#*}"      # strip inline comments
        value="${value#"${value%%[! ]*}"}"  # ltrim
        value="${value%"${value##*[! ]}"}"  # rtrim
        export "$key=$value"
    done < "$ENV_FILE"
fi

BACKUP_DIR="${1:-${BACKUP_DIR:-$PROJECT_DIR/backups}}"
KEEP_LAST="${KEEP_LAST:-12}"
PG_CONTAINER="photosapp-postgres-1"
PG_USER="${POSTGRES_USER:-photosapp}"
PG_DB="${POSTGRES_DB:-photosapp}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/photosapp_db_${TIMESTAMP}.sql.gz"

# ── Pre-flight checks ─────────────────────────────────────────────────────────

if ! docker inspect "$PG_CONTAINER" > /dev/null 2>&1; then
    echo "ERROR: Container '$PG_CONTAINER' not found. Is the stack running?" >&2
    echo "       Try: docker compose up -d" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# ── Dump ──────────────────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backup → $BACKUP_FILE"

docker exec "$PG_CONTAINER" \
    pg_dump -U "$PG_USER" -d "$PG_DB" \
    --no-owner --no-privileges \
    | gzip > "$BACKUP_FILE"

# Verify the file is a valid gzip (catches silent pipe failures)
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "ERROR: Backup file failed integrity check — removing corrupt file." >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi

SIZE="$(du -sh "$BACKUP_FILE" | cut -f1)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete: $(basename "$BACKUP_FILE") ($SIZE)"

# ── Rotate old backups ────────────────────────────────────────────────────────

ROTATED=0
while IFS= read -r old_file; do
    [[ -z "$old_file" ]] && continue
    echo "  Removed: $(basename "$old_file")"
    rm -f "$old_file"
    ROTATED=$((ROTATED + 1))
done < <(ls -t "$BACKUP_DIR"/photosapp_db_*.sql.gz 2>/dev/null | tail -n "+$((KEEP_LAST + 1))")

[[ $ROTATED -gt 0 ]] && echo "Rotated $ROTATED old backup(s) (keeping last $KEEP_LAST)."

TOTAL="$(ls "$BACKUP_DIR"/photosapp_db_*.sql.gz 2>/dev/null | wc -l | tr -d ' ')"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. $TOTAL backup(s) in $BACKUP_DIR"

# ── Restore hint ──────────────────────────────────────────────────────────────

echo ""
echo "To restore this backup run:"
echo "  ./scripts/restore-db.sh $BACKUP_FILE"
