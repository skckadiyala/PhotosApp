"""Add timeline covering index, GPS bbox index, and face HNSW vector index

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-30

Why these indexes:

1. idx_photos_timeline_with_thumb (covering index for library summary / by-month)
   The library-summary and by-month queries filter on (user_id, mime_type) and
   order by COALESCE(taken_at, created_at).  For the ~95% of photos that have
   EXIF taken_at, a covering index on (user_id, mime_type, taken_at DESC)
   INCLUDE (id, thumb_sm) lets PostgreSQL answer the query entirely from the
   index without a heap fetch.  Photos with taken_at IS NULL fall through to
   a small heap scan, which is acceptable since undated photos are a minority.
   Note: a functional index on COALESCE(taken_at, created_at) is not possible
   because taken_at (timestamp) and created_at (timestamptz) require a cast
   that PostgreSQL does not consider IMMUTABLE.

2. idx_photos_gps_bbox (map viewport queries)
   The map API filters gps_latitude BETWEEN sw AND ne AND gps_longitude BETWEEN
   sw AND ne.  A composite (lat, lng) btree index lets PostgreSQL prune on
   latitude first then latitude+longitude, dramatically reducing rows examined
   for typical viewport sizes.

3. idx_faces_embedding_hnsw (face similarity search)
   Face similarity queries use embedding <-> query ORDER BY distance LIMIT N.
   Without an index every search is O(n) * 512 float comparisons.  HNSW gives
   ~95% recall at < 5 ms per query even for 1 M+ faces.
   m=16 (graph connectivity) and ef_construction=64 (build-time beam width)
   are conservative defaults that balance build time vs. recall.
"""
from typing import Union

from alembic import op
from sqlalchemy import text

revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Covering index for timeline queries (photos with EXIF dates) ────────
    # Covers library-summary, event-clusters, and by-month for dated photos.
    # INCLUDE (id, thumb_sm) enables index-only scans — no heap fetch needed.
    conn.execute(text(
        """
        CREATE INDEX IF NOT EXISTS idx_photos_timeline_with_thumb
        ON photos (user_id, mime_type, taken_at DESC NULLS LAST, created_at DESC)
        INCLUDE (id, thumb_sm)
        WHERE is_hidden = false
        """
    ))

    # ── 2. GPS bounding-box index for map viewport queries ────────────────────
    # Supports: WHERE gps_latitude BETWEEN sw AND ne AND gps_longitude BETWEEN sw AND ne
    conn.execute(text(
        """
        CREATE INDEX IF NOT EXISTS idx_photos_gps_bbox
        ON photos (gps_latitude, gps_longitude)
        WHERE gps_latitude IS NOT NULL
          AND gps_longitude IS NOT NULL
          AND is_hidden = false
        """
    ))

    # ── 3. HNSW vector index for face similarity search ───────────────────────
    # vector_l2_ops = Euclidean distance, consistent with ArcFace L2 normalization.
    # m=16, ef_construction=64: conservative settings (good recall, fast build).
    conn.execute(text(
        """
        CREATE INDEX IF NOT EXISTS idx_faces_embedding_hnsw
        ON faces USING hnsw (embedding vector_l2_ops)
        WITH (m = 16, ef_construction = 64)
        """
    ))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_photos_timeline_with_thumb")
    op.execute("DROP INDEX IF EXISTS idx_photos_gps_bbox")
    op.execute("DROP INDEX IF EXISTS idx_faces_embedding_hnsw")
