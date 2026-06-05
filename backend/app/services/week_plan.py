from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.household import MealSlotTemplate
from app.models.recipe import Recipe, RecipeIngredient
from app.models.week_plan import MealSlot, PlannedRecipe, WeekPlan

MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert"]
ZURICH_TZ = ZoneInfo("Europe/Zurich")


def get_current_iso_week() -> tuple[int, int]:
    now = datetime.now(ZURICH_TZ)
    iso = now.isocalendar()
    return (iso[0], iso[1])


def get_iso_week_for_date(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso[0], iso[1])


def iso_week_start_date(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 1)


def iso_week_end_date(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 7)


async def get_or_create_plan(
    db: AsyncSession,
    household_id: int,
    year: int,
    iso_week: int,
    copy_from_previous: bool = False,
) -> WeekPlan:
    result = await db.execute(
        select(WeekPlan)
        .where(
            WeekPlan.household_id == household_id,
            WeekPlan.year == year,
            WeekPlan.iso_week == iso_week,
        )
        .options(
            selectinload(WeekPlan.slots).selectinload(MealSlot.planned_recipes)
        )
    )
    existing = result.unique().scalar_one_or_none()
    if existing is not None:
        return existing

    from app.models.household import Household

    household_result = await db.execute(
        select(Household).where(Household.id == household_id)
    )
    household = household_result.scalar_one_or_none()
    is_public = household.default_public if household else False

    plan = WeekPlan(
        household_id=household_id,
        year=year,
        iso_week=iso_week,
        is_public=is_public,
    )
    db.add(plan)
    await db.flush()

    templates = await _get_meal_templates(db, household_id)

    prev_slot_plan_map: dict[tuple[int, str], dict[str, int]] = {}
    if copy_from_previous:
        prev_slot_plan_map = await _get_previous_week_recipe_map(
            db, household_id, year, iso_week
        )

    for day in range(7):
        for meal_type in MEAL_TYPES:
            template = templates.get((day, meal_type))
            active = template.active if template else True
            portions = (
                template.default_portions if template
                else household.default_size if household
                else 1
            )
            prev_data = prev_slot_plan_map.get(
                (day, meal_type)
            ) if copy_from_previous else None

            slot = MealSlot(
                week_plan_id=plan.id,
                meal_type=meal_type,
                day_of_week=day,
                active=active,
                portions=portions,
            )
            db.add(slot)
            await db.flush()

            if prev_data is not None:
                planned = PlannedRecipe(
                    meal_slot_id=slot.id,
                    recipe_id=prev_data["recipe_id"],
                    portions=prev_data["portions"],
                    order_index=0,
                )
                db.add(planned)

    await db.flush()
    result = await db.execute(
        select(WeekPlan)
        .where(WeekPlan.id == plan.id)
        .options(
            selectinload(WeekPlan.slots).selectinload(MealSlot.planned_recipes)
        )
    )
    return result.unique().scalar_one()


async def _get_meal_templates(
    db: AsyncSession,
    household_id: int,
) -> dict[tuple[int, str], MealSlotTemplate]:
    result = await db.execute(
        select(MealSlotTemplate).where(
            MealSlotTemplate.household_id == household_id
        )
    )
    return {
        (s.day_of_week, s.meal_type): s
        for s in result.scalars().all()
    }


async def _get_previous_week_recipe_map(
    db: AsyncSession,
    household_id: int,
    current_year: int,
    current_week: int,
) -> dict[tuple[int, str], dict[str, int]]:
    prev_week = current_week - 1
    prev_year = current_year
    if prev_week < 1:
        prev_year -= 1
        prev_week = date(prev_year, 12, 28).isocalendar()[1]

    result = await db.execute(
        select(WeekPlan)
        .where(
            WeekPlan.household_id == household_id,
            WeekPlan.year == prev_year,
            WeekPlan.iso_week == prev_week,
        )
    )
    prev_plan = result.scalar_one_or_none()
    if prev_plan is None:
        return {}

    slots_result = await db.execute(
        select(MealSlot)
        .where(
            MealSlot.week_plan_id == prev_plan.id,
            MealSlot.active.is_(True),
        )
        .options(selectinload(MealSlot.planned_recipes))
    )
    slots = list(slots_result.scalars().all())

    prev_map: dict[tuple[int, str], dict[str, int]] = {}
    for s in slots:
        pr_list = s.planned_recipes
        if pr_list:
            pr = pr_list[0]
            prev_map[(s.day_of_week, s.meal_type)] = {
                "recipe_id": pr.recipe_id,
                "portions": pr.portions,
            }
    return prev_map


async def get_plan(
    db: AsyncSession,
    household_id: int,
    year: int,
    iso_week: int,
) -> WeekPlan | None:
    result = await db.execute(
        select(WeekPlan)
        .where(
            WeekPlan.household_id == household_id,
            WeekPlan.year == year,
            WeekPlan.iso_week == iso_week,
        )
        .options(
            selectinload(WeekPlan.slots).selectinload(MealSlot.planned_recipes)
        )
    )
    return result.unique().scalar_one_or_none()


