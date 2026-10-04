"""Persist encrypted refresh tokens only; encryption belongs to the caller."""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SpotifyConnection


async def get_by_user_id(db: AsyncSession, user_id: UUID) -> SpotifyConnection | None:
    return await db.get(SpotifyConnection, user_id)


async def upsert(
    db: AsyncSession,
    *,
    user_id: UUID,
    encrypted_refresh_token: str,
    scopes: str,
) -> SpotifyConnection:
    statement = insert(SpotifyConnection).values(
        user_id=user_id,
        encrypted_refresh_token=encrypted_refresh_token,
        scopes=scopes,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[SpotifyConnection.user_id],
        set_={
            "encrypted_refresh_token": statement.excluded.encrypted_refresh_token,
            "scopes": statement.excluded.scopes,
        },
    ).returning(SpotifyConnection)
    return (
        await db.scalars(statement, execution_options={"populate_existing": True})
    ).one()
