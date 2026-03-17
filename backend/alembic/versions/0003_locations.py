"""Phase 3 — locations table + photo.location_id FK.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── locations ────────────────────────────────────────────
    # Table may already exist from metadata.create_all() — use IF NOT EXISTS via raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id UUID NOT NULL PRIMARY KEY,
            latitude FLOAT NOT NULL,
            longitude FLOAT NOT NULL,
            altitude FLOAT,
            city VARCHAR(200),
            state VARCHAR(200),
            country VARCHAR(100),
            formatted TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_locations_city ON locations (city)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_locations_country ON locations (country)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_locations_lat_lng ON locations (latitude, longitude)")

    # ── photos.location_id ──────────────────────────────────
    op.add_column('photos', sa.Column(
        'location_id', postgresql.UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        'fk_photos_location_id', 'photos', 'locations',
        ['location_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_photos_location_id', 'photos', ['location_id'])


def downgrade() -> None:
    op.drop_index('ix_photos_location_id', table_name='photos')
    op.drop_constraint('fk_photos_location_id', 'photos', type_='foreignkey')
    op.drop_column('photos', 'location_id')
    op.drop_index('idx_locations_lat_lng', table_name='locations')
    op.drop_index('ix_locations_country', table_name='locations')
    op.drop_index('ix_locations_city', table_name='locations')
    op.drop_table('locations')
