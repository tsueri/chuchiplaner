from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryItem
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.models.week_plan import MealSlot
from app.schemas.week_plan import (
    CookSlotRequest,
    LeftoversRequest,
    MealSlotResponse,
    PlannedRecipeResponse,
    SlotBulkUpdate,
    VisibilityUpdateRequest,
    WeekPlanCreateRequest,
    WeekPlanListItem,
    WeekPlanResponse,
)
from app.services.week_plan import (
    compute_reservations,
    get_or_create_plan,
    get_plan,
    is_editable,
    list_weeks,
    update_slots,
)

router = APIRouter(prefix="/weeks", tags=["weeks"])

_NOT_FOUND = "Week plan not found"
_SLOT_NOT_FOUND = "Slot not found"


async def _resolve_recipe_titles(
    db: AsyncSession,
    recipe_ids: set[int],
) -> dict[int, str]:
    if not recipe_ids:
        return {}
    result = await db.execute(
        select(Recipe).where(Recipe.id.in_(recipe_ids))
    )
    return {r.id: r.title for r in result.scalars().all()}


def _slot_to_response(
    slot: MealSlot, recipe_titles: dict[int, str]
) -> MealSlotResponse:
    planned_recipes = [
        PlannedRecipeResponse(
            id=pr.id,
            recipe_id=pr.recipe_id,
            recipe_title=recipe_titles.get(pr.recipe_id),
            portions=pr.portions,
            cooked=pr.cooked,
        )
        for pr in slot.planned_recipes
    ]
    return MealSlotResponse(
        id=slot.id,
        week_plan_id=slot.week_plan_id,
        meal_type=slot.meal_type,
        day_of_week=slot.day_of_week,
        active=slot.active,
        planned_recipes=planned_recipes,
        portions=slot.portions,
        dietary_filter_tag_id=slot.dietary_filter_tag_id,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
    )


@router.get("", response_model=list[WeekPlanListItem])
async def list_weeks_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WeekPlanListItem]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    weeks = await list_weeks(db, current_user.household_id)
    return [WeekPlanListItem(**w) for w in weeks]


@router.post("", response_model=WeekPlanResponse)
async def create_week(
    body: WeekPlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeekPlanResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = await get_or_create_plan(
        db,
        current_user.household_id,
        body.year,
        body.iso_week,
        body.copy_from_previous,
    )

    all_recipe_ids: set[int] = set()
    for s in plan.slots:
        for pr in s.planned_recipes:
            all_recipe_ids.add(pr.recipe_id)
    recipe_titles = await _resolve_recipe_titles(db, all_recipe_ids)

    return WeekPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        year=plan.year,
        iso_week=plan.iso_week,
        is_public=plan.is_public,
        created_at=plan.created_at,
        slots=[
            _slot_to_response(s, recipe_titles) for s in plan.slots
        ],
    )


@router.get("/{year}/{iso_week}", response_model=WeekPlanResponse)
async def get_week(
    year: int,
    iso_week: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeekPlanResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = await get_plan(db, current_user.household_id, year, iso_week)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)

    all_recipe_ids: set[int] = set()
    for s in plan.slots:
        for pr in s.planned_recipes:
            all_recipe_ids.add(pr.recipe_id)
    recipe_titles = await _resolve_recipe_titles(db, all_recipe_ids)

    return WeekPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        year=plan.year,
        iso_week=plan.iso_week,
        is_public=plan.is_public,
        created_at=plan.created_at,
        slots=[
            _slot_to_response(s, recipe_titles) for s in plan.slots
        ],
    )


@router.put("/{year}/{iso_week}/slots")
async def update_week_slots(
    year: int,
    iso_week: int,
    body: SlotBulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = await get_plan(db, current_user.household_id, year, iso_week)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)

    if not is_editable(plan):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This week is not editable (past or too far in the future)",
        )

    updates_data: list[dict[str, int | str | list[dict[str, int]]]] = []
    for s in body.slots:
        upd: dict[str, int | str | list[dict[str, int]]] = {
            "day_of_week": s.day_of_week,
            "meal_type": s.meal_type,
        }
        if s.model_fields_set and "planned_recipes" in s.model_fields_set:
            if s.planned_recipes:
                upd["planned_recipes"] = [
                    {"recipe_id": pr.recipe_id, "portions": pr.portions}
                    for pr in s.planned_recipes
                ]
            else:
                upd["planned_recipes"] = []
        elif s.recipe_id is not None:
            upd["planned_recipes"] = [
                {"recipe_id": s.recipe_id, "portions": s.portions or 1}
            ]
        if s.portions is not None:
            upd["portions"] = s.portions
        if s.dietary_filter_tag_id is not None:
            upd["dietary_filter_tag_id"] = s.dietary_filter_tag_id
        updates_data.append(upd)
    await update_slots(db, plan, updates_data)
    return {"status": "ok"}