async def list_weeks(
    db: AsyncSession,
    household_id: int,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(WeekPlan)
        .where(WeekPlan.household_id == household_id)
        .options(
            selectinload(WeekPlan.slots).selectinload(MealSlot.planned_recipes)
        )
        .order_by(WeekPlan.year.desc(), WeekPlan.iso_week.desc())
    )
    plans = result.unique().scalars().all()

    weeks: list[dict[str, Any]] = []
    for plan in plans:
        active_slots = [s for s in plan.slots if s.active]
        planned = sum(1 for s in active_slots if s.planned_recipes)
        weeks.append({
            "id": plan.id,
            "household_id": plan.household_id,
            "year": plan.year,
            "iso_week": plan.iso_week,
            "is_public": plan.is_public,
            "created_at": plan.created_at,
            "planned_count": planned,
            "total_slots": len(active_slots),
        })
    return weeks


async def sync_templates_to_plan(
    db: AsyncSession,
    plan: WeekPlan,
) -> None:
    templates = await _get_meal_templates(db, plan.household_id)

    for slot in plan.slots:
        template = templates.get((slot.day_of_week, slot.meal_type))
        if template is None:
            continue

        has_recipe = bool(slot.planned_recipes)
        template_active = template.active

        if has_recipe:
            slot.active = True
        else:
            slot.active = template_active

        slot.portions = template.default_portions

    await db.flush()


async def update_slots(
    db: AsyncSession,
    plan: WeekPlan,
    updates: list[dict[str, Any]],
) -> list[MealSlot]:
    existing = {(s.day_of_week, s.meal_type): s for s in plan.slots}

    updated: list[MealSlot] = []
    for upd in updates:
        key = (int(upd["day_of_week"]), str(upd["meal_type"]))
        slot = existing.get(key)
        if slot is None:
            continue
        if "portions" in upd and upd["portions"] is not None:
            slot.portions = int(upd["portions"])
        if "dietary_filter_tag_id" in upd:
            slot.dietary_filter_tag_id = upd["dietary_filter_tag_id"]

        if "planned_recipes" in upd:
            incoming_prs: list[dict[str, Any]] = upd["planned_recipes"]
            existing_prs = {pr.recipe_id: pr for pr in slot.planned_recipes}
            incoming_ids = {pr["recipe_id"] for pr in incoming_prs}

            for rec_id, existing_pr in existing_prs.items():
                if rec_id not in incoming_ids:
                    slot.planned_recipes.remove(existing_pr)

            for idx, pr_data in enumerate(incoming_prs):
                rid = pr_data["recipe_id"]
                matched_pr: PlannedRecipe | None = existing_prs.get(rid)
                if matched_pr is not None:
                    if "portions" in pr_data:
                        matched_pr.portions = pr_data["portions"]
                    matched_pr.order_index = idx
                else:
                    new_pr = PlannedRecipe(
                        meal_slot_id=slot.id,
                        recipe_id=rid,
                        portions=pr_data.get("portions", slot.portions),
                        order_index=idx,
                    )
                    db.add(new_pr)

        updated.append(slot)

    await db.flush()
    return updated


async def get_past_weeks(
    db: AsyncSession,
    household_id: int,
) -> list[WeekPlan]:
    current_year, current_week = get_current_iso_week()
    result = await db.execute(
        select(WeekPlan)
        .where(
            WeekPlan.household_id == household_id,
        )
        .options(selectinload(WeekPlan.slots))
        .order_by(WeekPlan.year.desc(), WeekPlan.iso_week.desc())
    )
    all_plans = result.unique().scalars().all()

    past: list[WeekPlan] = []
    for plan in all_plans:
        if plan.year < current_year:
            past.append(plan)
        elif plan.year == current_year and plan.iso_week < current_week:
            past.append(plan)
    return past


def is_editable(plan: WeekPlan) -> bool:
    cy, cw = get_current_iso_week()
    if plan.year < cy:
        return False
    if plan.year == cy and plan.iso_week < cw:
        return False
    max_week = cw + 4
    if plan.year == cy and plan.iso_week > max_week:
        return False
    if plan.year > cy + 1:
        return False
    return True


async def compute_reservations(
    db: AsyncSession,
    plan_id: int,
) -> dict[int, dict[str, float]]:
    result = await db.execute(
        select(MealSlot)
        .where(MealSlot.week_plan_id == plan_id)
        .options(selectinload(MealSlot.planned_recipes))
    )
    slots = list(result.scalars().all())

    reservations: dict[int, dict[str, float]] = {}
    for slot in slots:
        for pr in slot.planned_recipes:
            if pr.cooked:
                continue
            if pr.recipe_id is None:
                continue
            recipe_result = await db.execute(
                select(Recipe).where(Recipe.id == pr.recipe_id).options(
                    selectinload(Recipe.ingredients).joinedload(
                        RecipeIngredient.ingredient
                    )
                )
            )
            recipe = recipe_result.scalar_one_or_none()
            if recipe is None:
                continue

            scale = pr.portions / recipe.servings if recipe.servings > 0 else 1
            from app.services.unit_converter import UnitConverter

            for ri in recipe.ingredients:
                grams, milliliters, pieces = UnitConverter.normalize(
                    ri.quantity, ri.unit, ingredient=ri.ingredient
                )
                if ri.ingredient_id not in reservations:
                    reservations[ri.ingredient_id] = {
                        "grams": 0.0, "milliliters": 0.0, "pieces": 0.0
                    }
                if grams:
                    reservations[ri.ingredient_id]["grams"] += grams * scale
                if milliliters:
                    reservations[ri.ingredient_id]["milliliters"] += (
                        milliliters * scale
                    )
                if pieces:
                    reservations[ri.ingredient_id]["pieces"] += pieces * scale

    return reservations
