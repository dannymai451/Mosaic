"""Session persistence hashes opaque tokens before storing or querying them."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def create(
    db: AsyncSession, *, token: str, user_id: UUID, expires_at: datetime
) -> Session:
    session = Session(id=token_digest(token), user_id=user_id, expires_at=expires_at)
    db.add(session)
    await db.flush()
    return session


async def get_active(db: AsyncSession, token: str) -> Session | None:
    return await db.scalar(
        select(Session).where(
            Session.id == token_digest(token),
            Session.expires_at > datetime.now(UTC),
        )
    )


async def delete_by_token(db: AsyncSession, token: str) -> None:
    await db.execute(delete(Session).where(Session.id == token_digest(token)))


async def delete_expired(db: AsyncSession) -> int:
    result = await db.execute(
        delete(Session).where(Session.expires_at <= datetime.now(UTC))
    )
    return result.rowcount
