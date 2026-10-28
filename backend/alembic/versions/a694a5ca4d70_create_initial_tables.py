"""create initial tables

This is a genesis migration that should have existed from the start: the
`articles` table was originally created directly via SQLAlchemy (likely
Base.metadata.create_all()) before Alembic was ever set up, so the very
first real migration (1bf20f17f9b0, "add article category") was generated
by diffing against a database that already had the table — it only
captures an ALTER, never a CREATE. That's invisible on any database that
already has the table (which is every database that existed before today),
but it means `alembic upgrade head` can never actually initialize a
brand-new, empty database — exactly what broke here.

This migration creates `articles` in its original pre-1bf20f17f9b0 shape
(no category/dynamics/embedding columns, no unique constraint on url —
those are added by the migrations that already exist and run right after
this one). It's spliced in as the new true root; every existing revision
ID is untouched, so already-migrated databases are unaffected by this.

Revision ID: a694a5ca4d70
Revises:
Create Date: 2026-10-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a694a5ca4d70'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('articles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('published_at', sa.DateTime(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('headline', sa.String(), nullable=False),
    sa.Column('summary', sa.String(), nullable=False),
    sa.Column('key_points', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('articles')
