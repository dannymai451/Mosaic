"""Seasonal shapes and bounded, metadata-free user background uploads."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.models import MonthlyMosaic
from app.services.monthly_mosaic import PUMPKIN_MASK

SHAPES = {
    "pumpkin": ("Pumpkin", PUMPKIN_MASK),
    "ghost": (
        "Ghost",
        (
            "....####....",
            "...######...",
            "..########..",
            ".##########.",
            ".##..##..##.",
            ".##..##..##.",
            ".##########.",
            ".####..####.",
            ".####..####.",
            ".##########.",
            ".##########.",
            ".##..##..##.",
        ),
    ),
    "bat": (
        "Bat",
        (
            "....#..#....",
            "#...####...#",
            "##..####..##",
            "###.####.###",
            "############",
            "############",
            "############",
            "############",
            ".##########.",
            "..##.##.##..",
            ".....##.....",
            ".....##.....",
        ),
    ),
    "skull": (
        "Skull",
        (
            "...######...",
            "..########..",
            ".##########.",
            "############",
            "##...##...##",
            "##...##...##",
            "############",
            ".####..####.",
            "..########..",
            "..########..",
            "...#.##.#...",
            "...######...",
        ),
    ),
}


def shape_catalog():
    return [
        {
            "key": key,
            "label": label,
            "grid_width": 12,
            "grid_height": 12,
            "coordinates": [
                {"x": x, "y": y}
                for y, row in enumerate(mask)
                for x, cell in enumerate(row)
                if cell == "#"
            ],
        }
        for key, (label, mask) in SHAPES.items()
    ]


def remix_layout(snapshot: MonthlyMosaic, shape: str) -> dict:
    pairs = {}
    for tile in snapshot.tiles:
        album = tile["spotifyAlbumId"]
        track = tile.get("spotifyTrackId") or snapshot.representative_track_ids.get(
            album
        )
        pairs.setdefault(
            (album, track),
            {"spotifyAlbumId": album, **({"spotifyTrackId": track} if track else {})},
        )
    songs = list(pairs.values())
    if not songs:
        raise ValueError("No saved songs to remix")
    preset = next(item for item in shape_catalog() if item["key"] == shape)
    if len(songs) > len(preset["coordinates"]):
        raise ValueError("This shape cannot hold every saved song")
    return {
        "preset_key": shape,
        "grid_width": 12,
        "grid_height": 12,
        "tiles": [
            {**point, **songs[index % len(songs)]}
            for index, point in enumerate(preset["coordinates"])
        ],
    }


def normalize_background(content: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if (
                    source.format not in {"JPEG", "PNG", "WEBP"}
                    or source.width * source.height > 20_000_000
                ):
                    raise ValueError(
                        "Choose a JPEG, PNG, or WebP photo under 20 megapixels"
                    )
                source.load()
                photo = ImageOps.exif_transpose(source).convert("RGBA")
                photo.thumbnail((1600, 1600))
                canvas = Image.new("RGB", photo.size, "white")
                canvas.paste(photo, mask=photo.getchannel("A"))
                output = BytesIO()
                canvas.save(output, format="JPEG", quality=85, optimize=True)
                data = output.getvalue()
                if len(data) > 2_000_000:
                    raise ValueError("Photo is too large after resizing")
                return data
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Choose a valid JPEG, PNG, or WebP photo") from exc
