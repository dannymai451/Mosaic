from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("username", name="uq_profiles_username"),
        CheckConstraint(
            "visibility IN ('public', 'private')", name="ck_profiles_visibility"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    username: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    visibility: Mapped[str] = mapped_column(
        String(7), default="private", server_default="private"
    )
    theme: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSONB), default=dict, server_default=text("'{}'::jsonb")
    )

    user: Mapped[User] = relationship(back_populates="profile")
