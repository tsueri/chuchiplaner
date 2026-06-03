"""Migration b2c3d4e5f6a7: recipe model v2 — instructions → recipe_steps,
9 nullable Recipe columns, recipes_fts multi-column rebuild, tags.group expansion.
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
    tmp_dir = tempfile.mkdtemp(prefix="chuchi-mig-")
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
async def pre_migration_db() -> AsyncGenerator[str, None]:
    db_url = _new_db()
    await asyncio.get_running_loop().run_in_executor(
        None, _run_migration, db_url, "a7b8c9d0e1f2"
    )
    yield db_url


@pytest_asyncio.fixture
async def post_migration_db() -> AsyncGenerator[str, None]:
    db_url = _new_db()
    await asyncio.get_running_loop().run_in_executor(
        None, _run_migration, db_url, "b2c3d4e5f6a7"
    )
    yield db_url


@pytest.mark.asyncio
async def test_migration_forward_seeds_recipe_steps_from_instructions(
    pre_migration_db: str,
) -> None:
    engine = create_async_engine(pre_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO households (id, name, slug, invite_code) "
                "VALUES (1, 'H1', 'h1', 'inv-1')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO recipes (id, title, instructions, servings, "
                "household_id) VALUES (1, 'R1', "
                "'Anbraten und ablöschen.', 4, 1)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO recipes (id, title, instructions, servings, "
                "household_id) VALUES (2, 'R2', '', 2, 1)"
            )
        )

    await asyncio.get_running_loop().run_in_executor(
        None, _run_migration, pre_migration_db, "b2c3d4e5f6a7"
    )

    async with session_factory() as session:  # type: AsyncSession
        result = await session.execute(
            text("PRAGMA table_info(recipes)")
        )
        columns = {row[1] for row in result.fetchall()}
        assert "instructions" not in columns
        assert "description" in columns
        assert "prep_time_minutes" in columns
        assert "cook_time_minutes" in columns
        assert "total_time_minutes" in columns
        assert "perform_time_minutes" in columns
        assert "nutrition" in columns
        assert "aggregate_rating" in columns
        assert "keywords" in columns
        assert "author" in columns
        assert "date_published" in columns

        step_rows = (
            await session.execute(
                text(
                    "SELECT recipe_id, position, text, name "
                    "FROM recipe_steps ORDER BY recipe_id"
                )
            )
        ).all()
        assert len(step_rows) == 2
        r1, r2 = step_rows
        assert r1[0] == 1 and r1[1] == 0
        assert r1[2] == "Anbraten und ablöschen."
        assert r2[0] == 2 and r2[1] == 0
        assert r2[2] == ""

        fts_row = (
            await session.execute(
                text(
                    "SELECT title, steps FROM recipes_fts "
                    "WHERE rowid = 1"
                )
            )
        ).first()
        assert fts_row is not None
        assert fts_row[0] == "R1"
        assert fts_row[1] == "Anbraten und ablöschen."

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_forward_creates_tag_with_new_group(
    post_migration_db: str,
) -> None:
    engine = create_async_engine(post_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        for group in ("season", "ingredient", "category", "cuisine", "diet"):
            await conn.execute(
                text(
                    "INSERT INTO tags (name, \"group\", household_id) "
                    f"VALUES ('T-{group}', '{group}', NULL)"
                )
            )

    async with session_factory() as session:
        seen = {
            row[0]: row[1]
            for row in (
                await session.execute(
                    text("SELECT name, \"group\" FROM tags")
                )
            ).all()
        }
        assert seen["T-season"] == "season"
        assert seen["T-ingredient"] == "ingredient"
        assert seen["T-category"] == "category"
        assert seen["T-cuisine"] == "cuisine"
        assert seen["T-diet"] == "diet"

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_back_recreates_instructions_from_steps(
    post_migration_db: str,
) -> None:
    engine = create_async_engine(post_migration_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO households (id, name, slug, invite_code) "
                "VALUES (1, 'H1', 'h1', 'inv-1')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO recipes (id, title, servings, household_id) "
                "VALUES (1, 'R1', 4, 1)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO recipe_steps (recipe_id, position, text, name) "
                "VALUES (1, 0, 'Schritt 1', NULL)"
            )
        )

    await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: command.downgrade(
            _alembic_config(post_migration_db), "a7b8c9d0e1f2"
        ),
    )

    async with session_factory() as session:
        result = await session.execute(
            text("PRAGMA table_info(recipes)")
        )
        columns = {row[1] for row in result.fetchall()}
        assert "instructions" in columns
        assert "description" not in columns
        assert "prep_time_minutes" not in columns
        assert "nutrition" not in columns
        assert "date_published" not in columns

        instructions = (
            await session.execute(
                text("SELECT instructions FROM recipes WHERE id = 1")
            )
        ).scalar_one()
        assert instructions == "Schritt 1"

        fts_row = (
            await session.execute(
                text(
                    "SELECT title, instructions FROM recipes_fts "
                    "WHERE rowid = 1"
                )
            )
        ).first()
        assert fts_row is not None
        assert fts_row[0] == "R1"
        assert fts_row[1] == "Schritt 1"

        step_table_exists = (
            await session.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='recipe_steps'"
                )
            )
        ).first()
        assert step_table_exists is None

    await engine.dispose()
