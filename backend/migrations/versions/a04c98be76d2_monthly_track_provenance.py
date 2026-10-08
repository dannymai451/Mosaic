"""Retain representative track IDs without copying Spotify metadata.

Revision ID: a04c98be76d2
Revises: f83d16729a4c
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a04c98be76d2"
down_revision = "f83d16729a4c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monthly_mosaics",
        sa.Column(
            "representative_track_ids",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("monthly_mosaics", "representative_track_ids")
