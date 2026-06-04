from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.grocery_list import GroceryList, GroceryListItem
from app.models.household import Household
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryItem
from app.models.recipe import Recipe
from app.models.week_plan import MealSlot, WeekPlan
from app.services.unit_converter import UnitConverter


async def get_or_generate_list(
    db: AsyncSession,
    household_id: int,
    week_plan_id: int | None,
) -> GroceryList:
    if week_plan_id is not None:
        plan = await _get_week_plan(db, household_id, week_plan_id)
        if plan is None:
            return await _create_empty_list(db, household_id, week_plan_id=None)
    else:
        plan = None

    result = await db.execute(
        select(GroceryList)
        .where(
            GroceryList.household_id == household_id,
            GroceryList.week_plan_id == week_plan_id,
            GroceryList.completed_at.is_(None),
        )
        .order_by(GroceryList.created_at.desc())
        .limit(1)
        .options(selectinload(GroceryList.items))
    )
    existing = result.scalars().first()
    if existing is not None:
        if plan is None:
            return existing
        if existing.generated_at is None:
            planned = [s for s in plan.slots if s.active and s.recipe_id is not None]
            if planned:
                return await regenerate_list(db, household_id, existing)
        return existing

    if plan is not None:
        return await generate_list(db, household_id, plan)
    return await _create_empty_list(db, household_id, week_plan_id)


