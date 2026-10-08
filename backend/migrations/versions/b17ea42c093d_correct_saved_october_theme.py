"""Correct pre-pumpkin October 2026 hearts without regenerating listening data.

Revision ID: b17ea42c093d
Revises: a04c98be76d2

This is a one-time correction explicitly requested for already-saved artwork.
Downgrading retains the corrected data; both shapes are supported by the parent
revision. No accounts, listening selections, timestamps, or song IDs are changed.
"""

import sqlalchemy as sa
from alembic import op

revision = "b17ea42c093d"
down_revision = "a04c98be76d2"
branch_labels = None
depends_on = None

# Freeze the correction so future preset edits cannot change migration behavior.
PUMPKIN_MASK = (
    "....#....",
    "..#####..",
    ".#######.",
    "#########",
    "##.###.##",
    "####.####",
    "##.....##",
    ".#######.",
    "..#####..",
)


def upgrade() -> None:
    points = [
        (x, y)
        for y, row in enumerate(PUMPKIN_MASK)
        for x, cell in enumerate(row)
        if cell == "#"
    ]
    values = ", ".join(f"({index}, {x}, {y})" for index, (x, y) in enumerate(points))
    op.execute(
        sa.text(
            f"""
            UPDATE monthly_mosaics AS mosaic
            SET preset_key = 'pumpkin', grid_width = 9, grid_height = 9,
                tiles = (
                    SELECT jsonb_agg(jsonb_build_object(
                        'x', point.x, 'y', point.y,
                        'spotifyAlbumId', mosaic.album_ids ->>
                            (point.position % jsonb_array_length(mosaic.album_ids))
                    ) ORDER BY point.position)
                    FROM (VALUES {values}) AS point(position, x, y)
                )
            WHERE month = DATE '2026-10-01' AND preset_key = 'heart'
                AND jsonb_array_length(album_ids) BETWEEN 1 AND 50
            """
        )
    )


def downgrade() -> None:
    # Retain the intentional data correction rather than undoing users' artwork.
    pass
