#!/bin/bash
set -euo pipefail

echo "=== Initializing PhotosApp Database ==="

# Wait for PostgreSQL
until docker compose exec postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo "PostgreSQL is ready."

# Enable pgvector extension
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo "pgvector extension enabled."

# Run migrations
docker compose exec backend alembic upgrade head
echo "Migrations applied."

echo "=== Database initialization complete ==="
