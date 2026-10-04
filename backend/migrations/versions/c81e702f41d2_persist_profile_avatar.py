"""Persist Spotify avatar for database-backed /api/me.

Revision ID: c81e702f41d2
Revises: b74f236d90ab
"""

import sqlalchemy as sa
from alembic import op

revision = "c81e702f41d2"
down_revision = "b74f236d90ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "avatar_url")
