"""Mosaic persistence. Writes flush; callers own transactions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mosaic
from app.schemas.mosaic import MosaicLayout


async def get_by_profile_id(db: AsyncSession, profile_id: UUID) -> Mosaic | None:
    return await db.scalar(select(Mosaic).where(Mosaic.profile_id == profile_id))


async def get_for_update(db: AsyncSession, profile_id: UUID) -> Mosaic | None:
    return await db.scalar(
        select(Mosaic).where(Mosaic.profile_id == profile_id).with_for_update()
    )


async def create(db: AsyncSession, profile_id: UUID, layout: MosaicLayout) -> Mosaic:
    mosaic = Mosaic(profile_id=profile_id, **layout.model_dump())
    db.add(mosaic)
    await db.flush()
    return mosaic


async def save(db: AsyncSession, mosaic: Mosaic, layout: MosaicLayout) -> None:
    for field, value in layout.model_dump().items():
        setattr(mosaic, field, value)
    await db.flush()


async def activate(db: AsyncSession, mosaic: Mosaic) -> None:
    mosaic.is_active = True
    await db.flush()


async def retain_featured_albums(
    db: AsyncSession, mosaic: Mosaic, album_ids: list[str]
) -> None:
    mosaic.tiles = [
        tile for tile in mosaic.tiles if tile["spotifyAlbumId"] in album_ids
    ]
    await db.flush()
