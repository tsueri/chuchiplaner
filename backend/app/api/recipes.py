from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.schemas.recipe import (
    RecipeImportRequest,
    RecipeResponse,
    RecipeSaveRequest,
    ScrapedRecipeResponse,
)
from app.services.scraper import RecipeScraper

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/import", response_model=ScrapedRecipeResponse)
async def import_recipe(
    body: RecipeImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScrapedRecipeResponse:
    parsed = urlparse(body.url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL",
        )

    result = await db.execute(
        select(Recipe).where(
            Recipe.source_url == body.url,
            Recipe.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()

    scraped = RecipeScraper.scrape(body.url)
    if scraped is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract recipe from this URL",
        )

    return ScrapedRecipeResponse(
        title=scraped.title,
        ingredients=scraped.ingredients,
        instructions=scraped.instructions,
        image_url=scraped.image_url,
        servings=scraped.servings,
        source_url=scraped.source_url,
        source_domain=scraped.source_domain,
        existing_recipe_id=existing.id if existing else None,
    )


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    recipe = Recipe(
        title=body.title,
        instructions=body.instructions,
        image_url=body.image_url,
        source_url=body.source_url,
        source_domain=body.source_domain,
        servings=body.servings,
        created_by=current_user.id,
        household_id=current_user.household_id,
    )
    db.add(recipe)
    await db.flush()

    for item in body.ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=item.ingredient_id,
            quantity=item.quantity,
            unit=item.unit,
            order_index=item.order_index,
        )
        db.add(recipe_ingredient)

    await db.flush()

    refreshed = await db.execute(
        select(Recipe)
        .where(Recipe.id == recipe.id)
        .options(selectinload(Recipe.ingredients))
    )
    return refreshed.scalar_one()


@router.get("/check-url")
async def check_url(
    url: str = Query(min_length=1, max_length=2048),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | None]:
    result = await db.execute(
        select(Recipe).where(
            Recipe.source_url == url,
            Recipe.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    return {"existing_recipe_id": existing.id if existing else None}


@router.get("", response_model=list[RecipeResponse])
async def list_recipes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Recipe]:
    result = await db.execute(
        select(Recipe)
        .where(
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
        .options(selectinload(Recipe.ingredients))
        .order_by(Recipe.created_at.desc())
    )
    return list(result.scalars().all())
