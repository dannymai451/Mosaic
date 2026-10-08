"""Editable presentation of an immutable monthly listening snapshot."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArtworkRemix(Base):
    __tablename__ = "artwork_remixes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monthly_mosaic_id: Mapped[UUID] = mapped_column(
        ForeignKey("monthly_mosaics.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    style: Mapped[dict] = mapped_column(JSONB)
    layout: Mapped[dict] = mapped_column(JSONB)
    share_id: Mapped[UUID | None] = mapped_column(unique=True)
    has_background: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    background_version: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    background_image: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
