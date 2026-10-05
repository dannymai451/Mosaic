"""Owner profile editing routes."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories import profiles, sessions
from app.schemas.profile import ProfilePatch

router = APIRouter(prefix="/api/me/profile", tags=["profiles"])


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
                    raise HTTPException(status_code=409, detail="Username is unavailable")

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
