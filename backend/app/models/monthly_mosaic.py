"""Private monthly snapshots; Spotify catalog metadata remains transient."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MonthlyMosaic(Base):
    __tablename__ = "monthly_mosaics"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "month", name="uq_monthly_mosaics_profile_month"
        ),
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="ck_monthly_mosaics_month"),
        CheckConstraint(
            "source_track_count BETWEEN 1 AND 50", name="ck_monthly_mosaics_tracks"
        ),
        CheckConstraint("grid_width BETWEEN 1 AND 12", name="ck_monthly_mosaics_width"),
        CheckConstraint(
            "grid_height BETWEEN 1 AND 12", name="ck_monthly_mosaics_height"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    month: Mapped[date] = mapped_column()
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_track_count: Mapped[int] = mapped_column()
    album_ids: Mapped[list[str]] = mapped_column(JSONB)
    representative_track_ids: Mapped[dict[str, str]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    preset_key: Mapped[str] = mapped_column(String(20))
    grid_width: Mapped[int] = mapped_column()
    grid_height: Mapped[int] = mapped_column()
    tiles: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
