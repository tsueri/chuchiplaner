from datetime import UTC
from datetime import datetime as dt
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.recipe import (
    Recipe,
    RecipeFavorite,
    RecipeIngredient,
    RecipeNote,
    RecipeTag,
    Tag,
)
from app.models.user import User
from app.schemas.recipe import (
    RecipeDetailResponse,
    RecipeFavoriteResponse,
    RecipeImportRequest,
    RecipeIngredientResponse,
    RecipeListResponse,
    RecipeNoteCreateRequest,
    RecipeNoteResponse,
    RecipeNoteUpdateRequest,
    RecipeResponse,
    RecipeSaveRequest,
    RecipeUpdateRequest,
    ScrapedIngredientItem,
    ScrapedRecipeResponse,
    TagCreateRequest,
    TagResponse,
)
from app.services.ingredient_line_parser import IngredientLineParser
from app.services.normalizer import IngredientNormalizer
from app.services.scraper import RecipeScraper

router = APIRouter(prefix="/recipes", tags=["recipes"])
tag_router = APIRouter(prefix="/tags", tags=["tags"])


def _build_tag_response(tag: Tag) -> TagResponse:
    return TagResponse(
        id=tag.id,
        name=tag.name,
        group=tag.group,
        household_id=tag.household_id,
    )


def _build_recipe_list_item(
    recipe: Recipe, user_id: int
) -> RecipeListResponse:
    tag_responses = [
        _build_tag_response(rt.tag) for rt in recipe.tags if rt.tag is not None
    ]
    is_favorited = bool(recipe.favorites)
    recipe_fav_ids = [f.user_id for f in recipe.favorites]
    if user_id in recipe_fav_ids:
        is_favorited = True

    return RecipeListResponse(
        id=recipe.id,
        title=recipe.title,
        instructions=recipe.instructions,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_domain=recipe.source_domain,
        servings=recipe.servings,
        household_id=recipe.household_id,
        tags=tag_responses,
        is_favorited=is_favorited,
        created_at=recipe.created_at,
    )


def _build_recipe_detail(recipe: Recipe, user_id: int) -> RecipeDetailResponse:
    tag_responses = [
        _build_tag_response(rt.tag) for rt in recipe.tags if rt.tag is not None
    ]
    fav_ids = [f.user_id for f in recipe.favorites]
    is_favorited = user_id in fav_ids

    return RecipeDetailResponse(
        id=recipe.id,
        title=recipe.title,
        instructions=recipe.instructions,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_domain=recipe.source_domain,
        servings=recipe.servings,
        household_id=recipe.household_id,
        ingredients=[
            RecipeIngredientResponse(
                id=i.id,
                ingredient_id=i.ingredient_id,
                quantity=i.quantity,
                unit=i.unit,
                order_index=i.order_index,
            )
            for i in recipe.ingredients
        ],
        tags=tag_responses,
        is_favorited=is_favorited,
        created_at=recipe.created_at,
    )


# ----- Recipe CRUD -----


