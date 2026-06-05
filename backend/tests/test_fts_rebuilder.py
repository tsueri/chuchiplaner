"""FTSRebuilder: drops and recreates recipes_fts and repopulates from the
joined recipe / recipe_steps / recipe_ingredients / tags state.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fts_rebuilder import COLUMNS, WEIGHTS, FTSRebuilder


@pytest.mark.asyncio
async def test_rebuilder_columns_in_documented_order() -> None:
    assert COLUMNS == (
        "title",
        "description",
        "steps",
        "ingredients",
        "keywords",
        "author",
        "tags",
    )


@pytest.mark.asyncio
async def test_rebuilder_ingredients_outrank_steps_outrank_title() -> None:
    assert WEIGHTS["ingredients"] > WEIGHTS["steps"]
    assert WEIGHTS["ingredients"] > WEIGHTS["description"]
    assert WEIGHTS["steps"] > WEIGHTS["title"]
    assert WEIGHTS["description"] > WEIGHTS["title"]


@pytest.mark.asyncio
async def test_weights_sql_lists_one_per_column_in_column_order() -> None:
    parts = FTSRebuilder.weights_sql().split(", ")
    assert len(parts) == len(COLUMNS)
    for value, column in zip(parts, COLUMNS, strict=True):
        assert float(value) == WEIGHTS[column]


@pytest.mark.asyncio
async def test_rebuild_populates_columns_from_joined_state(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO households "
            "(id, name, slug, invite_code, default_size, default_public) "
            "VALUES (901, 'H1', 'h1', 'inv-901', 4, 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, description, keywords, "
            "author, servings, household_id) "
            "VALUES (901, 'Tomatensuppe', 'Klassiker', 'schnell', "
            "'Anna', 4, 901)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text) "
            "VALUES (901, 0, 'Rühren und köcheln.')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO ingredients (id, name) "
            "VALUES (901, 'Tomate'), (902, 'Basilikum')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (901, 901, 500, 'g', 0), (901, 902, 1, 'Bund', 1)"
        )
    )
    await db_session.execute(
        text(
            'INSERT INTO tags (id, name, "group", household_id) '
            "VALUES (901, 'Mediterran', 'cuisine', NULL)"
        )
    )
    await db_session.execute(
        text("INSERT INTO recipe_tags (recipe_id, tag_id) VALUES (901, 901)")
    )
    await db_session.execute(text("DELETE FROM recipes_fts WHERE rowid = 901"))

    await FTSRebuilder.rebuild(db_session)

    row = (
        await db_session.execute(
            text(
                "SELECT title, description, steps, ingredients, keywords, "
                "author, tags FROM recipes_fts WHERE rowid = 901"
            )
        )
    ).first()
    assert row is not None
    assert row[0] == "Tomatensuppe"
    assert row[1] == "Klassiker"
    assert row[2] == "Rühren und köcheln."
    assert "Tomate" in row[3]
    assert "Basilikum" in row[3]
    assert row[4] == "schnell"
    assert row[5] == "Anna"
    assert row[6] == "Mediterran"


@pytest.mark.asyncio
async def test_rebuild_ingredient_search_finds_recipe_absent_from_title(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO households "
            "(id, name, slug, invite_code, default_size, default_public) "
            "VALUES (902, 'H2', 'h2', 'inv-902', 4, 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            "VALUES (902, 'Pasta', 4, 902)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text) "
            "VALUES (902, 0, 'Cook.')"
        )
    )
    await db_session.execute(
        text("INSERT INTO ingredients (id, name) VALUES (903, 'Tomatenkonzentrat')")
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (902, 903, 200, 'g', 0)"
        )
    )

    await FTSRebuilder.rebuild(db_session)

    hits = (
        await db_session.execute(
            text("SELECT rowid FROM recipes_fts WHERE recipes_fts MATCH :q"),
            {"q": "Tomatenkonzentrat"},
        )
    ).fetchall()
    assert [row[0] for row in hits] == [902]


@pytest.mark.asyncio
async def test_rebuild_skips_soft_deleted_recipes(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO households "
            "(id, name, slug, invite_code, default_size, default_public) "
            "VALUES (903, 'H3', 'h3', 'inv-903', 4, 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id, "
            "deleted_at) VALUES "
            "(903, 'Alive', 4, 903, NULL), "
            "(904, 'Tombstoned', 4, 903, '2026-01-01 00:00:00')"
        )
    )

    await FTSRebuilder.rebuild(db_session)

    rowids = [
        row[0]
        for row in (
            await db_session.execute(text("SELECT rowid FROM recipes_fts"))
        ).fetchall()
    ]
    assert 903 in rowids
    assert 904 not in rowids


@pytest.mark.asyncio
async def test_reindex_one_replaces_existing_fts_row(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO households "
            "(id, name, slug, invite_code, default_size, default_public) "
            "VALUES (905, 'H5', 'h5', 'inv-905', 4, 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            "VALUES (905, 'V1', 4, 905)"
        )
    )
    await FTSRebuilder.reindex_one(db_session, 905)

    await db_session.execute(text("UPDATE recipes SET title = 'V2' WHERE id = 905"))
    await FTSRebuilder.reindex_one(db_session, 905)

    rows = (
        await db_session.execute(
            text("SELECT rowid, title FROM recipes_fts WHERE rowid = 905")
        )
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "V2"


@pytest.mark.asyncio
async def test_delete_one_removes_row(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO households "
            "(id, name, slug, invite_code, default_size, default_public) "
            "VALUES (906, 'H6', 'h6', 'inv-906', 4, 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            "VALUES (906, 'Doomed', 4, 906)"
        )
    )
    await FTSRebuilder.reindex_one(db_session, 906)

    await FTSRebuilder.delete_one(db_session, 906)

    rows = (
        await db_session.execute(
            text("SELECT rowid FROM recipes_fts WHERE rowid = 906")
        )
    ).fetchall()
    assert rows == []
