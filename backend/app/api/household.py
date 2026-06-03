from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.household import MealSlotTemplate
from app.models.ingredient import IngredientAlias
from app.models.user import User
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
        from app.services.household import generate_slug
        household.name = body.name
        household.slug = generate_slug(body.name)

    if body.default_size is not None:
        household.default_size = body.default_size
        result = await db.execute(
            select(MealSlotTemplate).where(
                MealSlotTemplate.household_id == household.id
            )
        )
        for slot in result.scalars().all():
            slot.default_portions = body.default_size

    await db.flush()

    hwm = await get_household_with_members(db, household.id)
    assert hwm is not None
    return HouseholdResponse(
        id=hwm.id,
        name=hwm.name,
        slug=hwm.slug,
        invite_code=hwm.invite_code,
        default_size=hwm.default_size,
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
    await db.flush()
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
