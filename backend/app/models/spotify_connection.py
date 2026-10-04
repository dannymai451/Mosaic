from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class SpotifyConnection(Base):
    """Server-only authorization state; encrypt tokens before assigning them."""

    __tablename__ = "spotify_connections"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="spotify_connection")
