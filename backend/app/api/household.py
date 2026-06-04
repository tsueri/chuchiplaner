from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.grocery_list import GroceryList, GroceryListItem
from app.models.ingredient import IngredientAlias
from app.models.inventory import InventoryItem
from app.models.recipe import (
    Recipe,
    RecipeIngredient,
    RecipeNote,
    RecipeStep,
    RecipeTag,
    Tag,
)
from app.models.user import User
from app.models.week_plan import MealSlot, WeekPlan
from app.schemas.household import (
    HouseholdResponse,
    HouseholdUpdateRequest,
    MealSlotTemplateBulkUpdate,
    MealSlotTemplateResponse,
    MemberResponse,
)
from app.schemas.ingredient import IngredientAliasCreate, IngredientAliasResponse
from app.services.household import (
    get_household_by_id,
    get_household_with_members,
    get_meal_template,
    get_user_by_id,
    regenerate_invite_code,
    remove_member,
    update_meal_template,
)
from app.services.recipe_jsonld_exporter import RecipeJSONLDExporter
from app.services.week_plan import is_editable, sync_templates_to_plan

router = APIRouter(prefix="/household", tags=["household"])


def _to_member(user: User) -> MemberResponse:
    return MemberResponse(id=user.id, username=user.username, role=user.role)


@router.get("", response_model=HouseholdResponse)
async def get_household(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HouseholdResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    hwm = await get_household_with_members(db, current_user.household_id)
    if hwm is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return HouseholdResponse(
        id=hwm.id,
        name=hwm.name,
        slug=hwm.slug,
        invite_code=hwm.invite_code,
        default_size=hwm.default_size,
        default_public=hwm.default_public,
        members=[_to_member(m) for m in hwm.members],
    )


@router.put("", response_model=HouseholdResponse)
async def update_household(
    body: HouseholdUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HouseholdResponse:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update household settings",
        )
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    household = await get_household_by_id(db, current_user.household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    if body.name is not None:
        household.name = body.name
        if body.slug is None:
            from app.services.household import generate_slug
            household.slug = generate_slug(body.name)
    if body.slug is not None:
        household.slug = body.slug

    if body.default_size is not None:
        household.default_size = body.default_size

    if body.default_public is not None:
        household.default_public = body.default_public

    await db.flush()

    hwm = await get_household_with_members(db, household.id)
    assert hwm is not None
    return HouseholdResponse(
        id=hwm.id,
        name=hwm.name,
        slug=hwm.slug,
        invite_code=hwm.invite_code,
        default_size=hwm.default_size,
        default_public=hwm.default_public,
        members=[_to_member(m) for m in hwm.members],
    )


@router.post("/invite-code")
async def regenerate_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can regenerate invite codes",
        )
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    household = await get_household_by_id(db, current_user.household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    new_code = await regenerate_invite_code(db, household)
    return {"invite_code": new_code}


@router.delete("/members/{user_id}")
async def remove_household_member(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can remove members",
        )
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from the household",
        )

    target = await get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if target.household_id != current_user.household_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of your household",
        )

    await remove_member(db, target)
    return {"status": "ok"}


@router.get("/meal-template", response_model=list[MealSlotTemplateResponse])
async def get_meal_slot_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MealSlotTemplateResponse]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    slots = await get_meal_template(db, current_user.household_id)
    return [
        MealSlotTemplateResponse(
            id=s.id,
            household_id=s.household_id,
            day_of_week=s.day_of_week,
            meal_type=s.meal_type,
            active=s.active,
            default_portions=s.default_portions,
        )
        for s in slots
    ]


@router.put("/meal-template")
async def update_meal_slot_template(
    body: MealSlotTemplateBulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update meal templates",
        )
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    existing = await get_meal_template(db, current_user.household_id)
    updates_by_key = {
        (s.day_of_week, s.meal_type): s for s in body.slots
    }

    active_count = 0
    for es in existing:
        key = (es.day_of_week, es.meal_type)
        if key in updates_by_key:
            matching = updates_by_key[key]
            if matching.active is not None:
                if matching.active:
                    active_count += 1
            elif es.active:
                active_count += 1
        elif es.active:
            active_count += 1

    if active_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one meal slot must be active",
        )

    slots_data = [
        {
            "day_of_week": s.day_of_week,
            "meal_type": s.meal_type,
            "active": s.active,
            "default_portions": s.default_portions,
        }
        for s in body.slots
    ]
    await update_meal_template(db, current_user.household_id, slots_data)

    plans_result = await db.execute(
        select(WeekPlan)
        .where(WeekPlan.household_id == current_user.household_id)
        .options(selectinload(WeekPlan.slots))
    )
    for plan in plans_result.unique().scalars().all():
        if is_editable(plan):
            await sync_templates_to_plan(db, plan)

    return {"status": "ok"}


