"""Small owner-facing album contracts, independent of Spotify payloads."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

AlbumId = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9]{22}$")]


class FeaturedAlbumsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    album_ids: list[AlbumId] = Field(max_length=100)

    @field_validator("album_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Album IDs must be unique")
        return value


class FeaturedAlbums(BaseModel):
    albumIds: list[str]


class Album(BaseModel):
    id: str
    name: str
    artists: list[str]
    imageUrl: str | None
    spotifyUrl: str
    releaseDate: str
    totalTracks: int


class AlbumPage(BaseModel):
    items: list[Album]
    total: int
    nextOffset: int | None
