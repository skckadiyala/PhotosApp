"""Phase 2 — people and faces tables + pgvector extension.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── people ───────────────────────────────────────────────
    op.create_table(
        'people',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('face_count', sa.Integer(), server_default='0'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_people_name', 'people', ['name'])
    op.create_index('ix_people_user_id', 'people', ['user_id'])

    # ── faces ────────────────────────────────────────────────
    op.create_table(
        'faces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('photo_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('photos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('people.id', ondelete='SET NULL'), nullable=True),

        # Bounding box (top, right, bottom, left)
        sa.Column('bbox_top', sa.Integer(), nullable=False),
        sa.Column('bbox_right', sa.Integer(), nullable=False),
        sa.Column('bbox_bottom', sa.Integer(), nullable=False),
        sa.Column('bbox_left', sa.Integer(), nullable=False),

        # 128-d face embedding (pgvector)
        sa.Column('embedding', sa.Text(), nullable=False),  # Will be altered to vector type

        sa.Column('confidence', sa.Float(), server_default='0.0'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Change embedding column to vector(128)
    op.execute("ALTER TABLE faces ALTER COLUMN embedding TYPE vector(128) USING embedding::vector(128)")

    op.create_index('ix_faces_photo_id', 'faces', ['photo_id'])
    op.create_index('ix_faces_person_id', 'faces', ['person_id'])

    # IVFFlat index for fast nearest-neighbor on embeddings
    op.execute("""
        CREATE INDEX ix_faces_embedding ON faces
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)


def downgrade() -> None:
    op.drop_table('faces')
    op.drop_table('people')
    op.execute("DROP EXTENSION IF EXISTS vector")
