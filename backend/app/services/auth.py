import hmac
import secrets
from datetime import UTC, datetime, timedelta

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import Session as SessionModel
from app.models.user import User
from app.services.household import (
    create_household,
    get_household_by_invite_code,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    invite_code: str | None = None,
) -> User:
    if invite_code is not None:
        household = await get_household_by_invite_code(db, invite_code)
        if household is None:
            raise ValueError("Invalid invite code")
        user = User(
            username=username,
            password_hash=hash_password(password),
            household_id=household.id,
            role="member",
        )
    else:
        household = await create_household(
            db, f"{username}'s Household"
        )
        user = User(
            username=username,
            password_hash=hash_password(password),
            household_id=household.id,
            role="admin",
        )
    db.add(user)
    await db.flush()
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_session(db: AsyncSession, user: User) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        token=secrets.token_hex(32),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(session)
    await db.flush()
    return session


async def get_session_by_token(
    db: AsyncSession, token: str
) -> SessionModel | None:
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.token == token)
        .where(SessionModel.expires_at > datetime.now(UTC))
        .options(selectinload(SessionModel.user).selectinload(User.household))
    )
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, token: str) -> None:
    result = await db.execute(
        select(SessionModel).where(SessionModel.token == token)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.flush()


def verify_admin_signup_code(submitted: str | None) -> bool:
    if not submitted:
        return False
    configured = settings.admin_signup_code.strip()
    if not configured:
        return False
    return hmac.compare_digest(submitted.strip(), configured)
