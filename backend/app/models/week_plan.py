from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WeekPlan(Base):
    __tablename__ = "week_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    iso_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    slots: Mapped[list["MealSlot"]] = relationship(
        back_populates="week_plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "household_id", "year", "iso_week", name="uq_week_plan"
        ),
    )


class MealSlot(Base):
    __tablename__ = "meal_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_plan_id: Mapped[int] = mapped_column(
        ForeignKey("week_plans.id"), nullable=False
    )
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(default=True)
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id"), nullable=True
    )
    portions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dietary_filter_tag_id: Mapped[int | None] = mapped_column(
        ForeignKey("tags.id"), nullable=True
    )
    cooked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    week_plan: Mapped["WeekPlan"] = relationship(back_populates="slots")

    __table_args__ = (
        UniqueConstraint(
            "week_plan_id", "day_of_week", "meal_type", name="uq_meal_slot"
        ),
    )
