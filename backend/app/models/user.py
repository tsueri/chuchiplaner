from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.household import Household


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    household_id: Mapped[int | None] = mapped_column(
        ForeignKey("households.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    household: Mapped["Household | None"] = relationship(
        "Household", back_populates="members"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32)
    )
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC) + timedelta(days=7),
    )

    user: Mapped[User] = relationship(back_populates="sessions")
