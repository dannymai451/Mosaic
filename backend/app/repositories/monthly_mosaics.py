"""Immutable monthly snapshot persistence; callers own transactions."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MonthlyMosaic
from app.schemas.monthly_mosaic import MonthlyMosaicLayout
from app.schemas.mosaic import MosaicLayout


async def list_for_profile(db: AsyncSession, profile_id: UUID) -> list[MonthlyMosaic]:
    result = await db.scalars(
        select(MonthlyMosaic)
        .where(MonthlyMosaic.profile_id == profile_id)
        .order_by(MonthlyMosaic.month.desc())
    )
    return list(result)


async def get_for_month(
    db: AsyncSession, profile_id: UUID, month: date
) -> MonthlyMosaic | None:
    return await db.scalar(
        select(MonthlyMosaic).where(
            MonthlyMosaic.profile_id == profile_id, MonthlyMosaic.month == month
        )
    )


async def get_owned(
    db: AsyncSession, profile_id: UUID, mosaic_id: UUID
) -> MonthlyMosaic | None:
    return await db.scalar(
        select(MonthlyMosaic).where(
            MonthlyMosaic.profile_id == profile_id, MonthlyMosaic.id == mosaic_id
        )
    )


async def create(
    db: AsyncSession,
    profile_id: UUID,
    *,
    month: date,
    generated_at: datetime,
    source_track_count: int,
    album_ids: list[str],
    layout: MosaicLayout | MonthlyMosaicLayout,
    representative_track_ids: dict[str, str] | None = None,
) -> MonthlyMosaic:
    mosaic = MonthlyMosaic(
        profile_id=profile_id,
        month=month,
        generated_at=generated_at,
        source_track_count=source_track_count,
        album_ids=album_ids,
        representative_track_ids=representative_track_ids or {},
        **layout.model_dump(),
    )
    db.add(mosaic)
    await db.flush()
    return mosaic
