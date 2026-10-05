"""Persist the owner's working album set, without catalog metadata.

Revision ID: d492ab31e706
Revises: c81e702f41d2
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d492ab31e706"
down_revision = "c81e702f41d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "featured_album_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "featured_album_ids")
