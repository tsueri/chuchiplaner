import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _set_admin_signup_code() -> None:
    original = settings.admin_signup_code
    settings.admin_signup_code = "test-secret"
    yield
    settings.admin_signup_code = original


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:  # type: ignore[misc]
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _setup_fts_and_seeds(connection):
            from sqlalchemy import text

            connection.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5("
                    "title, description, steps, ingredients, "
                    "keywords, author, tags)"
                )
            )
            season_tags = ["Frühling", "Sommer", "Herbst", "Winter", "Ganzjährig"]
            category_tags = [
                "Vorspeise",
                "Hauptgericht",
                "Dessert",
                "Snack",
                "Beilage",
            ]
            cuisine_tags = [
                "Italienisch",
                "Asiatisch",
                "Schweizerisch",
                "Mexikanisch",
                "Indisch",
                "Französisch",
            ]
            diet_tags = [
                "VegetarianDiet",
                "VeganDiet",
                "GlutenFreeDiet",
                "LowFatDiet",
                "LowLactoseDiet",
                "DiabeticDiet",
                "HalalDiet",
                "KosherDiet",
            ]
            for name in season_tags:
                connection.execute(
                    text(
                        'INSERT OR IGNORE INTO tags (name, "group", household_id) '
                        f"VALUES ('{name}', 'season', NULL)"
                    )
                )
            for name in category_tags:
                connection.execute(
                    text(
                        'INSERT OR IGNORE INTO tags (name, "group", household_id) '
                        f"VALUES ('{name}', 'category', NULL)"
                    )
                )
            for name in cuisine_tags:
                connection.execute(
                    text(
                        'INSERT OR IGNORE INTO tags (name, "group", household_id) '
                        f"VALUES ('{name}', 'cuisine', NULL)"
                    )
                )
            for name in diet_tags:
                connection.execute(
                    text(
                        'INSERT OR IGNORE INTO tags (name, "group", household_id) '
                        f"VALUES ('{name}', 'diet', NULL)"
                    )
                )

        await conn.run_sync(_setup_fts_and_seeds)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    from app.db.session import get_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