@router.post("/import", response_model=ScrapedRecipeResponse)
async def import_recipe(
    body: RecipeImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScrapedRecipeResponse:
    parsed = urlparse(body.url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL",
        )

    result = await db.execute(
        select(Recipe).where(
            Recipe.source_url == body.url,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()

    scraped = RecipeScraper.scrape(body.url)
    if scraped is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract recipe from this URL",
        )

    alias_rows = await db.execute(
        select(IngredientAlias).where(
            IngredientAlias.household_id == current_user.household_id
        )
    )
    household_aliases: dict[str, int] = {
        a.alias_name: a.ingredient_id for a in alias_rows.scalars().all()
    }

    ingredient_rows = await db.execute(select(Ingredient))
    ingredient_map: dict[str, int] = {
        i.name: i.id for i in ingredient_rows.scalars().all()
    }

    normalizer = IngredientNormalizer(ingredient_map)

    parsed_items: list[ScrapedIngredientItem] = []
    for raw_line in scraped.ingredients:
        parsed_line = IngredientLineParser.parse(raw_line)
        if parsed_line.quantity is not None and parsed_line.name:
            resolved_id, confidence = normalizer.resolve(
                parsed_line.name, household_aliases
            )
        else:
            resolved_id, confidence = None, 0.0

        parsed_items.append(
            ScrapedIngredientItem(
                raw=raw_line,
                name=parsed_line.name,
                quantity=parsed_line.quantity,
                unit=parsed_line.unit,
                ingredient_id=resolved_id,
                confidence=confidence,
            )
        )

    return ScrapedRecipeResponse(
        title=scraped.title,
        ingredients=parsed_items,
        instructions=scraped.instructions,
        image_url=scraped.image_url,
        servings=scraped.servings,
        source_url=scraped.source_url,
        source_domain=scraped.source_domain,
        existing_recipe_id=existing.id if existing else None,
        is_partial=scraped.is_partial,
    )


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse | RecipeResponse:
    if body.source_url is not None:
        dup_result = await db.execute(
            select(Recipe).where(
                Recipe.source_url == body.source_url,
                Recipe.household_id == current_user.household_id,
                Recipe.deleted_at.is_(None),
            )
        )
        dup = dup_result.scalar_one_or_none()
        if dup is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": (
                        f"Duplikat: Ein Rezept mit der URL {body.source_url} "
                        "existiert bereits in diesem Haushalt."
                    ),
                    "existing_recipe_id": dup.id,
                },
            )

    recipe = Recipe(
        title=body.title,
        instructions=body.instructions,
        image_url=body.image_url,
        source_url=body.source_url,
        source_domain=body.source_domain,
        servings=body.servings,
        created_by=current_user.id,
        household_id=current_user.household_id,
    )
    db.add(recipe)
    await db.flush()

    for item in body.ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=item.ingredient_id,
            quantity=item.quantity,
            unit=item.unit,
            order_index=item.order_index,
        )
        db.add(recipe_ingredient)

    try:
        for alias_item in body.learned_aliases:
            ing_result = await db.execute(
                select(Ingredient).where(Ingredient.id == alias_item.ingredient_id)
            )
            if ing_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Ungültiger ingredient_id: "
                        f"Zutat mit ID {alias_item.ingredient_id} existiert nicht."
                    ),
                )
            alias = IngredientAlias(
                household_id=current_user.household_id,
                alias_name=alias_item.alias_name,
                ingredient_id=alias_item.ingredient_id,
            )
            db.add(alias)

        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ein Alias mit diesem Namen existiert bereits "
                "in diesem Haushalt."
            ),
        )

    from sqlalchemy import text as sqla_text
    await db.execute(
        sqla_text(
            "INSERT INTO recipes_fts(rowid, title, instructions) "
            "VALUES (:id, :title, :instructions)"
        ),
        {"id": recipe.id, "title": recipe.title, "instructions": recipe.instructions},
    )

    refreshed_result = await db.execute(
        select(Recipe)
        .where(Recipe.id == recipe.id)
        .options(selectinload(Recipe.ingredients))
    )
    refreshed = refreshed_result.scalar_one()
    return RecipeResponse(
        id=refreshed.id,
        title=refreshed.title,
        instructions=refreshed.instructions,
        image_url=refreshed.image_url,
        source_url=refreshed.source_url,
        source_domain=refreshed.source_domain,
        servings=refreshed.servings,
        household_id=refreshed.household_id,
        ingredients=[
            RecipeIngredientResponse(
                id=i.id,
                ingredient_id=i.ingredient_id,
                quantity=i.quantity,
                unit=i.unit,
                order_index=i.order_index,
            )
            for i in refreshed.ingredients
        ],
        created_at=refreshed.created_at,
    )


