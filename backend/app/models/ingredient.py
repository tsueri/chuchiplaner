from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    aliases: Mapped[list["IngredientAlias"]] = relationship(back_populates="ingredient")


class IngredientAlias(Base):
    __tablename__ = "ingredient_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(nullable=False)
    alias_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"), nullable=False
    )

    ingredient: Mapped[Ingredient] = relationship(back_populates="aliases")

    __table_args__ = (
        Index(
            "uq_ingredient_aliases_household_lower_alias",
            "household_id",
            func.lower(alias_name),
            unique=True,
        ),
    )
