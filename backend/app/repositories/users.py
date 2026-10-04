"""User persistence. Writes flush; callers own commit and rollback."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def get_by_spotify_account_id(
    db: AsyncSession, spotify_account_id: str
) -> User | None:
    return await db.scalar(
        select(User).where(User.spotify_account_id == spotify_account_id)
    )


async def create(db: AsyncSession, *, spotify_account_id: str) -> User:
    user = User(spotify_account_id=spotify_account_id)
    db.add(user)
    await db.flush()
    return user
