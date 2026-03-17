"""Add albums and album_photos tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-14
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            cover_photo_id UUID REFERENCES photos(id) ON DELETE SET NULL,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            is_smart BOOLEAN NOT NULL DEFAULT FALSE,
            smart_rules JSONB,
            photo_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_albums_user_id ON albums(user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS album_photos (
            album_id UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            photo_id UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (album_id, photo_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS album_photos")
    op.execute("DROP TABLE IF EXISTS albums")
