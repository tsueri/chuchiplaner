from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.deps import require_admin
from app.db.session import get_db
from app.models.grocery_list import GroceryListItem
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.inventory import InventoryItem
from app.models.recipe import RecipeIngredient
from app.models.user import User
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
)

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.post("", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
async def create_ingredient(
    body: IngredientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Ingredient:
    existing = await db.execute(
        select(Ingredient).where(Ingredient.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingredient already exists",
        )
    ingredient = Ingredient(name=body.name)
    db.add(ingredient)
    await db.flush()
    return ingredient


@router.get("", response_model=list[IngredientResponse])
async def list_ingredients(
    q: str = Query(default="", max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Ingredient]:
    if q:
        result = await db.execute(
            select(Ingredient).where(Ingredient.name.ilike(f"%{q}%"))
        )
    else:
        result = await db.execute(select(Ingredient))
    return list(result.scalars().all())


@router.get("/{ingredient_id}", response_model=IngredientResponse)
async def get_ingredient(
    ingredient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Ingredient:
    result = await db.execute(
        select(Ingredient).where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )
    return ingredient


@router.patch("/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: int,
    body: IngredientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Ingredient:
    result = await db.execute(
        select(Ingredient).where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )
    update_data = body.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing = await db.execute(
            select(Ingredient).where(
                Ingredient.name == update_data["name"],
                Ingredient.id != ingredient_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ingredient already exists",
            )

    for field, value in update_data.items():
        setattr(ingredient, field, value)
    await db.flush()
    return ingredient


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ingredient(
    ingredient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    result = await db.execute(
        select(Ingredient).where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    inventory_count = (
        await db.execute(
            select(func.count()).select_from(InventoryItem).where(
                InventoryItem.ingredient_id == ingredient_id
            )
        )
    ).scalar() or 0

    recipe_count = (
        await db.execute(
            select(func.count()).select_from(RecipeIngredient).where(
                RecipeIngredient.ingredient_id == ingredient_id
            )
        )
    ).scalar() or 0

    alias_count = (
        await db.execute(
            select(func.count()).select_from(IngredientAlias).where(
                IngredientAlias.ingredient_id == ingredient_id
            )
        )
    ).scalar() or 0

    grocery_count = (
        await db.execute(
            select(func.count()).select_from(GroceryListItem).where(
                GroceryListItem.ingredient_id == ingredient_id
            )
        )
    ).scalar() or 0

    if inventory_count or recipe_count or alias_count or grocery_count:
        parts = []
        if inventory_count:
            parts.append(f"{inventory_count} Inventar-Einträgen")
        if recipe_count:
            parts.append(f"{recipe_count} Rezept-Zutaten")
        if alias_count:
            parts.append(f"{alias_count} Aliassen")
        if grocery_count:
            parts.append(f"{grocery_count} Einkaufslisten-Einträgen")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zutat wird verwendet von " + ", ".join(parts),
        )

    await db.delete(ingredient)
    await db.flush()
