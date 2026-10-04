from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.session import Session
    from app.models.spotify_connection import SpotifyConnection


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("spotify_account_id", name="uq_users_spotify_account_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    spotify_account_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    spotify_connection: Mapped[SpotifyConnection | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    profile: Mapped[Profile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
