"""Session-derived owner identity shared by album and mosaic routes."""

from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Profile
from app.repositories import profiles, sessions, spotify_connections
from app.services import spotify_cache
from app.services.spotify import LIBRARY_SCOPE, SpotifyClient, SpotifyError

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
async def spotify_for_owner(
    db: AsyncSession, profile: Profile, required_scope: str = LIBRARY_SCOPE
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            async with spotify_cache.serialized_refresh(profile.user_id):
                async with db.begin():
                    connection = await spotify_connections.get_for_update(
                        db, profile.user_id
                    )
                    if (
                        connection is None
                        or required_scope not in connection.scopes.split()
                    ):
                        raise SpotifyError(403, "spotify_reconnect_required")
                    spotify = SpotifyClient(http, db, connection)
                    if not spotify.use_cached_access_token():
                        await spotify.refresh()
                spotify.cache_access_token()
            if required_scope not in spotify.connection.scopes.split():
                raise SpotifyError(403, "spotify_reconnect_required")
            yield spotify
    except SpotifyError as exc:
        headers = {"Cache-Control": "no-store"}
        if exc.retry_after is not None:
            headers["Retry-After"] = exc.retry_after
        raise HTTPException(exc.status, exc.code, headers=headers) from exc
