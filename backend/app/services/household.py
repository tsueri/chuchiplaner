from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household import Household as HouseholdModel
from app.models.household import MealSlotTemplate

if TYPE_CHECKING:
    from app.models.user import User


MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert"]


def generate_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def generate_invite_code() -> str:
    """Generate a cryptographically random invite code.

    Must be unguessable from a public plan URL.
    Returns 32 hex characters (128 bits of entropy).
    """
    return secrets.token_hex(16)


async def create_household(
    db: AsyncSession, name: str
) -> HouseholdModel:
    slug = generate_slug(name)
    household = HouseholdModel(
        name=name, slug=slug, invite_code=generate_invite_code()
    )
    db.add(household)
    await db.flush()

    for day in range(7):
        for meal_type in MEAL_TYPES:
            slot = MealSlotTemplate(
                household_id=household.id,
                day_of_week=day,
                meal_type=meal_type,
                active=True,
                default_portions=household.default_size,
            )
            db.add(slot)
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
    default_size: int
    default_public: bool
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
        default_size=household.default_size,
        default_public=household.default_public,
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


async def get_meal_template(
    db: AsyncSession, household_id: int
) -> list[MealSlotTemplate]:
    result = await db.execute(
        select(MealSlotTemplate)
        .where(MealSlotTemplate.household_id == household_id)
        .order_by(MealSlotTemplate.day_of_week, MealSlotTemplate.meal_type)
    )
    return list(result.scalars().all())


async def update_meal_template(
    db: AsyncSession,
    household_id: int,
    slots_data: list[dict[str, Any]],
) -> list[MealSlotTemplate]:
    result = await db.execute(
        select(MealSlotTemplate).where(
            MealSlotTemplate.household_id == household_id
        )
    )
    existing = {
        (s.day_of_week, s.meal_type): s
        for s in result.scalars().all()
    }

    updated: list[MealSlotTemplate] = []
    for slot_data in slots_data:
        day = slot_data["day_of_week"]
        meal = slot_data["meal_type"]
        slot = existing.get((int(day), str(meal)))
        if slot is None:
            continue
        if "active" in slot_data and slot_data["active"] is not None:
            slot.active = bool(slot_data["active"])
        if ("default_portions" in slot_data
                and slot_data["default_portions"] is not None):
            slot.default_portions = int(slot_data["default_portions"])
        updated.append(slot)

    await db.flush()
    return sorted(updated, key=lambda s: (s.day_of_week, s.meal_type))


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


async def update_household(
    db: AsyncSession,
    household: HouseholdModel,
    body: Any,
) -> HouseholdModel:
    if body.name is not None:
        household.name = body.name
        if body.slug is None:
            household.slug = generate_slug(body.name)
    if body.slug is not None:
        if not SLUG_RE.match(body.slug):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Ungültiges Slug-Format. Nur Kleinbuchstaben, Ziffern "
                    "und Bindestriche erlaubt (max. 64 Zeichen)."
                ),
            )
        household.slug = body.slug
    if getattr(body, "default_size", None) is not None:
        household.default_size = body.default_size
    if getattr(body, "default_public", None) is not None:
        household.default_public = body.default_public

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug bereits vergeben",
        )

    return household