@router.get("/{year}/{iso_week}/reservations")
async def get_week_reservations(
    year: int,
    iso_week: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[int, dict[str, float]]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = await get_plan(db, current_user.household_id, year, iso_week)
    if plan is None:
        return {}

    return await compute_reservations(db, plan.id)


@router.put("/{year}/{iso_week}/visibility")
async def update_week_visibility(
    year: int,
    iso_week: int,
    body: VisibilityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update visibility",
        )

    plan = await get_plan(db, current_user.household_id, year, iso_week)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)

    plan.is_public = body.is_public
    await db.flush()
    return {"is_public": plan.is_public}


@router.post("/{year}/{iso_week}/slots/{slot_id}/cook")
async def cook_slot(
    year: int,
    iso_week: int,
    slot_id: int,
    body: CookSlotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | bool | list[dict[str, object]]]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = await get_plan(db, current_user.household_id, year, iso_week)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)

    slot = next((s for s in plan.slots if s.id == slot_id), None)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_SLOT_NOT_FOUND
        )

    planned_recipe = next(
        (pr for pr in slot.planned_recipes if pr.id == body.planned_recipe_id), None
    )
    if planned_recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planned recipe not found in this slot",
        )

    if planned_recipe.cooked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planned recipe already cooked",
        )

    recipe_result = await db.execute(
        select(Recipe)
        .where(Recipe.id == planned_recipe.recipe_id)
        .options(
            selectinload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient)
        )
    )
    recipe = recipe_result.scalar_one()

    scale = planned_recipe.portions / recipe.servings if recipe.servings > 0 else 1

    from app.services.unit_converter import UnitConverter

    deductions: list[dict[str, object]] = []
    for ri in recipe.ingredients:
        grams, ml, pieces = UnitConverter.normalize(
            ri.quantity, ri.unit, ingredient=ri.ingredient
        )
        needed = grams or ml or pieces
        if needed is None or needed == 0:
            continue
        needed *= scale
        dim = "g" if grams else ("ml" if ml else "Stück")
        actual_deducted = 0.0

        inv_result = await db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.household_id == current_user.household_id,
                InventoryItem.ingredient_id == ri.ingredient_id,
                InventoryItem.category == "raw",
            )
            .options(joinedload(InventoryItem.ingredient))
            .order_by(
                InventoryItem.expiry_date.is_(None),
                InventoryItem.expiry_date.asc(),
            )
        )
        items = list(inv_result.unique().scalars().all())

        remaining = needed
        for item in items:
            if remaining <= 0:
                break
            norm = UnitConverter.normalize(
                item.quantity, item.unit, ingredient=item.ingredient
            )
            available = norm[0] or norm[1] or norm[2] or 0
            deduct = min(available, remaining)
            if deduct <= 0:
                continue

            new_qty = round(item.quantity - (deduct / (item.quantity / available)), 3)
            if new_qty <= 0.001:
                await db.delete(item)
            else:
                item.quantity = new_qty

            remaining -= deduct
            actual_deducted += deduct

        if actual_deducted > 0:
            ing_result = await db.execute(
                select(Ingredient.name).where(Ingredient.id == ri.ingredient_id)
            )
            name = ing_result.scalar_one()
            deductions.append({
                "ingredient_id": ri.ingredient_id,
                "ingredient_name": name,
                "deducted": round(actual_deducted, 3),
                "unit": dim,
            })

    planned_recipe.cooked = True
    await db.flush()

    return {"cooked": True, "deductions": deductions}


@router.post("/{year}/{iso_week}/slots/{slot_id}/leftovers")
async def create_leftovers(
    year: int,
    iso_week: int,
    slot_id: int,
    body: LeftoversRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = await get_plan(db, current_user.household_id, year, iso_week)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)

    slot = next((s for s in plan.slots if s.id == slot_id), None)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_SLOT_NOT_FOUND
        )

    planned_recipe = next(
        (pr for pr in slot.planned_recipes if pr.id == body.planned_recipe_id), None
    )
    if planned_recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planned recipe not found in this slot",
        )

    recipe_result = await db.execute(
        select(Recipe).where(Recipe.id == planned_recipe.recipe_id)
    )
    recipe = recipe_result.scalar_one()

    title = f"{recipe.title} (Reste)"
    existing_ing = await db.execute(
        select(Ingredient).where(Ingredient.name == title)
    )
    leftover_ingredient = existing_ing.scalar_one_or_none()
    if leftover_ingredient is None:
        leftover_ingredient = Ingredient(name=title)
        db.add(leftover_ingredient)
        await db.flush()

    item = InventoryItem(
        household_id=current_user.household_id,
        ingredient_id=leftover_ingredient.id,
        quantity=float(body.portions_count),
        unit="Stück",
        category="cooked",
        source_recipe_id=recipe.id,
        source_week_plan_id=plan.id,
    )
    db.add(item)
    await db.flush()

    return {
        "id": item.id,
        "ingredient_name": title,
        "quantity": float(body.portions_count),
        "unit": "Stück",
        "category": "cooked",
        "source_recipe_id": recipe.id,
    }
