import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import (
    LOGIN_LIMIT,
    LOGIN_WINDOW,
    _check_rate_limit,
    rate_limit_login,
    rate_limit_password,
    rate_limit_register,
)
from app.db.session import get_db
from app.models.recipe import Recipe, RecipeFavorite, RecipeNote
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    UserResponse,
)
from app.schemas.recipe import (
    RecipeListResponse,
    RecipeNoteResponse,
    TagResponse,
)
from app.services.auth import (
    create_session,
    create_user,
    delete_session,
    get_session_by_token,
    get_user_by_username,
    hash_password,
    verify_admin_signup_code,
    verify_password,
)
from app.services.household import get_household_by_invite_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "session_token"

# Precomputed dummy bcrypt hash for constant-time login verification.
# When no user is found, verify_password is still called against this hash
# so a timing observer cannot distinguish the "unknown user" branch from
# the "wrong password" branch.
_DUMMY_HASH: str = hash_password("dummy_constanthash_for_timing_safety")
logger.debug("Dummy hash computed for constant-time login verification")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie.name,
        value=token,
        httponly=settings.cookie.httponly,
        samesite=settings.cookie.samesite,
        secure=settings.cookie.secure,
        max_age=settings.cookie.max_age_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.cookie.name, path="/")


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    token = getattr(request.state, "session_token", None)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    session = await get_session_by_token(db, token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return session.user


@router.post("/register", response_model=UserResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_register),
) -> User:
    if not settings.signup_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signup is disabled",
        )
    if body.invite_code:
        household = await get_household_by_invite_code(db, body.invite_code)
        if household is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid invite code",
            )
    elif not verify_admin_signup_code(body.admin_signup_code):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite code or admin signup code required",
        )
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    try:
        user = await create_user(
            db, body.username, body.password, body.invite_code
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    session = await create_session(db, user)
    _set_session_cookie(response, session.token)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl_ip: None = Depends(rate_limit_login),
) -> User:
    await _check_rate_limit(
        f"login:user:{body.username}", limit=LOGIN_LIMIT, window_seconds=LOGIN_WINDOW
    )
    user = await get_user_by_username(db, body.username)
    if user is not None:
        password_valid = verify_password(body.password, user.password_hash)
    else:
        verify_password(body.password, _DUMMY_HASH)  # constant-time, discard
        password_valid = False
    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    session = await create_session(db, user)
    _set_session_cookie(response, session.token)
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = request.cookies.get(settings.cookie.name)
    if token:
        await delete_session(db, token)
    _clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/password")
async def change_password(
    body: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_password),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from current password",
        )
    current_user.password_hash = hash_password(body.new_password)
    await db.flush()
    return {"status": "ok"}


@router.get("/user/favorites", response_model=list[RecipeListResponse])
async def list_user_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecipeListResponse]:
    from app.models.recipe import RecipeTag, Tag

    result = await db.execute(
        select(Recipe)
        .join(RecipeFavorite, RecipeFavorite.recipe_id == Recipe.id)
        .where(RecipeFavorite.user_id == current_user.id)
        .where(Recipe.deleted_at.is_(None))
        .order_by(RecipeFavorite.created_at.desc())
    )
    recipes = result.unique().scalars().all()

    recipe_ids = [r.id for r in recipes]
    tags_by_recipe: dict[int, list[Tag]] = {}
    if recipe_ids:
        tag_result = await db.execute(
            select(RecipeTag, Tag)
            .join(Tag, RecipeTag.tag_id == Tag.id)
            .where(RecipeTag.recipe_id.in_(recipe_ids))
        )
        for rt, tag in tag_result:
            tags_by_recipe.setdefault(rt.recipe_id, []).append(tag)

    return [
        RecipeListResponse(
            id=r.id, title=r.title,
            description=r.description,
            image_url=r.image_url, source_url=r.source_url,
            source_domain=r.source_domain, servings=r.servings,
            prep_time_minutes=r.prep_time_minutes,
            cook_time_minutes=r.cook_time_minutes,
            total_time_minutes=r.total_time_minutes,
            perform_time_minutes=r.perform_time_minutes,
            nutrition=r.nutrition,
            aggregate_rating=r.aggregate_rating,
            keywords=r.keywords,
            author=r.author,
            date_published=r.date_published,
            household_id=r.household_id,
            tags=[
                TagResponse(id=t.id, name=t.name, group=t.group,
                            household_id=t.household_id)
                for t in tags_by_recipe.get(r.id, [])
            ],
            is_favorited=True, created_at=r.created_at,
        )
        for r in recipes
    ]


@router.get("/user/notes", response_model=list[RecipeNoteResponse])
async def list_user_notes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecipeNoteResponse]:
    result = await db.execute(
        select(RecipeNote)
        .where(RecipeNote.user_id == current_user.id)
        .order_by(RecipeNote.created_at.desc())
    )
    notes = result.scalars().all()

    recipe_ids = list({n.recipe_id for n in notes})
    recipe_titles: dict[int, str] = {}
    if recipe_ids:
        recipe_result = await db.execute(
            select(Recipe.id, Recipe.title).where(Recipe.id.in_(recipe_ids))
        )
        for rid, rtitle in recipe_result:
            recipe_titles[rid] = rtitle

    return [
        RecipeNoteResponse(
            id=n.id, recipe_id=n.recipe_id, user_id=n.user_id,
            text=n.text, visibility=n.visibility,
            username=current_user.username,
            recipe_title=recipe_titles.get(n.recipe_id),
            created_at=n.created_at, updated_at=n.updated_at,
        )
        for n in notes
    ]
