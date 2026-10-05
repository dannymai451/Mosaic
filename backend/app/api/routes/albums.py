"""Owner library browsing and persistent Featured Album selection."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.dependencies import Database, Owner, spotify_for_owner
from app.repositories import mosaics, profiles
from app.schemas.album import Album, AlbumPage, FeaturedAlbums, FeaturedAlbumsPut
from app.services.spotify import normalize_album

router = APIRouter(prefix="/api/me", tags=["albums"])


@router.get("/albums", response_model=AlbumPage)
async def saved_albums(
    db: Database,
    profile: Owner,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    async with spotify_for_owner(db, profile) as spotify:
        return await spotify.saved_albums(limit=limit, offset=offset)


@router.get("/albums/{album_id}", response_model=Album)
async def featured_album_details(
    album_id: Annotated[str, Path(pattern=r"^[a-zA-Z0-9]{22}$")],
    db: Database,
    profile: Owner,
):
    # Resolve off-page selections on demand rather than copying catalog data to DB.
    if album_id not in profile.featured_album_ids:
        raise HTTPException(404, "Featured album not found")
    async with spotify_for_owner(db, profile) as spotify:
        return normalize_album(await spotify.get(f"/albums/{album_id}"))


@router.get("/featured-albums", response_model=FeaturedAlbums)
async def get_featured_albums(profile: Owner):
    return FeaturedAlbums(albumIds=profile.featured_album_ids)


@router.put("/featured-albums", response_model=FeaturedAlbums)
async def save_featured_albums(patch: FeaturedAlbumsPut, db: Database, profile: Owner):
    # Existing selections remain removable when Spotify is unavailable or unsaved.
    added = [
        album_id
        for album_id in patch.album_ids
        if album_id not in profile.featured_album_ids
    ]
    if added:
        async with spotify_for_owner(db, profile) as spotify:
            await spotify.require_saved(added)
    async with db.begin():
        profile = await profiles.get_for_update(db, profile.user_id)
        await profiles.set_featured_albums(db, profile, patch.album_ids)
        mosaic = await mosaics.get_for_update(db, profile.id)
        if mosaic is not None:
            await mosaics.retain_featured_albums(db, mosaic, patch.album_ids)
    return FeaturedAlbums(albumIds=profile.featured_album_ids)