@router.post(
    "/aliases",
    response_model=IngredientAliasResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_alias(
    body: IngredientAliasCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IngredientAlias:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    alias = IngredientAlias(
        household_id=current_user.household_id,
        alias_name=body.alias_name,
        ingredient_id=body.ingredient_id,
    )
    db.add(alias)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Der Alias '{body.alias_name}' existiert bereits "
                "in diesem Haushalt."
            ),
        )
    return alias


@router.get("/aliases", response_model=list[IngredientAliasResponse])
async def list_aliases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IngredientAlias]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    result = await db.execute(
        select(IngredientAlias).where(
            IngredientAlias.household_id == current_user.household_id
        )
    )
    return list(result.scalars().all())


@router.get("/export")
async def export_household_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    hid = current_user.household_id

    hwm = await get_household_with_members(db, hid)
    if hwm is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    meal_template = await get_meal_template(db, hid)

    recipes_result = await db.execute(
        select(Recipe)
        .where(Recipe.household_id == hid)
        .where(Recipe.deleted_at.is_(None))
        .options(
            selectinload(Recipe.ingredients).joinedload(
                RecipeIngredient.ingredient
            ),
            selectinload(Recipe.steps),
            selectinload(Recipe.tags).joinedload(RecipeTag.tag),
        )
    )
    recipes = recipes_result.unique().scalars().all()
    recipe_ids = [r.id for r in recipes]

    ingredients_by_recipe: dict[int, list[dict[str, object]]] = {}
    steps_by_recipe: dict[int, list[dict[str, object]]] = {}
    tags_by_recipe: dict[int, list[dict[str, object]]] = {}
    notes_by_recipe: dict[int, list[dict[str, object]]] = {}
    if recipe_ids:
        ri_result = await db.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id.in_(recipe_ids)
            )
        )
        for ri in ri_result.scalars():
            ingredients_by_recipe.setdefault(ri.recipe_id, []).append({
                "id": ri.id, "ingredient_id": ri.ingredient_id,
                "quantity": ri.quantity, "unit": ri.unit,
                "order_index": ri.order_index,
            })

        rs_result = await db.execute(
            select(RecipeStep).where(RecipeStep.recipe_id.in_(recipe_ids))
        )
        for rs in rs_result.scalars():
            steps_by_recipe.setdefault(rs.recipe_id, []).append({
                "id": rs.id, "position": rs.position,
                "text": rs.text, "name": rs.name,
            })

        rt_result = await db.execute(
            select(RecipeTag, Tag)
            .join(Tag, RecipeTag.tag_id == Tag.id)
            .where(RecipeTag.recipe_id.in_(recipe_ids))
        )
        for rt, tag in rt_result:
            tags_by_recipe.setdefault(rt.recipe_id, []).append({
                "id": tag.id, "name": tag.name, "group": tag.group,
            })

        rn_result = await db.execute(
            select(RecipeNote).where(RecipeNote.recipe_id.in_(recipe_ids))
        )
        for rn in rn_result.scalars():
            notes_by_recipe.setdefault(rn.recipe_id, []).append({
                "id": rn.id, "user_id": rn.user_id,
                "text": rn.text, "visibility": rn.visibility,
                "created_at": rn.created_at.isoformat() if rn.created_at else None,
            })

    week_plans_result = await db.execute(
        select(WeekPlan).where(WeekPlan.household_id == hid)
    )
    week_plans = week_plans_result.scalars().all()
    wp_ids = [wp.id for wp in week_plans]

    slots_by_plan: dict[int, list[dict[str, object]]] = {}
    if wp_ids:
        slots_result = await db.execute(
            select(MealSlot).where(MealSlot.week_plan_id.in_(wp_ids))
        )
        for slot in slots_result.scalars():
            slots_by_plan.setdefault(slot.week_plan_id, []).append({
                "id": slot.id, "meal_type": slot.meal_type,
                "day_of_week": slot.day_of_week, "active": slot.active,
                "recipe_id": slot.recipe_id, "portions": slot.portions,
                "dietary_filter_tag_id": slot.dietary_filter_tag_id,
                "cooked": slot.cooked,
            })

    inventory_result = await db.execute(
        select(InventoryItem).where(InventoryItem.household_id == hid)
    )
    inventory_items = inventory_result.scalars().all()

    grocery_lists_result = await db.execute(
        select(GroceryList).where(GroceryList.household_id == hid)
    )
    grocery_lists = grocery_lists_result.scalars().all()
    gl_ids = [gl.id for gl in grocery_lists]

    items_by_list: dict[int, list[dict[str, object]]] = {}
    if gl_ids:
        gli_result = await db.execute(
            select(GroceryListItem).where(
                GroceryListItem.grocery_list_id.in_(gl_ids)
            )
        )
        for gli in gli_result.scalars():
            items_by_list.setdefault(gli.grocery_list_id, []).append({
                "id": gli.id, "ingredient_id": gli.ingredient_id,
                "name": gli.name, "quantity": gli.quantity,
                "unit": gli.unit, "checked": gli.checked,
                "recipe_breakdown": gli.recipe_breakdown,
            })

    aliases_result = await db.execute(
        select(IngredientAlias).where(IngredientAlias.household_id == hid)
    )
    aliases = aliases_result.scalars().all()

    import json
    from datetime import date, datetime

    def _serializer(obj: object) -> str:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    data = {
        "household": {
            "id": hwm.id, "name": hwm.name, "slug": hwm.slug,
            "default_size": hwm.default_size,
            "default_public": hwm.default_public,
        },
        "members": [
            {"id": m.id, "username": m.username, "role": m.role}
            for m in hwm.members
        ],
        "meal_template": [
            {"day_of_week": mt.day_of_week, "meal_type": mt.meal_type,
             "active": mt.active, "default_portions": mt.default_portions}
            for mt in meal_template
        ],
        "recipes": [
            {
                "id": r.id, "title": r.title, "description": r.description,
                "image_url": r.image_url, "source_url": r.source_url,
                "source_domain": r.source_domain, "servings": r.servings,
                "prep_time_minutes": r.prep_time_minutes,
                "cook_time_minutes": r.cook_time_minutes,
                "total_time_minutes": r.total_time_minutes,
                "perform_time_minutes": r.perform_time_minutes,
                "nutrition": r.nutrition,
                "aggregate_rating": r.aggregate_rating,
                "keywords": r.keywords,
                "author": r.author,
                "date_published": r.date_published.isoformat()
                    if r.date_published else None,
                "created_at": r.created_at,
                "ingredients": ingredients_by_recipe.get(r.id, []),
                "steps": steps_by_recipe.get(r.id, []),
                "tags": tags_by_recipe.get(r.id, []),
                "notes": notes_by_recipe.get(r.id, []),
            }
            for r in recipes
        ],
        "recipes_as_jsonld": {
            "@context": "https://schema.org",
            "@graph": [
                RecipeJSONLDExporter.to_jsonld(r) for r in recipes
            ],
        },
        "week_plans": [
            {
                "id": wp.id, "year": wp.year, "iso_week": wp.iso_week,
                "is_public": wp.is_public, "created_at": wp.created_at,
                "slots": slots_by_plan.get(wp.id, []),
            }
            for wp in week_plans
        ],
        "inventory": [
            {
                "id": ii.id, "ingredient_id": ii.ingredient_id,
                "quantity": ii.quantity, "unit": ii.unit,
                "expiry_date": ii.expiry_date,
                "category": ii.category,
                "source_recipe_id": ii.source_recipe_id,
                "source_week_plan_id": ii.source_week_plan_id,
            }
            for ii in inventory_items
        ],
        "grocery_lists": [
            {
                "id": gl.id, "week_plan_id": gl.week_plan_id,
                "completed_at": gl.completed_at,
                "created_at": gl.created_at,
                "items": items_by_list.get(gl.id, []),
            }
            for gl in grocery_lists
        ],
        "aliases": [
            {"id": a.id, "alias_name": a.alias_name,
             "ingredient_id": a.ingredient_id}
            for a in aliases
        ],
    }

    json_bytes = json.dumps(
        data, default=_serializer, ensure_ascii=False
    ).encode("utf-8")

    from datetime import datetime as dt
    today = dt.now().strftime("%Y-%m-%d")
    filename = f"chuchiplaner-export-{hwm.slug}-{today}.json"

    return StreamingResponse(
        content=iter([json_bytes]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
