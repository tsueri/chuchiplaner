from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.grocery_list import GroceryList, GroceryListItem
from app.models.ingredient import Ingredient
from app.models.user import User
from app.schemas.grocery_list import (
    GroceryListItemCreate,
    GroceryListItemResponse,
    GroceryListItemUpdate,
    GroceryListResponse,
    GroceryListShareResponse,
)
from app.services.grocery_list import (
    complete_list,
    get_or_generate_list,
    get_share_data,
    regenerate_list,
)

router = APIRouter(prefix="/grocery-list", tags=["grocery-list"])

_NOT_FOUND = "Grocery list not found"
_NOT_OWNER = "Grocery list not found"


async def _resolve_ingredient_names(
    db: AsyncSession,
    items: list[GroceryListItem],
) -> list[GroceryListItemResponse]:
    ingredient_ids = {i.ingredient_id for i in items if i.ingredient_id is not None}
    ing_map: dict[int, str] = {}
    if ingredient_ids:
        result = await db.execute(
            select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
        )
        ing_map = {ing.id: ing.name for ing in result.scalars().all()}

    response = []
    for item in items:
        resp = GroceryListItemResponse.model_validate(item)
        if item.ingredient_id is not None:
            resp.name = ing_map.get(item.ingredient_id, item.name)
        response.append(resp)
    return response


async def _get_owned_list(
    db: AsyncSession,
    list_id: int,
    household_id: int,
) -> GroceryList:
    result = await db.execute(
        select(GroceryList)
        .where(GroceryList.id == list_id, GroceryList.household_id == household_id)
        .options(selectinload(GroceryList.items))
    )
    glist = result.scalar_one_or_none()
    if glist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND
        )
    return glist


@router.get("", response_model=GroceryListResponse)
async def get_grocery_list(
    week_plan_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryListResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    glist = await get_or_generate_list(
        db, current_user.household_id, week_plan_id
    )
    await db.refresh(glist, ["items"])

    items_resp = await _resolve_ingredient_names(db, glist.items)
    return GroceryListResponse(
        id=glist.id,
        household_id=glist.household_id,
        week_plan_id=glist.week_plan_id,
        share_token=glist.share_token,
        created_at=glist.created_at,
        completed_at=glist.completed_at,
        items=items_resp,
    )


@router.post("/generate", response_model=GroceryListResponse)
async def force_generate(
    week_plan_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryListResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    glist = await get_or_generate_list(
        db, current_user.household_id, week_plan_id
    )
    glist = await regenerate_list(db, current_user.household_id, glist)
    await db.refresh(glist, ["items"])

    items_resp = await _resolve_ingredient_names(db, glist.items)
    return GroceryListResponse(
        id=glist.id,
        household_id=glist.household_id,
        week_plan_id=glist.week_plan_id,
        share_token=glist.share_token,
        created_at=glist.created_at,
        completed_at=glist.completed_at,
        items=items_resp,
    )


@router.put("/items/{item_id}", response_model=GroceryListItemResponse)
async def update_item(
    item_id: int,
    body: GroceryListItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryListItemResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(
        select(GroceryListItem)
        .join(GroceryList)
        .where(
            GroceryListItem.id == item_id,
            GroceryList.household_id == current_user.household_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    if body.quantity is not None:
        item.quantity = body.quantity
    if body.unit is not None:
        item.unit = body.unit
    if body.checked is not None:
        item.checked = body.checked

    await db.flush()
    await db.refresh(item)

    return GroceryListItemResponse.model_validate(item)


@router.post(
    "/items",
    response_model=GroceryListItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_item(
    body: GroceryListItemCreate,
    list_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryListItemResponse:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    glist = await _get_owned_list(db, list_id, current_user.household_id)
    if glist.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="List is already completed",
        )

    item = GroceryListItem(
        grocery_list_id=list_id,
        ingredient_id=body.ingredient_id,
        name=body.name,
        quantity=body.quantity,
        unit=body.unit,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    return GroceryListItemResponse.model_validate(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(
        select(GroceryListItem)
        .join(GroceryList)
        .where(
            GroceryListItem.id == item_id,
            GroceryList.household_id == current_user.household_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    await db.delete(item)
    await db.flush()


@router.post("/complete")
async def complete_grocery_list(
    list_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    glist = await _get_owned_list(db, list_id, current_user.household_id)
    result = await complete_list(db, current_user.household_id, glist)
    return result


@router.get("/share/{token}", response_model=GroceryListShareResponse)
async def get_shared_list(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> GroceryListShareResponse:
    result = await db.execute(
        select(GroceryList)
        .where(GroceryList.share_token == token)
        .options(selectinload(GroceryList.items))
    )
    glist = result.scalar_one_or_none()
    if glist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found"
        )

    data = await get_share_data(db, glist)

    items_resp = []
    for item in glist.items:
        r = GroceryListItemResponse.model_validate(item)
        if item.ingredient_id is not None:
            ing_result = await db.execute(
                select(Ingredient.name).where(Ingredient.id == item.ingredient_id)
            )
            ing_name = ing_result.scalar_one_or_none()
            if ing_name:
                r.name = ing_name
        items_resp.append(r)

    return GroceryListShareResponse(
        id=data["id"],
        household_name=data["household_name"],
        week_label=data["week_label"],
        items=items_resp,
        completed_at=data["completed_at"],
    )


@router.get("/{list_id}/share", response_model=dict[str, str])
async def get_share_token(
    list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.household_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    glist = await _get_owned_list(db, list_id, current_user.household_id)
    await get_share_data(db, glist)
    return {"token": glist.share_token or ""}