@router.get("/check-url")
async def check_url(
    url: str = Query(min_length=1, max_length=2048),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | None]:
    result = await db.execute(
        select(Recipe).where(
            Recipe.source_url == url,
            Recipe.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    return {"existing_recipe_id": existing.id if existing else None}


@router.get("", response_model=list[RecipeListResponse])
async def list_recipes(
    search: str | None = Query(default=None, min_length=1),
    tag_id: int | None = Query(default=None),
    favorites_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecipeListResponse]:
    base_query = select(Recipe).where(
        Recipe.household_id == current_user.household_id,
        Recipe.deleted_at.is_(None),
    )

    if search:
        from sqlalchemy import text as sqla_text
        fts_result = await db.execute(
            sqla_text(
                "SELECT rowid FROM recipes_fts WHERE recipes_fts MATCH :query"
            ),
            {"query": search},
        )
        fts_ids = [row[0] for row in fts_result.fetchall()]
        if fts_ids:
            base_query = base_query.where(
                Recipe.title.contains(search) | Recipe.id.in_(fts_ids)
            )
        else:
            base_query = base_query.where(Recipe.title.contains(search))

    if tag_id:
        tag_subq = (
            select(RecipeTag.recipe_id)
            .where(RecipeTag.tag_id == tag_id)
            .subquery()
        )
        base_query = base_query.where(Recipe.id.in_(select(tag_subq.c.recipe_id)))

    if favorites_only:
        fav_subq = (
            select(RecipeFavorite.recipe_id)
            .where(RecipeFavorite.user_id == current_user.id)
            .subquery()
        )
        base_query = base_query.where(Recipe.id.in_(select(fav_subq.c.recipe_id)))

    result = await db.execute(
        base_query
        .options(
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            selectinload(Recipe.favorites),
        )
        .order_by(Recipe.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    recipes = result.unique().scalars().all()
    return [_build_recipe_list_item(r, current_user.id) for r in recipes]


@router.get("/favorites", response_model=list[RecipeListResponse])
async def list_favorite_recipes(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecipeListResponse]:
    fav_subq = (
        select(RecipeFavorite.recipe_id)
        .where(RecipeFavorite.user_id == current_user.id)
        .subquery()
    )
    result = await db.execute(
        select(Recipe)
        .where(
            Recipe.id.in_(select(fav_subq.c.recipe_id)),
            Recipe.deleted_at.is_(None),
            Recipe.household_id == current_user.household_id,
        )
        .options(
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            selectinload(Recipe.favorites),
        )
        .order_by(Recipe.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    recipes = result.unique().scalars().all()
    return [_build_recipe_list_item(r, current_user.id) for r in recipes]


@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe_detail(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeDetailResponse:
    result = await db.execute(
        select(Recipe)
        .where(
            Recipe.id == recipe_id,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
        .options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            selectinload(Recipe.favorites),
        )
    )
    recipe = result.unique().scalar_one_or_none()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )
    return _build_recipe_detail(recipe, current_user.id)


@router.put("/{recipe_id}", response_model=RecipeDetailResponse)
async def update_recipe(
    recipe_id: int,
    body: RecipeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeDetailResponse:
    result = await db.execute(
        select(Recipe)
        .where(
            Recipe.id == recipe_id,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
        .options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            selectinload(Recipe.favorites),
        )
    )
    recipe = result.unique().scalar_one_or_none()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    if body.title is not None:
        recipe.title = body.title
    if body.instructions is not None:
        recipe.instructions = body.instructions
    if body.image_url is not None:
        recipe.image_url = body.image_url
    if body.servings is not None:
        recipe.servings = body.servings

    if body.tag_ids is not None:
        tag_ids_set = set(body.tag_ids)
        recipe_tag_ids = {rt.tag_id for rt in recipe.tags}

        for tr in list(recipe.tags):
            if tr.tag_id not in tag_ids_set:
                recipe.tags.remove(tr)

        for tid in tag_ids_set - recipe_tag_ids:
            recipe.tags.append(RecipeTag(tag_id=tid))

    await db.flush()

    from sqlalchemy import text as sqla_text
    if body.title is not None or body.instructions is not None:
        await db.execute(
            sqla_text(
                "DELETE FROM recipes_fts WHERE rowid = :id"
            ),
            {"id": recipe_id},
        )
        await db.execute(
            sqla_text(
                "INSERT INTO recipes_fts(rowid, title, instructions) "
                "VALUES (:id, :title, :instructions)"
            ),
            {
                "id": recipe.id,
                "title": recipe.title,
                "instructions": recipe.instructions,
            },
        )

    await db.refresh(recipe, ["ingredients", "tags", "favorites"])
    return _build_recipe_detail(recipe, current_user.id)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete recipes",
        )

    result = await db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    recipe.deleted_at = dt.now(UTC)

    from sqlalchemy import text as sqla_text
    await db.execute(
        sqla_text("DELETE FROM recipes_fts WHERE rowid = :id"),
        {"id": recipe_id},
    )


# ----- Favorites -----


@router.post(
    "/{recipe_id}/favorite",
    response_model=RecipeFavoriteResponse,
)
async def toggle_favorite(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeFavoriteResponse:
    recipe_result = await db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
    )
    recipe = recipe_result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    existing = await db.execute(
        select(RecipeFavorite).where(
            RecipeFavorite.user_id == current_user.id,
            RecipeFavorite.recipe_id == recipe_id,
        )
    )
    fav = existing.scalar_one_or_none()

    if fav:
        await db.delete(fav)
        return RecipeFavoriteResponse(
            id=fav.id,
            user_id=fav.user_id,
            recipe_id=fav.recipe_id,
            created_at=fav.created_at,
        )

    new_fav = RecipeFavorite(
        user_id=current_user.id,
        recipe_id=recipe_id,
    )
    db.add(new_fav)
    await db.flush()
    return RecipeFavoriteResponse(
        id=new_fav.id,
        user_id=new_fav.user_id,
        recipe_id=new_fav.recipe_id,
        created_at=new_fav.created_at,
    )


# ----- Notes -----


@router.post(
    "/{recipe_id}/notes",
    response_model=RecipeNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    recipe_id: int,
    body: RecipeNoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeNoteResponse:
    recipe_result = await db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
    )
    recipe = recipe_result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    note = RecipeNote(
        recipe_id=recipe_id,
        user_id=current_user.id,
        text=body.text,
        visibility=body.visibility,
    )
    db.add(note)
    await db.flush()

    return RecipeNoteResponse(
        id=note.id,
        recipe_id=note.recipe_id,
        user_id=note.user_id,
        text=note.text,
        visibility=note.visibility,
        username=current_user.username,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.put(
    "/{recipe_id}/notes/{note_id}",
    response_model=RecipeNoteResponse,
)
async def update_note(
    recipe_id: int,
    note_id: int,
    body: RecipeNoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeNoteResponse:
    result = await db.execute(
        select(RecipeNote, User.username)
        .join(User, RecipeNote.user_id == User.id)
        .where(
            RecipeNote.id == note_id,
            RecipeNote.recipe_id == recipe_id,
            RecipeNote.user_id == current_user.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    note, username = row
    note.text = body.text
    if body.visibility is not None:
        note.visibility = body.visibility

    note.updated_at = dt.now(UTC)
    await db.flush()

    return RecipeNoteResponse(
        id=note.id,
        recipe_id=note.recipe_id,
        user_id=note.user_id,
        text=note.text,
        visibility=note.visibility,
        username=username,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.delete(
    "/{recipe_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    recipe_id: int,
    note_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(RecipeNote).where(
            RecipeNote.id == note_id,
            RecipeNote.recipe_id == recipe_id,
            RecipeNote.user_id == current_user.id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    await db.delete(note)


@router.get("/{recipe_id}/notes", response_model=list[RecipeNoteResponse])
async def list_notes(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecipeNoteResponse]:
    result = await db.execute(
        select(RecipeNote, User.username)
        .join(User, RecipeNote.user_id == User.id)
        .where(RecipeNote.recipe_id == recipe_id)
        .order_by(RecipeNote.created_at.desc())
    )
    rows = result.all()

    notes: list[RecipeNoteResponse] = []
    for note, username in rows:
        is_own = note.user_id == current_user.id
        is_household_note = note.visibility == "household"
        if not is_own and not is_household_note:
            continue
        notes.append(
            RecipeNoteResponse(
                id=note.id,
                recipe_id=note.recipe_id,
                user_id=note.user_id,
                text=note.text,
                visibility=note.visibility,
                username=username,
                created_at=note.created_at,
                updated_at=note.updated_at,
            )
        )

    return notes


# ----- Tags -----


@tag_router.get("", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TagResponse]:
    result = await db.execute(
        select(Tag).where(
            (Tag.group == "season")
            | (
                (Tag.group == "ingredient")
                & (Tag.household_id == current_user.household_id)
            )
        )
    )
    tags = result.scalars().all()
    return [_build_tag_response(t) for t in tags]


@tag_router.post("", response_model=TagResponse)
async def create_tag(
    body: TagCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TagResponse:
    tag = Tag(
        name=body.name,
        group="ingredient",
        household_id=current_user.household_id,
    )
    db.add(tag)
    await db.flush()
    return _build_tag_response(tag)
