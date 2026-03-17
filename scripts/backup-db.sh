#!/bin/bash
set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/photosapp_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Backing up database to ${BACKUP_FILE}..."

docker compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER:-photosapp}" \
    -d "${POSTGRES_DB:-photosapp}" \
    --no-owner \
    --no-privileges \
    | gzip > "$BACKUP_FILE"

echo "Backup complete: ${BACKUP_FILE} ($(du -h "$BACKUP_FILE" | cut -f1))"
