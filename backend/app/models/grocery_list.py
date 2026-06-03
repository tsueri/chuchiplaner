from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GroceryList(Base):
    __tablename__ = "grocery_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(Integer, nullable=False)
    week_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("week_plans.id"), nullable=True
    )
    share_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["GroceryListItem"]] = relationship(
        back_populates="grocery_list", cascade="all, delete-orphan"
    )


class GroceryListItem(Base):
    __tablename__ = "grocery_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    grocery_list_id: Mapped[int] = mapped_column(
        ForeignKey("grocery_lists.id"), nullable=False
    )
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    recipe_breakdown: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )

    grocery_list: Mapped["GroceryList"] = relationship(back_populates="items")
