"""Remix persistence; callers own authorization and transactions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtworkRemix, MonthlyMosaic


async def list_for_month(db: AsyncSession, monthly_id: UUID) -> list[ArtworkRemix]:
    return list(
        await db.scalars(
            select(ArtworkRemix)
            .where(ArtworkRemix.monthly_mosaic_id == monthly_id)
            .order_by(ArtworkRemix.created_at, ArtworkRemix.id)
        )
    )


async def get_owned(db: AsyncSession, profile_id: UUID, remix_id: UUID):
    return await db.scalar(
        select(ArtworkRemix)
        .join(MonthlyMosaic)
        .where(ArtworkRemix.id == remix_id, MonthlyMosaic.profile_id == profile_id)
    )


async def get_shared(db: AsyncSession, share_id: UUID):
    return await db.scalar(
        select(ArtworkRemix).where(ArtworkRemix.share_id == share_id)
    )


async def create(db: AsyncSession, monthly_id: UUID, **values) -> ArtworkRemix:
    remix = ArtworkRemix(monthly_mosaic_id=monthly_id, **values)
    db.add(remix)
    await db.flush()
    return remix


async def update(db: AsyncSession, remix: ArtworkRemix, **values) -> None:
    for name, value in values.items():
        setattr(remix, name, value)
    await db.flush()


async def delete(db: AsyncSession, remix: ArtworkRemix) -> None:
    await db.delete(remix)
    await db.flush()


async def background(db: AsyncSession, remix_id: UUID) -> bytes | None:
    return await db.scalar(
        select(ArtworkRemix.background_image).where(ArtworkRemix.id == remix_id)
    )
