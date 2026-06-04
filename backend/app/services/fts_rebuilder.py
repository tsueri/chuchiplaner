from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

COLUMNS: tuple[str, ...] = (
    "title",
    "description",
    "steps",
    "ingredients",
    "keywords",
    "author",
    "tags",
)

WEIGHTS: dict[str, float] = {
    "title": 1.0,
    "description": 3.0,
    "steps": 3.0,
    "ingredients": 5.0,
    "keywords": 1.0,
    "author": 1.0,
    "tags": 1.0,
}


class FTSRebuilder:
    """Single source of truth for the ``recipes_fts`` virtual table.

    The table has seven columns: title, description, steps, ingredients,
    keywords, author, tags. Each column is populated by joining the corresponding
    ORM tables (steps text, ingredient names, tag names) and concatenating with
    spaces. Empty fields are stored as the empty string, never NULL — the FTS5
    MATCH operator treats both identically, but the explicit empty string keeps
    the rebuild SQL simple.

    The bm25 weights drive ``GET /api/recipes?search=...`` ordering: an FTS hit
    in ``ingredients`` ranks above a hit in ``steps`` or ``description``, which
    rank above a hit in ``title``. The ``keywords``, ``author`` and ``tags``
    columns are still matched but don't carry boost weight.
    """

    COLUMNS = COLUMNS
    WEIGHTS = WEIGHTS

    @classmethod
    def weights_sql(cls) -> str:
        """Return the bm25 weights as a comma-separated SQL fragment.

        Used in the search endpoint as ``bm25(recipes_fts, {weights_sql()})``.
        """
        return ", ".join(f"{cls.WEIGHTS[c]}" for c in cls.COLUMNS)

    @staticmethod
    async def rebuild(db: AsyncSession) -> None:
        """Drop and recreate ``recipes_fts``, then repopulate from the joined
        live recipe set.

        The migration that introduced the multi-column FTS schema runs the same
        rebuild inline; this method is the runtime equivalent that the search
        endpoint, admin commands, or future schema changes can call.
        """
        await db.execute(text("DROP TABLE IF EXISTS recipes_fts"))
        await db.execute(
            text(
                "CREATE VIRTUAL TABLE recipes_fts USING fts5("
                "title, description, steps, ingredients, "
                "keywords, author, tags)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO recipes_fts(rowid, title, description, steps, "
                "ingredients, keywords, author, tags) "
                "SELECT r.id, r.title, COALESCE(r.description, ''), "
                "COALESCE((SELECT GROUP_CONCAT(text, ' ') FROM recipe_steps "
                "WHERE recipe_id = r.id), ''), "
                "COALESCE((SELECT GROUP_CONCAT(i.name, ' ') "
                "FROM recipe_ingredients ri JOIN ingredients i "
                "ON ri.ingredient_id = i.id WHERE ri.recipe_id = r.id), ''), "
                "COALESCE(r.keywords, ''), COALESCE(r.author, ''), "
                "COALESCE((SELECT GROUP_CONCAT(t.name, ' ') "
                "FROM recipe_tags rt JOIN tags t ON rt.tag_id = t.id "
                "WHERE rt.recipe_id = r.id), '') "
                "FROM recipes r WHERE r.deleted_at IS NULL"
            )
        )

    @staticmethod
    async def row_payload(
        db: AsyncSession, recipe_id: int
    ) -> dict[str, object]:
        """Build the FTS row payload for a single recipe by querying the join.

        Independent of in-memory ORM relationship state, so create / update
        handlers can call this immediately after ``db.flush()`` without having
        to refresh the parent recipe to pick up freshly-added rows.
        """
        row = (
            await db.execute(
                text(
                    "SELECT r.id, r.title, COALESCE(r.description, ''), "
                    "COALESCE((SELECT GROUP_CONCAT(text, ' ') "
                    "FROM recipe_steps WHERE recipe_id = r.id), ''), "
                    "COALESCE((SELECT GROUP_CONCAT(i.name, ' ') "
                    "FROM recipe_ingredients ri JOIN ingredients i "
                    "ON ri.ingredient_id = i.id "
                    "WHERE ri.recipe_id = r.id), ''), "
                    "COALESCE(r.keywords, ''), COALESCE(r.author, ''), "
                    "COALESCE((SELECT GROUP_CONCAT(t.name, ' ') "
                    "FROM recipe_tags rt JOIN tags t ON rt.tag_id = t.id "
                    "WHERE rt.recipe_id = r.id), '') "
                    "FROM recipes r WHERE r.id = :id"
                ),
                {"id": recipe_id},
            )
        ).first()
        if row is None:
            raise ValueError(f"Recipe {recipe_id} not found")
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "steps": row[3],
            "ingredients": row[4],
            "keywords": row[5],
            "author": row[6],
            "tags": row[7],
        }

    @staticmethod
    async def reindex_one(db: AsyncSession, recipe_id: int) -> None:
        """Delete and re-insert a single recipe's row in ``recipes_fts``.

        Called by ``create_recipe`` / ``update_recipe`` after the row's
        relationships have been flushed.
        """
        payload = await FTSRebuilder.row_payload(db, recipe_id)
        await db.execute(
            text("DELETE FROM recipes_fts WHERE rowid = :id"),
            {"id": recipe_id},
        )
        await db.execute(
            text(
                "INSERT INTO recipes_fts(rowid, title, description, steps, "
                "ingredients, keywords, author, tags) "
                "VALUES (:id, :title, :description, :steps, "
                ":ingredients, :keywords, :author, :tags)"
            ),
            payload,
        )

    @staticmethod
    async def delete_one(db: AsyncSession, recipe_id: int) -> None:
        """Remove a single recipe's row from ``recipes_fts``."""
        await db.execute(
            text("DELETE FROM recipes_fts WHERE rowid = :id"),
            {"id": recipe_id},
        )
