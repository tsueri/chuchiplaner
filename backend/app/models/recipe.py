from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_domain: Mapped[str | None] = mapped_column(String(255))
    servings: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    household_id: Mapped[int] = mapped_column(nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    tags: Mapped[list["RecipeTag"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["RecipeFavorite"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    notes: Mapped[list["RecipeNote"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id"), nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    order_index: Mapped[int] = mapped_column(default=0)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")


class RecipeTag(Base):
    __tablename__ = "recipe_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id"), nullable=False
    )

    recipe: Mapped["Recipe"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship()

    def __repr__(self) -> str:
        return f"<RecipeTag recipe_id={self.recipe_id} tag_id={self.tag_id}>"


class RecipeFavorite(Base):
    __tablename__ = "recipe_favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="favorites")
    recipe: Mapped["Recipe"] = relationship()


class RecipeNote(Base):
    __tablename__ = "recipe_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, default="private"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="notes")
    recipe: Mapped["Recipe"] = relationship()


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    group: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ingredient"
    )
    household_id: Mapped[int | None] = mapped_column(nullable=True)
