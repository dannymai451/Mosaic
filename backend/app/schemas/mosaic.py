"""Complete layout contracts shared by preset expansion and owner saves."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.album import AlbumId

PresetKey = Literal["heart", "star", "music-note", "blank"]


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=11)


class Tile(Coordinate):
    spotifyAlbumId: AlbumId


class MosaicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_key: PresetKey = "blank"


class MosaicLayout(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    preset_key: PresetKey
    grid_width: int = Field(ge=1, le=12)
    grid_height: int = Field(ge=1, le=12)
    tiles: list[Tile] = Field(max_length=100)

    @model_validator(mode="after")
    def valid_coordinates(self):
        positions = set()
        for tile in self.tiles:
            if tile.x >= self.grid_width or tile.y >= self.grid_height:
                raise ValueError("Tile is outside the grid")
            if (tile.x, tile.y) in positions:
                raise ValueError("Tile coordinates must be unique")
            positions.add((tile.x, tile.y))
        return self


class MosaicRead(MosaicLayout):
    id: UUID
    is_active: bool


class Preset(BaseModel):
    key: PresetKey
    label: str
    grid_width: int
    grid_height: int
    coordinates: list[Coordinate]
