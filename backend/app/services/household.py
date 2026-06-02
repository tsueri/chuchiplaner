from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household import Household as HouseholdModel

if TYPE_CHECKING:
    from app.models.user import User


def generate_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def generate_invite_code() -> str:
    return secrets.token_hex(8)


async def create_household(
    db: AsyncSession, name: str
) -> HouseholdModel:
    slug = generate_slug(name)
    household = HouseholdModel(
        name=name, slug=slug, invite_code=generate_invite_code()
    )
    db.add(household)
    await db.flush()
    return household


async def get_household_by_invite_code(
    db: AsyncSession, invite_code: str
) -> HouseholdModel | None:
    result = await db.execute(
        select(HouseholdModel).where(HouseholdModel.invite_code == invite_code)
    )
    return result.scalar_one_or_none()


@dataclass
class HouseholdWithMembers:
    id: int
    name: str
    slug: str
    invite_code: str
    members: list["User"]


async def get_household_by_id(
    db: AsyncSession, household_id: int
) -> HouseholdModel | None:
    result = await db.execute(
        select(HouseholdModel).where(HouseholdModel.id == household_id)
    )
    return result.scalar_one_or_none()


async def get_household_with_members(
    db: AsyncSession, household_id: int
) -> HouseholdWithMembers | None:
    from app.models.user import User

    result = await db.execute(
        select(HouseholdModel).where(HouseholdModel.id == household_id)
    )
    household = result.scalar_one_or_none()
    if household is None:
        return None

    members_result = await db.execute(
        select(User).where(User.household_id == household_id)
    )

    return HouseholdWithMembers(
        id=household.id,
        name=household.name,
        slug=household.slug,
        invite_code=household.invite_code,
        members=list(members_result.scalars().all()),
    )


async def regenerate_invite_code(
    db: AsyncSession, household: HouseholdModel
) -> str:
    new_code = generate_invite_code()
    household.invite_code = new_code
    await db.flush()
    return new_code


async def get_user_by_id(
    db: AsyncSession, user_id: int
) -> "User | None":
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def remove_member(
    db: AsyncSession, user: "User"
) -> None:
    user.household_id = None
    user.role = "member"
    await db.flush()
