"""Add immutable private monthly snapshots, preserving legacy mosaics.

Revision ID: f83d16729a4c
Revises: e61ab049b823
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f83d16729a4c"
down_revision = "e61ab049b823"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_mosaics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_track_count", sa.Integer(), nullable=False),
        sa.Column("album_ids", postgresql.JSONB(), nullable=False),
        sa.Column("preset_key", sa.String(20), nullable=False),
        sa.Column("grid_width", sa.Integer(), nullable=False),
        sa.Column("grid_height", sa.Integer(), nullable=False),
        sa.Column("tiles", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM month) = 1", name="ck_monthly_mosaics_month"
        ),
        sa.CheckConstraint(
            "source_track_count BETWEEN 1 AND 50", name="ck_monthly_mosaics_tracks"
        ),
        sa.CheckConstraint(
            "grid_width BETWEEN 1 AND 12", name="ck_monthly_mosaics_width"
        ),
        sa.CheckConstraint(
            "grid_height BETWEEN 1 AND 12", name="ck_monthly_mosaics_height"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "month", name="uq_monthly_mosaics_profile_month"
        ),
    )


def downgrade() -> None:
    op.drop_table("monthly_mosaics")
