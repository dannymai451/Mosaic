"""UTC period labels and shared monthly shapes for recent-listening snapshots."""

from datetime import UTC, date, datetime

from app.schemas.monthly_mosaic import MonthlyMosaicLayout
from app.services.mosaic import PRESETS, expand_preset

MONTHLY_PRESETS = ("heart", "star", "music-note")
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
PUMPKIN_COORDINATES = [
    {"x": x, "y": y}
    for y, row in enumerate(PUMPKIN_MASK)
    for x, cell in enumerate(row)
    if cell == "#"
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def current_month() -> date:
    return utc_now().astimezone(UTC).date().replace(day=1)


def monthly_layout(
    month: date,
    album_ids: list[str],
    album_track_ids: dict[str, list[str]] | None = None,
):
    if month.month == 10:
        selected = album_ids[: len(PUMPKIN_COORDINATES)]
        layout = MonthlyMosaicLayout(
            preset_key="pumpkin",
            grid_width=len(PUMPKIN_MASK[0]),
            grid_height=len(PUMPKIN_MASK),
            tiles=[
                {**point, "spotifyAlbumId": selected[index % len(selected)]}
                for index, point in enumerate(PUMPKIN_COORDINATES)
            ]
            if selected
            else [],
        )
    else:
        key = MONTHLY_PRESETS[
            (month.year * 12 + month.month - 1) % len(MONTHLY_PRESETS)
        ]
        preset = next(item for item in PRESETS if item.key == key)
        selected = album_ids[: len(preset.coordinates)]
        layout = MonthlyMosaicLayout.model_validate(
            expand_preset(key, selected).model_dump()
        )
    # Each repeated cover cycles through that album's songs from this snapshot.
    occurrences: dict[str, int] = {}
    for tile in layout.tiles:
        tracks = (album_track_ids or {}).get(tile.spotifyAlbumId, [])
        if tracks:
            occurrence = occurrences.get(tile.spotifyAlbumId, 0)
            tile.spotifyTrackId = tracks[occurrence % len(tracks)]
            occurrences[tile.spotifyAlbumId] = occurrence + 1
    return selected, layout
