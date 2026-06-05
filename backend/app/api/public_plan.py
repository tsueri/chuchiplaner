from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.household import Household
from app.models.recipe import Recipe
from app.models.week_plan import MealSlot, WeekPlan
from app.schemas.public_plan import (
    PublicMealSlotResponse,
    PublicPlannedRecipeResponse,
    PublicRecipeResponse,
    PublicWeekPlanResponse,
)

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/plan/{slug}/{year}/{iso_week}", response_model=PublicWeekPlanResponse)
async def get_public_plan(
    slug: str,
    year: int,
    iso_week: int,
    db: AsyncSession = Depends(get_db),
) -> PublicWeekPlanResponse:
    household_result = await db.execute(
        select(Household).where(Household.slug == slug)
    )
    household = household_result.scalar_one_or_none()
    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )

    plan_result = await db.execute(
        select(WeekPlan)
        .where(
            WeekPlan.household_id == household.id,
            WeekPlan.year == year,
            WeekPlan.iso_week == iso_week,
        )
        .options(
            selectinload(WeekPlan.slots).selectinload(MealSlot.planned_recipes)
        )
    )
    plan = plan_result.unique().scalar_one_or_none()
    if plan is None or not plan.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )

    recipe_ids: set[int] = set()
    for s in plan.slots:
        for pr in s.planned_recipes:
            recipe_ids.add(pr.recipe_id)
    recipes_map: dict[int, dict[str, Any]] = {}
    if recipe_ids:
        recipes_result = await db.execute(
            select(Recipe).where(Recipe.id.in_(recipe_ids))
        )
        for r in recipes_result.scalars().all():
            recipes_map[r.id] = {
                "id": r.id,
                "title": r.title,
                "image_url": r.image_url,
                "source_url": r.source_url,
                "source_domain": r.source_domain,
                "servings": r.servings,
            }

    slots: list[PublicMealSlotResponse] = []
    for s in plan.slots:
        recipe_data = None
        cooked = False
        planned_recipes: list[PublicPlannedRecipeResponse] = []
        for pr in s.planned_recipes:
            pr_recipe = None
            if pr.recipe_id in recipes_map:
                pr_recipe = PublicRecipeResponse(**recipes_map[pr.recipe_id])
            else:
                pr_recipe = None
            planned_recipes.append(
                PublicPlannedRecipeResponse(
                    recipe=pr_recipe,
                    portions=pr.portions,
                    cooked=pr.cooked,
                )
            )

        if s.planned_recipes:
            pr = s.planned_recipes[0]
            if pr.recipe_id in recipes_map:
                recipe_data = PublicRecipeResponse(**recipes_map[pr.recipe_id])
            cooked = pr.cooked

        slots.append(
            PublicMealSlotResponse(
                id=s.id,
                meal_type=s.meal_type,
                day_of_week=s.day_of_week,
                active=s.active,
                recipe=recipe_data,
                portions=s.portions,
                cooked=cooked,
                planned_recipes=planned_recipes,
            )
        )

    return PublicWeekPlanResponse(
        household_name=household.name,
        household_slug=household.slug,
        year=plan.year,
        iso_week=plan.iso_week,
        slots=slots,
    )
