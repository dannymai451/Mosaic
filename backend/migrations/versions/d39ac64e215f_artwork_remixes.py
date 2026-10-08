"""Saved visual variations and independently revocable public links.

Revision ID: d39ac64e215f
Revises: c28fb53d104e
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d39ac64e215f"
down_revision = "c28fb53d104e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artwork_remixes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "monthly_mosaic_id",
            sa.Uuid(),
            sa.ForeignKey("monthly_mosaics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("style", postgresql.JSONB(), nullable=False),
        sa.Column("layout", postgresql.JSONB(), nullable=False),
        sa.Column("share_id", sa.Uuid(), unique=True, nullable=True),
        sa.Column(
            "has_background",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "background_version",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("background_image", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_artwork_remixes_monthly_mosaic_id", "artwork_remixes", ["monthly_mosaic_id"]
    )


def downgrade():
    op.drop_table("artwork_remixes")
