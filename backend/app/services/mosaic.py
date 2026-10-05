"""Deterministic coordinate presets and Featured Album placement validation."""

from app.schemas.mosaic import MosaicLayout, Preset, Tile

MASKS = {
    "heart": (
        "Heart",
        [
            ".........",
            ".##...##.",
            "####.####",
            "#########",
            "#########",
            ".#######.",
            "..#####..",
            "...###...",
            "....#....",
        ],
    ),
    "star": (
        "Star",
        [
            "....#....",
            "...###...",
            "...###...",
            "#########",
            ".#######.",
            "..#####..",
            "..#####..",
            ".###.###.",
            ".#.....#.",
        ],
    ),
    "music-note": (
        "Music note",
        [
            "...######",
            "...######",
            "...#....#",
            "...#....#",
            "...#....#",
            "...#....#",
            ".###..###",
            "####.####",
            ".##...##.",
        ],
    ),
    "blank": ("Blank / custom", ["........."] * 9),
}

PRESETS = [
    Preset(
        key=key,
        label=label,
        grid_width=9,
        grid_height=9,
        coordinates=[
            {"x": x, "y": y}
            for y, row in enumerate(rows)
            for x, cell in enumerate(row)
            if cell == "#"
        ],
    )
    for key, (label, rows) in MASKS.items()
]


def expand_preset(key: str, album_ids: list[str]) -> MosaicLayout:
    preset = next(preset for preset in PRESETS if preset.key == key)
    # Reuse covers when a small working set must fill a larger shape.
    tiles = (
        [
            Tile(**point.model_dump(), spotifyAlbumId=album_ids[index % len(album_ids)])
            for index, point in enumerate(preset.coordinates)
        ]
        if album_ids
        else []
    )
    return MosaicLayout(
        preset_key=preset.key,
        grid_width=preset.grid_width,
        grid_height=preset.grid_height,
        tiles=tiles,
    )


def uses_featured_albums(layout: MosaicLayout, album_ids: list[str]) -> bool:
    return all(tile.spotifyAlbumId in album_ids for tile in layout.tiles)
