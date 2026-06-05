"""Migration c2d3e4f5g6h7: seed global category, cuisine, diet tags.

Verifies that the new migration creates the standard controlled-vocabulary
tags as global (household_id IS NULL) and that the downgrade removes them.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from alembic import command


def _alembic_config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(Path(__file__).parent.parent / "alembic")
    )
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _new_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="chuchi-mig-tags-")
    db_path = os.path.join(tmp_dir, "test.db")
    return f"sqlite+aiosqlite:///{db_path}"


def _run_migration(database_url: str, target: str) -> None:
    cfg = _alembic_config(database_url)
    if "+" in target or target in ("head",):
        command.upgrade(cfg, target)
    else:
        rev = target
        if rev.startswith("-"):
            command.downgrade(cfg, rev[1:])
        else:
            command.upgrade(cfg, rev)


@pytest_asyncio.fixture
async def pre_seed_migration_db() -> AsyncGenerator[str, None]:
    db_url = _new_db()
    await asyncio.get_running_loop().run_in_executor(
        None, _run_migration, db_url, "b2c3d4e5f6a7"
    )
    yield db_url


@pytest_asyncio.fixture
async def post_seed_migration_db() -> AsyncGenerator[str, None]:
    db_url = _new_db()
    await asyncio.get_running_loop().run_in_executor(
        None, _run_migration, db_url, "c2d3e4f5g6h7"
    )
    yield db_url


CATEGORY_TAGS = ["Vorspeise", "Hauptgericht", "Dessert", "Snack", "Beilage"]
CUISINE_TAGS = [
    "Italienisch",
    "Asiatisch",
    "Schweizerisch",
    "Mexikanisch",
    "Indisch",
    "Französisch",
]
DIET_TAGS = [
    "VegetarianDiet",
    "VeganDiet",
    "GlutenFreeDiet",
    "LowFatDiet",
    "LowLactoseDiet",
    "DiabeticDiet",
    "HalalDiet",
    "KosherDiet",
]


@pytest.mark.asyncio
async def test_migration_seeds_global_category_tags(
    post_seed_migration_db: str,
) -> None:
    engine = create_async_engine(post_seed_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT name FROM tags WHERE \"group\" = 'category' "
                    "AND household_id IS NULL"
                )
            )
        ).all()
        names = {row[0] for row in rows}
        assert set(CATEGORY_TAGS) <= names
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_seeds_global_cuisine_tags(
    post_seed_migration_db: str,
) -> None:
    engine = create_async_engine(post_seed_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT name FROM tags WHERE \"group\" = 'cuisine' "
                    "AND household_id IS NULL"
                )
            )
        ).all()
        names = {row[0] for row in rows}
        assert set(CUISINE_TAGS) <= names
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_seeds_global_diet_tags(
    post_seed_migration_db: str,
) -> None:
    engine = create_async_engine(post_seed_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT name FROM tags WHERE \"group\" = 'diet' "
                    "AND household_id IS NULL"
                )
            )
        ).all()
        names = {row[0] for row in rows}
        assert set(DIET_TAGS) <= names
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_seeded_tags_remain_global(
    post_seed_migration_db: str,
) -> None:
    engine = create_async_engine(post_seed_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    seeded_names = CATEGORY_TAGS + CUISINE_TAGS + DIET_TAGS
    in_clause = ",".join(f"'{n}'" for n in seeded_names)
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    'SELECT "group", COUNT(*) FROM tags '
                    f"WHERE name IN ({in_clause}) "
                    'GROUP BY "group"'
                )
            )
        ).all()
        groups = {row[0] for row in rows}
        assert groups == {"category", "cuisine", "diet"}
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_seed_downgrade_removes_only_seeded_tags(
    post_seed_migration_db: str,
) -> None:
    await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: command.downgrade(
            _alembic_config(post_seed_migration_db), "b2c3d4e5f6a7"
        ),
    )

    engine = create_async_engine(post_seed_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    'SELECT name FROM tags WHERE "group" IN '
                    "('category', 'cuisine', 'diet')"
                )
            )
        ).all()
        names = {row[0] for row in rows}
        assert names == set()

        season_rows = (
            await session.execute(
                text("SELECT name FROM tags WHERE \"group\" = 'season'")
            )
        ).all()
        season_names = {row[0] for row in season_rows}
        assert {"Frühling", "Sommer", "Herbst", "Winter", "Ganzjährig"} <= season_names

    await engine.dispose()
