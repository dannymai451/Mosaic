"""One saved design per profile; coordinates are independent of display pixels."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Mosaic(Base):
    __tablename__ = "mosaics"
    __table_args__ = (
        CheckConstraint("grid_width BETWEEN 1 AND 12", name="ck_mosaics_width"),
        CheckConstraint("grid_height BETWEEN 1 AND 12", name="ck_mosaics_height"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), unique=True
    )
    preset_key: Mapped[str] = mapped_column(String(20))
    grid_width: Mapped[int] = mapped_column()
    grid_height: Mapped[int] = mapped_column()
    tiles: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
