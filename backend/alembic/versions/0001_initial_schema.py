"""Initial schema — users and photos tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # ── photos ───────────────────────────────────────────────
    op.create_table(
        'photos',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('file_path', sa.Text(), unique=True, nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(50), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),

        # EXIF
        sa.Column('taken_at', sa.DateTime(), nullable=True),
        sa.Column('camera_make', sa.String(100), nullable=True),
        sa.Column('camera_model', sa.String(100), nullable=True),
        sa.Column('lens_model', sa.String(100), nullable=True),
        sa.Column('f_number', sa.Float(), nullable=True),
        sa.Column('exposure_time', sa.String(20), nullable=True),
        sa.Column('iso', sa.Integer(), nullable=True),
        sa.Column('focal_length', sa.Float(), nullable=True),
        sa.Column('orientation', sa.SmallInteger(), nullable=True),

        # GPS
        sa.Column('gps_latitude', sa.Float(), nullable=True),
        sa.Column('gps_longitude', sa.Float(), nullable=True),

        # FK
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),

        # Flags
        sa.Column('is_favorite', sa.Boolean(), server_default='false'),
        sa.Column('is_hidden', sa.Boolean(), server_default='false'),
        sa.Column('is_processed', sa.Boolean(), server_default='false'),

        # Thumbnails
        sa.Column('thumb_sm', sa.String(500), nullable=True),
        sa.Column('thumb_md', sa.String(500), nullable=True),
        sa.Column('thumb_lg', sa.String(500), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_photos_file_hash', 'photos', ['file_hash'])
    op.create_index('ix_photos_taken_at', 'photos', ['taken_at'])
    op.create_index('idx_photos_user_taken', 'photos', ['user_id', 'taken_at'])
    op.create_index(
        'idx_photos_not_processed', 'photos', ['is_processed'],
        postgresql_where=sa.text('is_processed = false'),
    )


def downgrade() -> None:
    op.drop_table('photos')
    op.drop_table('users')
