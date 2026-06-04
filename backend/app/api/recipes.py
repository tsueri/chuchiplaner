from datetime import UTC
from datetime import datetime as dt
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
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
    RecipeStep,
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
    RecipeStepItem,
    RecipeStepResponse,
    RecipeUpdateRequest,
    ScrapedIngredientItem,
    ScrapedRecipeResponse,
    ScrapedStepItem,
    TagCreateRequest,
    TagResponse,
)
from app.services.fts_rebuilder import FTSRebuilder
from app.services.ingredient_line_parser import IngredientLineParser
from app.services.normalizer import IngredientNormalizer
from app.services.nutrition_parser import NutritionParser
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


def _build_recipe_ingredient_response(
    ri: RecipeIngredient,
) -> RecipeIngredientResponse:
    return RecipeIngredientResponse(
        id=ri.id,
        ingredient_id=ri.ingredient_id,
        quantity=ri.quantity,
        unit=ri.unit,
        order_index=ri.order_index,
        ingredient_name=ri.ingredient.name,
    )


def _build_recipe_step_response(step: RecipeStep) -> RecipeStepResponse:
    return RecipeStepResponse(
        id=step.id,
        position=step.position,
        text=step.text,
        name=step.name,
    )


def _build_recipe_step_responses(
    steps: list[RecipeStep],
) -> list[RecipeStepResponse]:
    sorted_steps = sorted(steps, key=lambda s: s.position)
    return [_build_recipe_step_response(s) for s in sorted_steps]


