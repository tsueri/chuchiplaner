from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryItem
from app.models.recipe import (
    Recipe,
    RecipeTag,
    Tag,
)
from app.models.user import User
from app.schemas.matching import MatchRequest, MatchResponse, ScoredRecipeResponse
from app.services.matching_engine import (
    IngredientAvailability,
    MatchingEngine,
    RecipeInfo,
    RecipeIngredientNeed,
    ScoredRecipe,
)
from app.services.unit_converter import UnitConverter

router = APIRouter(prefix="/match", tags=["matching"])

URGENCY_DAYS = 3


def _parse_reservations(
    reservations: dict[int, dict[str, float]] | None,
) -> dict[int, tuple[float, float, float]] | None:
    if reservations is None:
        return None
    result: dict[int, tuple[float, float, float]] = {}
    for ing_id, dims in reservations.items():
        result[ing_id] = (
            dims.get("grams", 0),
            dims.get("milliliters", 0),
            dims.get("pieces", 0),
        )
    return result


def _gather_inventory(
    items: list[InventoryItem],
    ingredient_names: dict[int, str],
    ingredients: dict[int, Any] | None = None,
) -> dict[int, IngredientAvailability]:
    today = date.today()
    by_ingredient: dict[int, list[tuple[float, float, float, date | None]]] = {}
    for item in items:
        ing = ingredients.get(item.ingredient_id) if ingredients else None
        normalized = UnitConverter.normalize(item.quantity, item.unit, ing)
        grams, milliliters, pieces = normalized
        by_ingredient.setdefault(item.ingredient_id, []).append(
            (grams or 0, milliliters or 0, pieces or 0, item.expiry_date)
        )

    inventory: dict[int, IngredientAvailability] = {}
    for ing_id, entries in by_ingredient.items():
        total_grams = sum(e[0] for e in entries)
        total_ml = sum(e[1] for e in entries)
        total_pcs = sum(e[2] for e in entries)
        has_expiring = any(
            e[3] is not None and (e[3] - today).days <= URGENCY_DAYS
            for e in entries
        )
        inventory[ing_id] = IngredientAvailability(
            ingredient_id=ing_id,
            name=ingredient_names.get(ing_id, f"Ingredient {ing_id}"),
            grams=total_grams,
            milliliters=total_ml,
            pieces=total_pcs,
            has_expiring=has_expiring,
        )
    return inventory


def _gather_recipes(
    recipes: list[Recipe],
    ingredient_names: dict[int, str],
    ingredients: dict[int, Any] | None = None,
) -> list[RecipeInfo]:
    result: list[RecipeInfo] = []
    for recipe in recipes:
        needs: list[RecipeIngredientNeed] = []
        for ri in recipe.ingredients:
            ing = ingredients.get(ri.ingredient_id) if ingredients else None
            normalized = UnitConverter.normalize(ri.quantity, ri.unit, ing)
            grams, milliliters, pieces = normalized
            name = ingredient_names.get(
                ri.ingredient_id, f"Ingredient {ri.ingredient_id}",
            )
            needs.append(RecipeIngredientNeed(
                ingredient_id=ri.ingredient_id,
                name=name,
                grams=grams or 0,
                milliliters=milliliters or 0,
                pieces=pieces or 0,
            ))
        tag_names = [rt.tag.name for rt in recipe.tags if rt.tag is not None]
        result.append(RecipeInfo(
            id=recipe.id,
            title=recipe.title,
            ingredients=needs,
            tag_names=tag_names,
        ))
    return result


def _to_response(scored: ScoredRecipe) -> ScoredRecipeResponse:
    return ScoredRecipeResponse(
        recipe_id=scored.recipe_id,
        title=scored.title,
        score=scored.score,
        matched_ingredients=scored.matched_ingredients,
        total_ingredients=scored.total_ingredients,
        missing_ingredients=scored.missing_ingredients,
        urgency_boost=scored.urgency_boost,
        expiring_ingredients=scored.expiring_ingredients,
    )


@router.post("", response_model=MatchResponse)
async def match_recipes(
    body: MatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    inventory_query = await db.execute(
        select(InventoryItem).where(
            InventoryItem.household_id == current_user.household_id,
        )
    )
    inventory_items = list(inventory_query.scalars().all())

    recipes_query = await db.execute(
        select(Recipe)
        .where(
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
        .options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
        )
    )
    recipes = list(recipes_query.unique().scalars().all())

    all_ingredient_ids: set[int] = {item.ingredient_id for item in inventory_items}
    for recipe in recipes:
        for ri in recipe.ingredients:
            all_ingredient_ids.add(ri.ingredient_id)

    ingredient_names: dict[int, str] = {}
    ingredients: dict[int, Ingredient] = {}
    if all_ingredient_ids:
        ing_result = await db.execute(
            select(Ingredient).where(Ingredient.id.in_(all_ingredient_ids))
        )
        for ing in ing_result.scalars().all():
            ingredient_names[ing.id] = ing.name
            ingredients[ing.id] = ing

    inventory = _gather_inventory(inventory_items, ingredient_names, ingredients)
    recipe_infos = _gather_recipes(recipes, ingredient_names, ingredients)

    dietary_tag_name: str | None = None
    if body.dietary_filter is not None:
        tag_result = await db.execute(
            select(Tag).where(Tag.id == body.dietary_filter)
        )
        tag = tag_result.scalar_one_or_none()
        if tag:
            dietary_tag_name = tag.name

    reservations = _parse_reservations(body.current_plan_reservations)

    suggestions = MatchingEngine.suggest(
        inventory=inventory,
        recipes=recipe_infos,
        mode=body.mode,
        ingredient_filter=body.ingredient_filter,
        dietary_filter=dietary_tag_name,
        current_plan_reservations=reservations,
    )

    return MatchResponse(
        suggestions=[_to_response(s) for s in suggestions],
    )
