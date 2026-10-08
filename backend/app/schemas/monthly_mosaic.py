"""Owner-only monthly archive and generation contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.album import Album, AlbumId
from app.schemas.mosaic import MosaicLayout, Tile


class MonthlyMosaicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MonthlyTile(Tile):
    spotifyTrackId: AlbumId | None = None


class MonthlyMosaicLayout(MosaicLayout):
    preset_key: Literal["heart", "star", "music-note", "blank", "pumpkin"]
    tiles: list[MonthlyTile] = Field(max_length=100)


class MonthlyMosaicRead(MonthlyMosaicLayout):
    id: UUID
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    generated_at: datetime
    listening_basis: Literal["spotify_short_term"] = "spotify_short_term"
    source_track_count: int
    album_ids: list[AlbumId]


class MonthlyMosaicArchive(BaseModel):
    current_month: str
    items: list[MonthlyMosaicRead]


class RepresentativeTrack(BaseModel):
    id: AlbumId
    name: str
    artists: list[str]
    spotifyUrl: str


class MonthlyAlbum(Album):
    representativeTrack: RepresentativeTrack | None = None
    trackDetailsUnavailable: bool = False


class MonthlyMosaicGenerated(MonthlyMosaicRead):
    # Transient, allowlisted display data; never stored on the monthly record.
    artwork: dict[str, MonthlyAlbum] = Field(default_factory=dict)
    artwork_expires_at: datetime | None = None