def _build_recipe_list_item(
    recipe: Recipe, user_id: int
) -> RecipeListResponse:
    tag_responses = [
        _build_tag_response(rt.tag) for rt in recipe.tags if rt.tag is not None
    ]
    recipe_fav_ids = [f.user_id for f in recipe.favorites]
    is_favorited = user_id in recipe_fav_ids

    return RecipeListResponse(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_domain=recipe.source_domain,
        servings=recipe.servings,
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        total_time_minutes=recipe.total_time_minutes,
        perform_time_minutes=recipe.perform_time_minutes,
        nutrition=recipe.nutrition,
        aggregate_rating=recipe.aggregate_rating,
        keywords=recipe.keywords,
        author=recipe.author,
        date_published=recipe.date_published,
        household_id=recipe.household_id,
        tags=tag_responses,
        is_favorited=is_favorited,
        created_at=recipe.created_at,
        ingredients=[_build_recipe_ingredient_response(i) for i in recipe.ingredients],
        steps=_build_recipe_step_responses(recipe.steps),
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
        description=recipe.description,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_domain=recipe.source_domain,
        servings=recipe.servings,
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        total_time_minutes=recipe.total_time_minutes,
        perform_time_minutes=recipe.perform_time_minutes,
        nutrition=recipe.nutrition,
        aggregate_rating=recipe.aggregate_rating,
        keywords=recipe.keywords,
        author=recipe.author,
        date_published=recipe.date_published,
        household_id=recipe.household_id,
        ingredients=[_build_recipe_ingredient_response(i) for i in recipe.ingredients],
        steps=_build_recipe_step_responses(recipe.steps),
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

    steps: list[ScrapedStepItem] = []
    if scraped.instructions:
        steps.append(ScrapedStepItem(position=0, text=scraped.instructions, name=None))

    diet_tag_ids: list[int] = []
    if scraped.suitable_for_diet:
        diet_uris = {
            uri.rstrip("/").split("/")[-1]
            for uri in scraped.suitable_for_diet
        }
        if diet_uris:
            diet_result = await db.execute(
                select(Tag.id).where(
                    Tag.name.in_(diet_uris),
                    Tag.group == "diet",
                    Tag.household_id.is_(None),
                )
            )
            diet_tag_ids = [row for (row,) in diet_result.all()]

    nutrients_parsed = None
    if scraped.nutrients:
        parsed_nutrition = NutritionParser.parse(scraped.nutrients)
        if parsed_nutrition is not None:
            nutrients_parsed = parsed_nutrition.to_dict()

    return ScrapedRecipeResponse(
        title=scraped.title,
        ingredients=parsed_items,
        image_url=scraped.image_url,
        servings=scraped.servings,
        source_url=scraped.source_url,
        source_domain=scraped.source_domain,
        existing_recipe_id=existing.id if existing else None,
        is_partial=scraped.is_partial,
        steps=steps,
        description=scraped.description,
        prep_time_minutes=scraped.prep_time_minutes,
        cook_time_minutes=scraped.cook_time_minutes,
        total_time_minutes=scraped.total_time_minutes,
        perform_time_minutes=scraped.perform_time_minutes,
        author=scraped.author,
        date_published=scraped.date_published,
        keywords=scraped.keywords,
        ratings=scraped.ratings,
        nutrients=nutrients_parsed,
        suitable_for_diet_tag_ids=diet_tag_ids,
    )


def _assign_recipe_fields(
    recipe: Recipe, body: RecipeSaveRequest | RecipeUpdateRequest
) -> None:
    if body.title is not None:
        recipe.title = body.title
    if body.description is not None:
        recipe.description = body.description
    if body.image_url is not None:
        recipe.image_url = body.image_url
    if body.source_url is not None:
        recipe.source_url = body.source_url
    if getattr(body, "source_domain", None) is not None:
        recipe.source_domain = body.source_domain
    if body.servings is not None:
        recipe.servings = body.servings
    if body.prep_time_minutes is not None:
        recipe.prep_time_minutes = body.prep_time_minutes
    if body.cook_time_minutes is not None:
        recipe.cook_time_minutes = body.cook_time_minutes
    if body.total_time_minutes is not None:
        recipe.total_time_minutes = body.total_time_minutes
    if body.perform_time_minutes is not None:
        recipe.perform_time_minutes = body.perform_time_minutes
    if body.nutrition is not None:
        recipe.nutrition = body.nutrition
    if body.aggregate_rating is not None:
        recipe.aggregate_rating = body.aggregate_rating
    if body.keywords is not None:
        recipe.keywords = body.keywords
    if body.author is not None:
        recipe.author = body.author
    if body.date_published is not None:
        recipe.date_published = body.date_published


async def _apply_recipe_steps(
    db: AsyncSession, recipe: Recipe, step_items: list[RecipeStepItem]
) -> None:
    for existing in list(recipe.steps):
        recipe.steps.remove(existing)
    await db.flush()
    for idx, step_item in enumerate(step_items):
        recipe.steps.append(
            RecipeStep(
                recipe_id=recipe.id,
                position=idx,
                text=step_item.text,
                name=step_item.name,
            )
        )


async def _apply_recipe_tags(
    db: AsyncSession, recipe: Recipe, tag_ids: list[int]
) -> None:
    tag_ids_set = set(tag_ids)
    recipe_tag_ids = {rt.tag_id for rt in recipe.tags}

    if tag_ids_set:
        incoming_tags_result = await db.execute(
            select(Tag).where(Tag.id.in_(tag_ids_set))
        )
        incoming_tags = incoming_tags_result.scalars().all()
        single_value_groups = {
            t.group for t in incoming_tags if t.group in ("category", "cuisine")
        }
        for tr in list(recipe.tags):
            if tr.tag is None:
                continue
            if tr.tag.group in single_value_groups and tr.tag_id not in tag_ids_set:
                recipe.tags.remove(tr)
                continue
            if tr.tag_id not in tag_ids_set:
                recipe.tags.remove(tr)
    else:
        for tr in list(recipe.tags):
            recipe.tags.remove(tr)

    new_tag_ids = tag_ids_set - recipe_tag_ids
    if new_tag_ids:
        tag_rows_result = await db.execute(
            select(Tag).where(Tag.id.in_(new_tag_ids))
        )
        tag_rows = {t.id: t for t in tag_rows_result.scalars().all()}
        for tid in new_tag_ids:
            tag = tag_rows.get(tid)
            recipe.tags.append(RecipeTag(tag_id=tid, tag=tag))


async def _persist_recipe_aliases(
    db: AsyncSession,
    body: RecipeSaveRequest,
    household_id: int | None,
) -> None:
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
            household_id=household_id,
            alias_name=alias_item.alias_name,
            ingredient_id=alias_item.ingredient_id,
        )
        db.add(alias)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ein Alias mit diesem Namen existiert bereits "
                "in diesem Haushalt."
            ),
        )


