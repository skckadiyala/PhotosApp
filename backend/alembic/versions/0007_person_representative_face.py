"""Add representative_face_id to people table

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-18
"""
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'people',
        sa.Column(
            'representative_face_id',
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey('faces.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('people', 'representative_face_id')
