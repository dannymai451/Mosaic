"""Owner library browsing and persistent Featured Album selection."""

from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Profile
from app.repositories import profiles, sessions, spotify_connections
from app.schemas.album import Album, AlbumPage, FeaturedAlbums, FeaturedAlbumsPut
from app.services.spotify import (
    LIBRARY_SCOPE,
    SpotifyClient,
    SpotifyError,
    normalize_album,
)

router = APIRouter(prefix="/api/me", tags=["albums"])
Database = Annotated[AsyncSession, Depends(get_db)]


async def owner_profile(
    db: Database,
    response: Response,
    mosaic_session: str | None = Cookie(default=None),
) -> Profile:
    response.headers["Cache-Control"] = "no-store"
    async with db.begin():
        active = (
            await sessions.get_active(db, mosaic_session) if mosaic_session else None
        )
        if active is None:
            raise HTTPException(
                401, "Authentication required", headers={"Cache-Control": "no-store"}
            )
        profile = await profiles.get_by_user_id(db, active.user_id)
        if profile is None:
            raise HTTPException(
                404, "Profile not found", headers={"Cache-Control": "no-store"}
            )
    return profile


Owner = Annotated[Profile, Depends(owner_profile)]


@asynccontextmanager
async def spotify_for_owner(db: AsyncSession, profile: Profile):
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            # Serialize refresh-token rotation across requests for this account.
            async with db.begin():
                connection = await spotify_connections.get_for_update(
                    db, profile.user_id
                )
                if connection is None or LIBRARY_SCOPE not in connection.scopes.split():
                    raise SpotifyError(403, "spotify_reconnect_required")
                spotify = SpotifyClient(http, db, connection)
                await spotify.refresh()
            # Commit rotated tokens before a library read that may fail.
            yield spotify
    except SpotifyError as exc:
        headers = {"Cache-Control": "no-store"}
        if exc.retry_after is not None:
            headers["Retry-After"] = exc.retry_after
        raise HTTPException(exc.status, exc.code, headers=headers) from exc


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
        await profiles.set_featured_albums(db, profile, patch.album_ids)
    return FeaturedAlbums(albumIds=profile.featured_album_ids)