async def _compute_needs(
    db: AsyncSession,
    planned_slots: list[MealSlot],
) -> tuple[dict[int, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    ingredient_needs: dict[int, dict[str, Any]] = {}
    recipe_refs: dict[int, list[dict[str, Any]]] = {}

    for slot in planned_slots:
        recipe_result = await db.execute(
            select(Recipe)
            .where(Recipe.id == slot.recipe_id)
            .options(selectinload(Recipe.ingredients))
        )
        recipe = recipe_result.scalar_one_or_none()
        if recipe is None:
            continue

        scale = slot.portions / recipe.servings if recipe.servings > 0 else 1

        for ri in recipe.ingredients:
            grams, ml, pieces = UnitConverter.normalize(ri.quantity, ri.unit)
            needed = grams or ml or pieces or 0
            if needed == 0:
                continue
            needed *= scale

            dim = "g" if grams else ("ml" if ml else "Stück")

            if ri.ingredient_id not in ingredient_needs:
                ingredient_needs[ri.ingredient_id] = {
                    "total": 0.0,
                    "unit": dim,
                }
                recipe_refs[ri.ingredient_id] = []

            ingredient_needs[ri.ingredient_id]["total"] += needed
            recipe_refs[ri.ingredient_id].append({
                "recipe_id": recipe.id,
                "recipe_title": recipe.title,
                "quantity": round(needed, 2),
                "unit": dim,
            })

    return ingredient_needs, recipe_refs


async def _populate_items(
    db: AsyncSession,
    glist: GroceryList,
    household_id: int,
    ingredient_needs: dict[int, dict[str, Any]],
    recipe_refs: dict[int, list[dict[str, Any]]],
) -> None:
    inventory = await _get_inventory_sums(db, household_id)

    for ingredient_id, need_data in ingredient_needs.items():
        inv_qty = inventory.get(ingredient_id, 0.0)
        net_quantity = round(need_data["total"] - inv_qty, 2)

        if net_quantity <= 0:
            continue

        ing_result = await db.execute(
            select(Ingredient.name).where(Ingredient.id == ingredient_id)
        )
        ing_name = ing_result.scalar_one()

        item = GroceryListItem(
            grocery_list_id=glist.id,
            ingredient_id=ingredient_id,
            name=ing_name,
            quantity=net_quantity,
            unit=need_data["unit"],
            recipe_breakdown=recipe_refs.get(ingredient_id),
        )
        db.add(item)


async def generate_list(
    db: AsyncSession,
    household_id: int,
    plan: WeekPlan,
) -> GroceryList:
    planned_slots = [
        s for s in plan.slots
        if s.active and s.recipe_id is not None
    ]

    ingredient_needs, recipe_refs = await _compute_needs(db, planned_slots)

    if not ingredient_needs:
        return await _create_empty_list(db, household_id, plan.id)

    glist = GroceryList(
        household_id=household_id,
        week_plan_id=plan.id,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(glist)
    await db.flush()

    await _populate_items(db, glist, household_id, ingredient_needs, recipe_refs)
    await db.flush()
    return glist


async def _get_week_plan(
    db: AsyncSession,
    household_id: int,
    plan_id: int,
) -> WeekPlan | None:
    result = await db.execute(
        select(WeekPlan)
        .where(
            WeekPlan.id == plan_id,
            WeekPlan.household_id == household_id,
        )
        .options(selectinload(WeekPlan.slots))
    )
    return result.scalar_one_or_none()


async def _get_inventory_sums(
    db: AsyncSession,
    household_id: int,
) -> dict[int, float]:
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.household_id == household_id,
            InventoryItem.category == "raw",
        )
    )
    items = list(result.scalars().all())

    sums: dict[int, float] = {}
    for item in items:
        grams, ml, pieces = UnitConverter.normalize(item.quantity, item.unit)
        available = grams or ml or pieces or 0

        if available == 0:
            continue

        if item.ingredient_id not in sums:
            sums[item.ingredient_id] = 0.0
        sums[item.ingredient_id] += available

    return sums


async def _create_empty_list(
    db: AsyncSession,
    household_id: int,
    week_plan_id: int | None,
) -> GroceryList:
    glist = GroceryList(
        household_id=household_id,
        week_plan_id=week_plan_id,
    )
    db.add(glist)
    await db.flush()
    return glist


async def regenerate_list(
    db: AsyncSession,
    household_id: int,
    glist: GroceryList,
) -> GroceryList:
    if glist.completed_at is not None:
        return glist

    for item in list(glist.items):
        await db.delete(item)
    await db.flush()

    if glist.week_plan_id is not None:
        plan = await _get_week_plan(db, household_id, glist.week_plan_id)
        if plan is not None:
            planned_slots = [
                s for s in plan.slots
                if s.active and s.recipe_id is not None
            ]
            ingredient_needs, recipe_refs = await _compute_needs(
                db, planned_slots
            )
            await _populate_items(
                db, glist, household_id, ingredient_needs, recipe_refs
            )
            glist.generated_at = datetime.now(timezone.utc)
            await db.flush()

    return glist


async def complete_list(
    db: AsyncSession,
    household_id: int,
    glist: GroceryList,
) -> dict[str, Any]:
    if glist.completed_at is not None:
        return {"transferred_count": 0}

    checked = [item for item in glist.items if item.checked]
    transferred = 0

    for item in checked:
        if item.ingredient_id is None:
            continue

        inv_result = await db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.household_id == household_id,
                InventoryItem.ingredient_id == item.ingredient_id,
                InventoryItem.category == "raw",
            )
            .order_by(
                InventoryItem.expiry_date.is_(None),
                InventoryItem.expiry_date.asc(),
            )
        )
        existing_inv = list(inv_result.scalars().all())

        if existing_inv:
            inv_item = existing_inv[0]
            inv_item.quantity += item.quantity
            transferred += 1
        else:
            inv_item = InventoryItem(
                household_id=household_id,
                ingredient_id=item.ingredient_id,
                quantity=item.quantity,
                unit=item.unit,
                category="raw",
                source_week_plan_id=glist.week_plan_id,
            )
            db.add(inv_item)
            transferred += 1

    glist.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"transferred_count": transferred}


async def get_share_data(
    db: AsyncSession,
    glist: GroceryList,
) -> dict[str, Any]:
    if glist.share_token is None:
        glist.share_token = secrets.token_urlsafe(32)[:64]
        await db.flush()

    household_result = await db.execute(
        select(Household.name).where(Household.id == glist.household_id)
    )
    household_name = household_result.scalar_one_or_none() or ""

    week_label = ""
    if glist.week_plan_id is not None:
        plan_result = await db.execute(
            select(WeekPlan).where(WeekPlan.id == glist.week_plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        if plan is not None:
            start = date.fromisocalendar(plan.year, plan.iso_week, 1)
            end = date.fromisocalendar(plan.year, plan.iso_week, 7)
            week_label = (
                f"KW {plan.iso_week}, "
                f"{start.day}.–{end.day}.{end.month}"
            )

    return {
        "id": glist.id,
        "household_name": str(household_name),
        "week_label": week_label,
        "items": glist.items,
        "completed_at": glist.completed_at,
    }
