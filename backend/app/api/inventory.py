from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryItem
from app.models.user import User
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryItemResponse])
async def list_inventory(
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InventoryItemResponse]:
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.household_id == current_user.household_id)
    )
    if category:
        stmt = stmt.where(InventoryItem.category == category)
    stmt = stmt.order_by(
        InventoryItem.expiry_date.is_(None),
        InventoryItem.expiry_date.asc(),
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    # Resolve ingredient names
    ingredient_ids = [item.ingredient_id for item in items]
    if ingredient_ids:
        ing_result = await db.execute(
            select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
        )
        ing_map = {ing.id: ing.name for ing in ing_result.scalars().all()}
    else:
        ing_map = {}

    response = []
    for item in items:
        resp = InventoryItemResponse.model_validate(item)
        resp.ingredient_name = ing_map.get(item.ingredient_id, "Unknown")
        response.append(resp)

    return response


@router.post(
    "", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_inventory_item(
    body: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryItemResponse:
    # Verify ingredient exists
    ing_result = await db.execute(
        select(Ingredient).where(Ingredient.id == body.ingredient_id)
    )
    ingredient = ing_result.scalar_one_or_none()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    # Merge with existing no-expiry item if applicable
    if body.expiry_date is None:
        existing_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.household_id == current_user.household_id,
                InventoryItem.ingredient_id == body.ingredient_id,
                InventoryItem.unit == body.unit,
                InventoryItem.category == body.category,
                InventoryItem.expiry_date.is_(None),
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            existing.quantity += body.quantity
            await db.flush()
            await db.refresh(existing)
            resp = InventoryItemResponse.model_validate(existing)
            resp.ingredient_name = ingredient.name
            return resp

    item = InventoryItem(
        household_id=current_user.household_id,
        ingredient_id=body.ingredient_id,
        quantity=body.quantity,
        unit=body.unit,
        expiry_date=body.expiry_date,
        category=body.category,
    )
    db.add(item)
    await db.flush()

    resp = InventoryItemResponse.model_validate(item)
    resp.ingredient_name = ingredient.name
    return resp


@router.put("/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int,
    body: InventoryItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryItemResponse:
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.household_id == current_user.household_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    if body.quantity is not None:
        item.quantity = body.quantity
    if body.unit is not None:
        item.unit = body.unit
    if body.expiry_date is not None:
        item.expiry_date = body.expiry_date
    if body.category is not None:
        item.category = body.category

    await db.flush()
    await db.refresh(item)

    ing_result = await db.execute(
        select(Ingredient).where(Ingredient.id == item.ingredient_id)
    )
    ingredient = ing_result.scalar_one()

    resp = InventoryItemResponse.model_validate(item)
    resp.ingredient_name = ingredient.name
    return resp


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.household_id == current_user.household_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    await db.delete(item)
    await db.flush()
