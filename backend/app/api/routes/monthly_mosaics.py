"""Private monthly archive and idempotent generation from recent listening."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Response

from app.api.dependencies import Database, Owner, spotify_for_owner
from app.models import MonthlyMosaic
from app.repositories import monthly_mosaics, profiles, spotify_connections
from app.schemas.monthly_mosaic import (
    MonthlyAlbum,
    MonthlyMosaicArchive,
    MonthlyMosaicCreate,
    MonthlyMosaicGenerated,
    MonthlyMosaicRead,
)
from app.services import monthly_mosaic, spotify_cache
from app.services.spotify import (
    TOP_SCOPE,
    SpotifyError,
)

router = APIRouter(prefix="/api/me/monthly-mosaics", tags=["monthly-mosaics"])


def read_monthly_mosaic(mosaic: MonthlyMosaic) -> MonthlyMosaicRead:
    return MonthlyMosaicRead(
        id=mosaic.id,
        month=mosaic.month.strftime("%Y-%m"),
        generated_at=mosaic.generated_at,
        source_track_count=mosaic.source_track_count,
        album_ids=mosaic.album_ids,
        preset_key=mosaic.preset_key,
        grid_width=mosaic.grid_width,
        grid_height=mosaic.grid_height,
        tiles=mosaic.tiles,
    )


@router.get("", response_model=MonthlyMosaicArchive)
async def get_archive(db: Database, profile: Owner):
    async with db.begin():
        items = await monthly_mosaics.list_for_profile(db, profile.id)
        return MonthlyMosaicArchive(
            current_month=monthly_mosaic.current_month().strftime("%Y-%m"),
            items=[read_monthly_mosaic(item) for item in items],
        )


@router.post("", response_model=MonthlyMosaicGenerated, status_code=201)
async def generate_monthly_mosaic(
    body: MonthlyMosaicCreate, response: Response, db: Database, profile: Owner
):
    generated_at = monthly_mosaic.utc_now().astimezone(UTC)
    month = generated_at.date().replace(day=1)
    async with db.begin():
        existing = await monthly_mosaics.get_for_month(db, profile.id, month)
        if existing is not None:
            response.status_code = 200
            return read_monthly_mosaic(existing)
    async with spotify_for_owner(db, profile, TOP_SCOPE) as spotify:
        (
            album_ids,
            track_count,
            representative_tracks,
            album_track_ids,
            artwork,
        ) = await spotify.recent_top_albums()
        if not album_ids:
            raise SpotifyError(422, "spotify_no_recent_listening")
    selected, layout = monthly_mosaic.monthly_layout(month, album_ids, album_track_ids)
    async with db.begin():
        # Recheck after serializing creates. Spotify reads never hold this lock.
        locked_profile = await profiles.get_for_update(db, profile.user_id)
        if locked_profile is None:
            raise HTTPException(404, "Profile not found")
        existing = await monthly_mosaics.get_for_month(db, profile.id, month)
        if existing is not None:
            response.status_code = 200
            return read_monthly_mosaic(existing)
        mosaic = await monthly_mosaics.create(
            db,
            profile.id,
            month=month,
            generated_at=generated_at,
            source_track_count=track_count,
            album_ids=selected,
            representative_track_ids={
                album_id: representative_tracks[album_id] for album_id in selected
            },
            layout=layout,
        )
        result = read_monthly_mosaic(mosaic)
    # Only seed the new snapshot's actual tile songs, after persistence succeeds.
    selected_artwork = {}
    for tile in mosaic.tiles:
        album_id, track_id = tile["spotifyAlbumId"], tile.get("spotifyTrackId")
        key = f"{album_id}:{track_id}"
        if key in artwork:
            selected_artwork[key] = artwork[key]
            spotify_cache.remember_metadata(
                spotify.connection, album_id, track_id, artwork[key]
            )
    return MonthlyMosaicGenerated(
        **result.model_dump(), artwork=selected_artwork,
        artwork_expires_at=datetime.now(UTC) + timedelta(seconds=spotify_cache.METADATA_TTL),
    )


@router.get("/{mosaic_id}/albums/{album_id}", response_model=MonthlyAlbum)
async def monthly_album_details(
    mosaic_id: UUID,
    album_id: Annotated[str, Path(pattern=r"^[a-zA-Z0-9]{22}$")],
    db: Database,
    profile: Owner,
    track_id: Annotated[str | None, Query(pattern=r"^[a-zA-Z0-9]{22}$")] = None,
):
    async with db.begin():
        mosaic = await monthly_mosaics.get_owned(db, profile.id, mosaic_id)
        if mosaic is None or album_id not in mosaic.album_ids:
            raise HTTPException(404, "Album not found")
        if track_id is not None and not any(
            tile["spotifyAlbumId"] == album_id
            and tile.get("spotifyTrackId") == track_id
            for tile in mosaic.tiles
        ):
            raise HTTPException(404, "Song not found")
        track_id = track_id or mosaic.representative_track_ids.get(album_id)
        connection = await spotify_connections.get_by_user_id(db, profile.user_id)
        if connection is not None and TOP_SCOPE in connection.scopes.split():
            cached = spotify_cache.monthly_metadata.get(
                (spotify_cache.connection_key(connection), album_id, track_id)
            )
            if cached is not None:
                return cached.model_copy(deep=True)
    async with spotify_for_owner(db, profile, TOP_SCOPE) as spotify:
        return await spotify.monthly_album(album_id, track_id)
