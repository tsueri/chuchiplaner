from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import IngredientAlias
from app.models.user import User
from app.schemas.ingredient import IngredientAliasCreate, IngredientAliasResponse

router = APIRouter(prefix="/household", tags=["household"])

HOUSEHOLD_ID = 1


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
    alias = IngredientAlias(
        household_id=HOUSEHOLD_ID,
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
    result = await db.execute(
        select(IngredientAlias).where(
            IngredientAlias.household_id == HOUSEHOLD_ID
        )
    )
    return list(result.scalars().all())
