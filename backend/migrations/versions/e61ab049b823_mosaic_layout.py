"""Persist one mosaic layout per profile, without Spotify catalog metadata.

Revision ID: e61ab049b823
Revises: d492ab31e706
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e61ab049b823"
down_revision = "d492ab31e706"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mosaics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("preset_key", sa.String(20), nullable=False),
        sa.Column("grid_width", sa.Integer(), nullable=False),
        sa.Column("grid_height", sa.Integer(), nullable=False),
        sa.Column(
            "tiles",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.CheckConstraint("grid_width BETWEEN 1 AND 12", name="ck_mosaics_width"),
        sa.CheckConstraint("grid_height BETWEEN 1 AND 12", name="ck_mosaics_height"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id"),
    )


def downgrade() -> None:
    op.drop_table("mosaics")
