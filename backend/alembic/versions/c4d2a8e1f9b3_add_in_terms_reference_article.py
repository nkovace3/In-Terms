"""add in_terms reference article

Revision ID: c4d2a8e1f9b3
Revises: b3e91f0c7a2d
Create Date: 2026-11-12 12:00:00.000000

The real target-domain story an In Terms card compares against. SET NULL on
delete so removing a reference article leaves the translation intact.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d2a8e1f9b3'
down_revision: Union[str, Sequence[str], None] = 'b3e91f0c7a2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('in_terms', sa.Column('reference_article_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_in_terms_reference_article', 'in_terms', 'articles',
        ['reference_article_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_in_terms_reference_article', 'in_terms', type_='foreignkey')
    op.drop_column('in_terms', 'reference_article_id')
