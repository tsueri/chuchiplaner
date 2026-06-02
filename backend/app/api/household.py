from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import IngredientAlias
from app.models.user import User
from app.schemas.household import HouseholdResponse, MemberResponse
from app.schemas.ingredient import IngredientAliasCreate, IngredientAliasResponse
from app.services.household import (
    get_household_by_id,
    get_household_with_members,
    get_user_by_id,
    regenerate_invite_code,
    remove_member,
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
