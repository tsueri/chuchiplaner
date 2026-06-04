from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.ingredient import Ingredient
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
    for field, value in update_data.items():
        setattr(ingredient, field, value)
    await db.flush()
    return ingredient
