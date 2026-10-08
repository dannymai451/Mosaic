"""Refine existing October pumpkins without replacing their saved listening.

Revision ID: c28fb53d104e
Revises: b17ea42c093d
"""

import sqlalchemy as sa
from alembic import op

revision = "c28fb53d104e"
down_revision = "b17ea42c093d"
branch_labels = None
depends_on = None

# Freeze this correction independently of future seasonal preset changes.
PUMPKIN_MASK = (
    "......##....",
    ".....##.....",
    "..########..",
    ".##########.",
    "###.####.###",
    "##...##...##",
    "#####..#####",
    "############",
    "##..#..#..##",
    ".##......##.",
    "..########..",
    "...######...",
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
        sa.text(f"""
        UPDATE monthly_mosaics AS mosaic
        SET grid_width = 12, grid_height = 12,
            tiles = (
                SELECT jsonb_agg(
                    (mosaic.tiles -> (point.position % jsonb_array_length(mosaic.tiles)))
                    || jsonb_build_object('x', point.x, 'y', point.y)
                    ORDER BY point.position
                )
                FROM (VALUES {values}) AS point(position, x, y)
            )
        WHERE month = DATE '2026-10-01' AND preset_key = 'pumpkin'
            AND grid_width = 9 AND grid_height = 9
            AND jsonb_array_length(tiles) BETWEEN 1 AND 81
    """)
    )


def downgrade() -> None:
    # Retain the requested visual correction, as with the preceding shape fix.
    pass
