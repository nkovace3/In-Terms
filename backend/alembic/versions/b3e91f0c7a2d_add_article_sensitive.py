"""add article sensitive

Revision ID: b3e91f0c7a2d
Revises: 5fc7a1fcb00c
Create Date: 2026-11-06 12:00:00.000000

Nullable on purpose: NULL means "not classified yet", and In Terms treats
that the same as sensitive (fails closed) until scripts/backfill_sensitive.py
has run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e91f0c7a2d'
down_revision: Union[str, Sequence[str], None] = '5fc7a1fcb00c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('articles', sa.Column('sensitive', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'sensitive')
