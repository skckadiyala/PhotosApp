"""Upgrade face embeddings from 128-d (dlib/face_recognition) to 512-d (DeepFace/ArcFace).

All existing face and person data is cleared because embeddings produced by
different models are geometrically incompatible — re-clustering 128-d dlib
embeddings alongside 512-d ArcFace embeddings would produce nonsense results.
Run face reprocessing after applying this migration.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-01
"""
from typing import Union

from alembic import op

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the IVFFlat index — it is tied to the old vector dimension.
    op.execute("DROP INDEX IF EXISTS ix_faces_embedding")

    # Clear all face data.  128-d dlib embeddings and 512-d ArcFace embeddings
    # are incompatible; mixing them would corrupt any future clustering run.
    op.execute("DELETE FROM faces")
    op.execute("DELETE FROM people")

    # Resize the embedding column from 128-d to 512-d.
    op.execute(
        "ALTER TABLE faces ALTER COLUMN embedding TYPE vector(512) "
        "USING NULL::vector(512)"
    )

    # Recreate the IVFFlat index for 512-d cosine similarity search.
    op.execute(
        "CREATE INDEX ix_faces_embedding ON faces "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_faces_embedding")
    op.execute("DELETE FROM faces")
    op.execute(
        "ALTER TABLE faces ALTER COLUMN embedding TYPE vector(128) "
        "USING NULL::vector(128)"
    )
    op.execute(
        "CREATE INDEX ix_faces_embedding ON faces "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
