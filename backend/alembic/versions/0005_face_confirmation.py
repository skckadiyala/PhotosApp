"""Add match_distance and status columns to faces table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-14
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column('faces', sa.Column('match_distance', sa.Float(), nullable=True, server_default='0'))
    op.add_column('faces', sa.Column('status', sa.String(20), nullable=True, server_default='confirmed'))
    # Backfill existing rows
    op.execute("UPDATE faces SET match_distance = 0 WHERE match_distance IS NULL")
    op.execute("UPDATE faces SET status = 'confirmed' WHERE status IS NULL")
    # Now make non-nullable
    op.alter_column('faces', 'match_distance', nullable=False)
    op.alter_column('faces', 'status', nullable=False)


def downgrade() -> None:
    op.drop_column('faces', 'status')
    op.drop_column('faces', 'match_distance')
