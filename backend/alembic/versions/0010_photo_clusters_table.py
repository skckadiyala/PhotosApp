"""Add photo_clusters materialized table for fast event-cluster pagination

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-30

Why:
The event-clusters endpoint runs a 7-CTE chain that processes the entire photo
table on every paginated request.  For a 60 K-photo library this computes
1 000+ cluster boundaries from scratch on every page scroll.

Instead, we pre-compute cluster assignments once (after a scan or on demand)
and store them in photo_clusters.  The API then reads pre-computed rows with
a simple OFFSET/LIMIT — O(1) query instead of O(n) scan.

Schema:
  photo_clusters stores one row per photo with its cluster_id and the cluster's
  aggregate metadata (start/end timestamps, count).  This allows:
    - Fast pagination:  SELECT DISTINCT cluster_id ... OFFSET :o LIMIT :l
    - Fast cluster detail:  SELECT * FROM photo_clusters WHERE cluster_id = :id
    - Fast cover photo lookup: one extra column, no JOIN needed
  The gap_hours parameter is stored so we can detect stale data and rebuild
  when the user changes the gap setting.
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'photo_clusters',
        sa.Column('photo_id', UUID(as_uuid=True),
                  sa.ForeignKey('photos.id', ondelete='CASCADE'),
                  nullable=False, primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('media_type', sa.String(10), nullable=False),   # 'image' or 'video'
        sa.Column('gap_hours', sa.Integer, nullable=False),
        sa.Column('cluster_id', sa.BigInteger, nullable=False),
        sa.Column('cluster_start', sa.DateTime(timezone=True)),
        sa.Column('cluster_end', sa.DateTime(timezone=True)),
        sa.Column('cluster_count', sa.Integer, nullable=False, default=0),
        sa.Column('is_cover', sa.Boolean, nullable=False, default=False),
        sa.Column('computed_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )

    # Primary lookup: paginate clusters for a user/media_type/gap_hours combo
    op.create_index(
        'idx_clusters_user_media_gap',
        'photo_clusters',
        ['user_id', 'media_type', 'gap_hours', 'cluster_id'],
    )

    # Fast cover-photo lookup per cluster
    op.create_index(
        'idx_clusters_cover',
        'photo_clusters',
        ['user_id', 'media_type', 'gap_hours', 'cluster_id'],
        postgresql_where=sa.text('is_cover = true'),
    )


def downgrade() -> None:
    op.drop_table('photo_clusters')