async def _upsert_recipe(
    db: AsyncSession,
    body: RecipeSaveRequest,
    existing: Recipe,
    current_user: User,
) -> RecipeDetailResponse:
    _assign_recipe_fields(existing, body)

    if body.ingredients is not None:
        for item in body.ingredients:
            ing_result = await db.execute(
                select(Ingredient).where(Ingredient.id == item.ingredient_id)
            )
            if ing_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Ungültiger ingredient_id: "
                        f"Zutat mit ID {item.ingredient_id} existiert nicht."
                    ),
                )

        for existing_ing in list(existing.ingredients):
            existing.ingredients.remove(existing_ing)

        for idx, item in enumerate(body.ingredients):
            new_ri = RecipeIngredient(
                recipe_id=existing.id,
                ingredient_id=item.ingredient_id,
                quantity=item.quantity,
                unit=item.unit,
                order_index=idx,
            )
            db.add(new_ri)
            existing.ingredients.append(new_ri)

    if body.steps is not None:
        await _apply_recipe_steps(db, existing, body.steps)

    if body.tag_ids is not None:
        await _apply_recipe_tags(db, existing, body.tag_ids)

    if body.learned_aliases:
        await _persist_recipe_aliases(db, body, current_user.household_id)

    await db.flush()

    await FTSRebuilder.reindex_one(db, existing.id)

    refreshed_result = await db.execute(
        select(Recipe)
        .where(Recipe.id == existing.id)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            selectinload(Recipe.favorites),
        )
    )
    refreshed = refreshed_result.unique().scalar_one()
    return _build_recipe_detail(refreshed, current_user.id)


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse | RecipeResponse:
    """Create a new recipe, or upsert an existing one when ``reimport=True``.

    Behavior:
    - ``reimport=False`` (default): a ``source_url`` collision returns 409 with
      ``existing_recipe_id``. This is the manual-create path: a user typing in
      a URL that already exists in the household should be told, not silently
      overwritten.
    - ``reimport=True``: a ``source_url`` collision performs an upsert. The
      existing row's fields are overwritten with the new body (title,
      description, times, steps, ingredients, tags, image_url, servings).
      The response is the updated ``RecipeDetailResponse`` (status 200) for
      that row.
    - ``reimport=True`` with a new ``source_url`` (or null) creates a new
      recipe and returns 201 — same as the manual path.
    """
    if body.source_url is not None:
        dup_result = await db.execute(
            select(Recipe)
            .where(
                Recipe.source_url == body.source_url,
                Recipe.household_id == current_user.household_id,
                Recipe.deleted_at.is_(None),
            )
            .options(
                selectinload(Recipe.ingredients).selectinload(
                    RecipeIngredient.ingredient
                ),
                selectinload(Recipe.steps),
                selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            )
        )
        dup = dup_result.scalar_one_or_none()
        if dup is not None:
            if not body.reimport:
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
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=jsonable_encoder(
                    await _upsert_recipe(db, body, dup, current_user)
                ),
            )

    recipe = Recipe(
        title=body.title,
        description=body.description,
        image_url=body.image_url,
        source_url=body.source_url,
        source_domain=body.source_domain,
        servings=body.servings,
        prep_time_minutes=body.prep_time_minutes,
        cook_time_minutes=body.cook_time_minutes,
        total_time_minutes=body.total_time_minutes,
        perform_time_minutes=body.perform_time_minutes,
        nutrition=body.nutrition,
        aggregate_rating=body.aggregate_rating,
        keywords=body.keywords,
        author=body.author,
        date_published=body.date_published,
        created_by=current_user.id,
        household_id=current_user.household_id,
    )
    db.add(recipe)
    await db.flush()

    if body.steps:
        for idx, step_item in enumerate(body.steps):
            db.add(
                RecipeStep(
                    recipe_id=recipe.id,
                    position=idx,
                    text=step_item.text,
                    name=step_item.name,
                )
            )
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

    if body.tag_ids is not None:
        await _apply_recipe_tags(db, recipe, body.tag_ids)

    if body.learned_aliases:
        await _persist_recipe_aliases(db, body, current_user.household_id)

    await db.flush()

    await FTSRebuilder.reindex_one(db, recipe.id)

    refreshed_result = await db.execute(
        select(Recipe)
        .where(Recipe.id == recipe.id)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            selectinload(Recipe.favorites),
        )
    )
    refreshed = refreshed_result.unique().scalar_one()
    return RecipeResponse(
        id=refreshed.id,
        title=refreshed.title,
        description=refreshed.description,
        image_url=refreshed.image_url,
        source_url=refreshed.source_url,
        source_domain=refreshed.source_domain,
        servings=refreshed.servings,
        prep_time_minutes=refreshed.prep_time_minutes,
        cook_time_minutes=refreshed.cook_time_minutes,
        total_time_minutes=refreshed.total_time_minutes,
        perform_time_minutes=refreshed.perform_time_minutes,
        nutrition=refreshed.nutrition,
        aggregate_rating=refreshed.aggregate_rating,
        keywords=refreshed.keywords,
        author=refreshed.author,
        date_published=refreshed.date_published,
        household_id=refreshed.household_id,
        ingredients=[
            _build_recipe_ingredient_response(i) for i in refreshed.ingredients
        ],
        steps=_build_recipe_step_responses(refreshed.steps),
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

    fts_ids_ranked: list[int] = []
    if search:
        from sqlalchemy import text as sqla_text
        fts_result = await db.execute(
            sqla_text(
                "SELECT rowid FROM recipes_fts WHERE recipes_fts MATCH :query "
                f"ORDER BY bm25(recipes_fts, {FTSRebuilder.weights_sql()})"
            ),
            {"query": search},
        )
        fts_ids_ranked = [row[0] for row in fts_result.fetchall()]
        if fts_ids_ranked:
            base_query = base_query.where(
                Recipe.title.contains(search) | Recipe.id.in_(fts_ids_ranked)
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

    base_query = base_query.options(
        selectinload(Recipe.tags).selectinload(RecipeTag.tag),
        selectinload(Recipe.favorites),
        selectinload(Recipe.ingredients).selectinload(
            RecipeIngredient.ingredient
        ),
        selectinload(Recipe.steps),
    )

    if fts_ids_ranked:
        result = await db.execute(base_query)
        recipes = result.unique().scalars().all()
        rank_index = {rid: idx for idx, rid in enumerate(fts_ids_ranked)}

        def _sort_key(r: Recipe) -> tuple[int, float]:
            if r.id in rank_index:
                return (0, float(rank_index[r.id]))
            return (1, -r.created_at.timestamp())

        recipes_sorted = sorted(recipes, key=_sort_key)
        return [
            _build_recipe_list_item(r, current_user.id)
            for r in recipes_sorted[offset : offset + limit]
        ]

    result = await db.execute(
        base_query.order_by(Recipe.created_at.desc()).offset(offset).limit(limit)
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
            selectinload(Recipe.ingredients).selectinload(
                RecipeIngredient.ingredient
            ),
            selectinload(Recipe.steps),
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
            selectinload(Recipe.ingredients).selectinload(
                RecipeIngredient.ingredient
            ),
            selectinload(Recipe.steps),
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
) -> JSONResponse | RecipeDetailResponse:
    result = await db.execute(
        select(Recipe)
        .where(
            Recipe.id == recipe_id,
            Recipe.household_id == current_user.household_id,
            Recipe.deleted_at.is_(None),
        )
        .options(
            selectinload(Recipe.ingredients).selectinload(
                RecipeIngredient.ingredient
            ),
            selectinload(Recipe.steps),
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

    if body.source_url is not None and body.source_url != recipe.source_url:
        dup_result = await db.execute(
            select(Recipe).where(
                Recipe.source_url == body.source_url,
                Recipe.household_id == current_user.household_id,
                Recipe.id != recipe_id,
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

    _assign_recipe_fields(recipe, body)

    if body.tag_ids is not None:
        await _apply_recipe_tags(db, recipe, body.tag_ids)

    if body.ingredients is not None:
        for item in body.ingredients:
            ing_result = await db.execute(
                select(Ingredient).where(Ingredient.id == item.ingredient_id)
            )
            if ing_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Ungültiger ingredient_id: "
                        f"Zutat mit ID {item.ingredient_id} existiert nicht."
                    ),
                )

        for existing in list(recipe.ingredients):
            recipe.ingredients.remove(existing)

        for idx, item in enumerate(body.ingredients):
            db.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=item.ingredient_id,
                    quantity=item.quantity,
                    unit=item.unit,
                    order_index=idx,
                )
            )

    if body.steps is not None:
        await _apply_recipe_steps(db, recipe, body.steps)

    await db.flush()

    fts_reindex = (
        body.title is not None
        or body.description is not None
        or body.keywords is not None
        or body.author is not None
        or body.steps is not None
        or body.ingredients is not None
        or body.tag_ids is not None
    )
    if fts_reindex:
        await FTSRebuilder.reindex_one(db, recipe_id)

    await db.refresh(
        recipe, ["ingredients", "steps", "tags", "favorites"]
    )
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

    await FTSRebuilder.delete_one(db, recipe_id)


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
            Tag.group.in_(["season", "category", "cuisine", "diet"])
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
    global_groups = {"season", "category", "cuisine", "diet"}
    if body.group in global_groups:
        household_id: int | None = None
    else:
        household_id = current_user.household_id
    tag = Tag(
        name=body.name,
        group=body.group,
        household_id=household_id,
    )
    db.add(tag)
    await db.flush()
    return _build_tag_response(tag)
