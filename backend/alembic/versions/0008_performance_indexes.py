"""Add performance indexes for large libraries (100K+ photos)

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-18
"""
from typing import Union
from alembic import op

revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial index for the main photo listing query:
    #   WHERE user_id = ? AND is_hidden = false ORDER BY taken_at DESC
    # Covers both the paginated SELECT and the COUNT(*) for total pages.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photos_user_visible
        ON photos (user_id, taken_at DESC NULLS LAST, created_at DESC)
        WHERE is_hidden = false
        """
    )

    # Partial index for the favorites page:
    #   WHERE user_id = ? AND is_favorite = true AND is_hidden = false
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photos_user_favorites
        ON photos (user_id, taken_at DESC NULLS LAST)
        WHERE is_favorite = true AND is_hidden = false
        """
    )

    # Partial index to help the geocoder quickly find photos that still
    # need reverse geocoding (GPS set but location_id not yet assigned).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photos_needs_geocoding
        ON photos (user_id)
        WHERE gps_latitude IS NOT NULL
          AND gps_longitude IS NOT NULL
          AND location_id IS NULL
        """
    )

    # Index to speed up media-type filtering (video/image split view).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photos_user_mime
        ON photos (user_id, mime_type, taken_at DESC NULLS LAST)
        WHERE is_hidden = false
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_photos_user_visible")
    op.execute("DROP INDEX IF EXISTS idx_photos_user_favorites")
    op.execute("DROP INDEX IF EXISTS idx_photos_needs_geocoding")
    op.execute("DROP INDEX IF EXISTS idx_photos_user_mime")
