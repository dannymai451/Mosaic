"""Profile persistence. Writes flush; callers own commit and rollback."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile


async def get_by_user_id(db: AsyncSession, user_id: UUID) -> Profile | None:
    return await db.scalar(select(Profile).where(Profile.user_id == user_id))


async def get_for_update(db: AsyncSession, user_id: UUID) -> Profile | None:
    return await db.scalar(
        select(Profile)
        .where(Profile.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_by_username(db: AsyncSession, username: str) -> Profile | None:
    return await db.scalar(select(Profile).where(Profile.username == username))


async def create(
    db: AsyncSession,
    *,
    user_id: UUID,
    username: str,
    display_name: str,
    bio: str = "",
    visibility: str = "private",
    theme: dict[str, object] | None = None,
) -> Profile:
    profile = Profile(
        user_id=user_id,
        username=username,
        display_name=display_name,
        bio=bio,
        visibility=visibility,
        theme={} if theme is None else theme,
    )
    db.add(profile)
    await db.flush()
    return profile


async def set_featured_albums(
    db: AsyncSession, profile: Profile, album_ids: list[str]
) -> None:
    profile.featured_album_ids = list(album_ids)
    await db.flush()


async def update(
    db: AsyncSession,
    profile: Profile,
    *,
    username: str | None = None,
    display_name: str | None = None,
    bio: str | None = None,
    visibility: str | None = None,
    theme: dict[str, object] | None = None,
) -> Profile:
    for field, value in {
        "username": username,
        "display_name": display_name,
        "bio": bio,
        "visibility": visibility,
        "theme": theme,
    }.items():
        if value is not None:
            setattr(profile, field, value)
    await db.flush()
    return profile
