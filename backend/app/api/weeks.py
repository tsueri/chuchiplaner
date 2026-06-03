from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryItem
from app.models.recipe import Recipe
from app.models.user import User
from app.models.week_plan import MealSlot
from app.schemas.week_plan import (
    LeftoversRequest,
    MealSlotResponse,
    SlotBulkUpdate,
    VisibilityUpdateRequest,
    WeekPlanCreateRequest,
    WeekPlanListItem,
    WeekPlanResponse,
)
from app.services.week_plan import (
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
    slot_ids: dict[int, int | None],
) -> dict[int, str | None]:
    recipe_ids = {sid for sid in slot_ids.values() if sid is not None}
    if not recipe_ids:
        return {}
    result = await db.execute(
        select(Recipe).where(Recipe.id.in_(recipe_ids))
    )
    recipes = {r.id: r.title for r in result.scalars().all()}
    return {
        slot_id: recipes.get(rid) if rid is not None else None
        for slot_id, rid in slot_ids.items()
    }


def _slot_to_response(
    slot: MealSlot, recipe_title: str | None = None
) -> MealSlotResponse:
    return MealSlotResponse(
        id=slot.id,
        week_plan_id=slot.week_plan_id,
        meal_type=slot.meal_type,
        day_of_week=slot.day_of_week,
        active=slot.active,
        recipe_id=slot.recipe_id,
        recipe_title=recipe_title,
        portions=slot.portions,
        dietary_filter_tag_id=slot.dietary_filter_tag_id,
        cooked=slot.cooked,
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

    recipe_titles = await _resolve_recipe_titles(
        db, {s.id: s.recipe_id for s in plan.slots}
    )

    return WeekPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        year=plan.year,
        iso_week=plan.iso_week,
        is_public=plan.is_public,
        created_at=plan.created_at,
        slots=[
            _slot_to_response(s, recipe_titles.get(s.id)) for s in plan.slots
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

    recipe_titles = await _resolve_recipe_titles(
        db, {s.id: s.recipe_id for s in plan.slots}
    )

    return WeekPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        year=plan.year,
        iso_week=plan.iso_week,
        is_public=plan.is_public,
        created_at=plan.created_at,
        slots=[
            _slot_to_response(s, recipe_titles.get(s.id)) for s in plan.slots
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

    updates_data = [
        {
            "day_of_week": s.day_of_week,
            "meal_type": s.meal_type,
            "recipe_id": s.recipe_id,
            "portions": s.portions,
            "dietary_filter_tag_id": s.dietary_filter_tag_id,
        }
        for s in body.slots
    ]
    await update_slots(db, plan, updates_data)
    return {"status": "ok"}


@router.delete("/{year}/{iso_week}/slots/{slot_id}/recipe")
async def unplan_recipe(
    year: int,
    iso_week: int,
    slot_id: int,
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
            detail="This week is not editable",
        )

    slot = next((s for s in plan.slots if s.id == slot_id), None)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_SLOT_NOT_FOUND
        )

    slot.recipe_id = None
    slot.dietary_filter_tag_id = None
    await db.flush()
    return {"status": "ok"}


@router.get("/{year}/{iso_week}/reservations")
async def get_week_reservations(
    year: int,
    iso_week: int,
    current_user: User = Depends(get_current_user),
) -> dict[int, dict[str, float]]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return {}


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

    if slot.recipe_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot has no recipe planned",
        )

    if slot.cooked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot already cooked",
        )

    recipe_result = await db.execute(
        select(Recipe)
        .where(Recipe.id == slot.recipe_id)
        .options(selectinload(Recipe.ingredients))
    )
    recipe = recipe_result.scalar_one()

    scale = slot.portions / recipe.servings if recipe.servings > 0 else 1

    from app.services.unit_converter import UnitConverter

    deductions: list[dict[str, object]] = []
    for ri in recipe.ingredients:
        grams, ml, pieces = UnitConverter.normalize(ri.quantity, ri.unit)
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
            .order_by(
                InventoryItem.expiry_date.is_(None),
                InventoryItem.expiry_date.asc(),
            )
        )
        items = list(inv_result.scalars().all())

        remaining = needed
        for item in items:
            if remaining <= 0:
                break
            norm = UnitConverter.normalize(item.quantity, item.unit)
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

    slot.cooked = True
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

    if slot.recipe_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot has no recipe planned",
        )

    recipe_result = await db.execute(
        select(Recipe).where(Recipe.id == slot.recipe_id)
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
