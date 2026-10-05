"""Owner profile editing and read-only public sharing routes."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import spotify_for_owner
from app.db.session import get_db
from app.repositories import mosaics, profiles, sessions
from app.schemas.album import Album
from app.schemas.profile import ProfilePatch
from app.services.spotify import normalize_album

router = APIRouter(prefix="/api/me/profile", tags=["profiles"])
public_router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@public_router.get("/{username}/public")
async def get_public_profile(
    username: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Visibility changes must apply immediately, including for previously shared URLs.
    response.headers["Cache-Control"] = "no-store"
    profile = await profiles.get_by_username(db, username)
    if profile is None or profile.visibility != "public":
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
            headers={"Cache-Control": "no-store"},
        )
    mosaic = await mosaics.get_by_profile_id(db, profile.id)
    # Explicit allowlist: no internal identity, session, or Spotify connection data.
    return {
        "username": profile.username,
        "displayName": profile.display_name,
        "images": [{"url": profile.avatar_url}] if profile.avatar_url else [],
        "bio": profile.bio,
        "theme": profile.theme,
        "mosaic": {
            "preset_key": mosaic.preset_key,
            "grid_width": mosaic.grid_width,
            "grid_height": mosaic.grid_height,
            "tiles": mosaic.tiles,
        }
        if mosaic and mosaic.is_active
        else None,
    }


@public_router.get("/{username}/albums/{album_id}", response_model=Album)
async def public_album(
    username: str,
    album_id: Annotated[str, Path(pattern=r"^[a-zA-Z0-9]{22}$")],
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    response.headers["Cache-Control"] = "no-store"
    async with db.begin():
        profile = await profiles.get_by_username(db, username)
        mosaic = await mosaics.get_by_profile_id(db, profile.id) if profile else None
        if (
            profile is None
            or profile.visibility != "public"
            or mosaic is None
            or not mosaic.is_active
            or not any(tile["spotifyAlbumId"] == album_id for tile in mosaic.tiles)
        ):
            raise HTTPException(
                404, "Album not found", headers={"Cache-Control": "no-store"}
            )
    async with spotify_for_owner(db, profile) as spotify:
        return normalize_album(await spotify.get(f"/albums/{album_id}"))


@router.patch("")
async def update_my_profile(
    patch: ProfilePatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    mosaic_session: str | None = Cookie(default=None),
):
    if not mosaic_session:
        raise HTTPException(status_code=401, detail="Authentication required")

    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field is required")

    proposed_username = changes.get("username")
    try:
        async with db.begin():
            active_session = await sessions.get_active(db, mosaic_session)
            if active_session is None:
                raise HTTPException(status_code=401, detail="Authentication required")

            profile = await profiles.get_by_user_id(db, active_session.user_id)
            if profile is None:
                raise HTTPException(status_code=404, detail="Profile not found")

            if proposed_username is not None and proposed_username != profile.username:
                existing = await profiles.get_by_username(db, proposed_username)
                if existing is not None:
                    raise HTTPException(
                        status_code=409, detail="Username is unavailable"
                    )

            await profiles.update(db, profile, **changes)
            result = {
                "username": profile.username,
                "displayName": profile.display_name,
                "images": [{"url": profile.avatar_url}] if profile.avatar_url else [],
                "bio": profile.bio,
                "visibility": profile.visibility,
                "theme": profile.theme,
            }

    except IntegrityError as exc:
        # A competing request may claim the username after the preflight lookup.
        await db.rollback()
        if proposed_username is not None:
            existing = await profiles.get_by_username(db, proposed_username)
            if existing is not None:
                raise HTTPException(
                    status_code=409, detail="Username is unavailable"
                ) from exc
        raise

    return result
