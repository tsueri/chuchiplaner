import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.matching_engine import (
    IngredientAvailability,
    MatchingEngine,
    RecipeInfo,
    RecipeIngredientNeed,
)


def _make_inventory(
    **ingredients: tuple[float, float, float, bool],
) -> dict[int, IngredientAvailability]:
    result: dict[int, IngredientAvailability] = {}
    for key, (grams, ml, pcs, expiring) in ingredients.items():
        parts = key.split(":", 1)
        ing_id = int(parts[0])
        result[ing_id] = IngredientAvailability(
            ingredient_id=ing_id,
            name=parts[1] if len(parts) > 1 else f"Ingredient {ing_id}",
            grams=grams,
            milliliters=ml,
            pieces=pcs,
            has_expiring=expiring,
        )
    return result


def _make_recipe(
    recipe_id: int, title: str, **ingredients: tuple[float, float, float],
) -> RecipeInfo:
    needs: list[RecipeIngredientNeed] = []
    for key, (grams, ml, pcs) in ingredients.items():
        parts = key.split(":", 1)
        ing_id = int(parts[0])
        name = parts[1] if len(parts) > 1 else f"Ingredient {ing_id}"
        needs.append(
            RecipeIngredientNeed(
                ingredient_id=ing_id,
                name=name,
                grams=grams,
                milliliters=ml,
                pieces=pcs,
            )
        )
    return RecipeInfo(id=recipe_id, title=title, ingredients=needs)


class TestMatchingEngineExact:
    def test_returns_recipes_with_all_ingredients(self) -> None:
        inv = _make_inventory(
            **{
                "1:Tomato": (500, 0, 0, False),
                "2:Pasta": (300, 0, 0, False),
            },
        )
        r1 = _make_recipe(
            1, "Pasta Sauce",
            **{"1:Tomato": (200, 0, 0), "2:Pasta": (100, 0, 0)},
        )
        r2 = _make_recipe(
            2, "Salad",
            **{"1:Tomato": (100, 0, 0), "3:Lettuce": (50, 0, 0)},
        )

        results = MatchingEngine.suggest(inv, [r1, r2], mode="exact")

        assert len(results) == 1
        assert results[0].recipe_id == 1
        assert results[0].score == 1.0

    def test_no_recipes_when_inventory_empty(self) -> None:
        results = MatchingEngine.suggest({}, [], mode="exact")
        assert results == []

    def test_no_exact_matches_when_ingredient_missing(self) -> None:
        inv = _make_inventory(**{"1:Onion": (100, 0, 0, False)})
        r1 = _make_recipe(
            1, "Soup", **{"1:Onion": (50, 0, 0), "2:Carrot": (50, 0, 0)},
        )
        results = MatchingEngine.suggest(inv, [r1], mode="exact")
        assert results == []

    def test_no_exact_match_when_quantity_insufficient(self) -> None:
        inv = _make_inventory(**{"1:Flour": (100, 0, 0, False)})
        r1 = _make_recipe(1, "Bread", **{"1:Flour": (200, 0, 0)})
        results = MatchingEngine.suggest(inv, [r1], mode="exact")
        assert results == []


class TestMatchingEnginePartial:
    def test_sorted_by_score(self) -> None:
        inv = _make_inventory(
            **{
                "1:Tomato": (500, 0, 0, False),
                "2:Pasta": (300, 0, 0, False),
            },
        )
        r1 = _make_recipe(
            1, "Pasta Sauce",
            **{"1:Tomato": (200, 0, 0), "2:Pasta": (100, 0, 0)},
        )
        r2 = _make_recipe(
            2, "Salad",
            **{"1:Tomato": (100, 0, 0), "3:Lettuce": (50, 0, 0)},
        )

        results = MatchingEngine.suggest(inv, [r1, r2], mode="partial")

        assert len(results) == 2
        assert results[0].recipe_id == 1
        assert results[0].score == 1.0
        assert results[1].recipe_id == 2
        assert results[1].score == 0.5

    def test_empty_inventory_returns_all_with_score_0(self) -> None:
        r1 = _make_recipe(1, "Bread", **{"1:Flour": (200, 0, 0)})
        r2 = _make_recipe(2, "Soup", **{"2:Water": (500, 0, 0)})

        results = MatchingEngine.suggest({}, [r1, r2], mode="partial")

        assert len(results) == 2
        assert all(r.score == 0.0 for r in results)

    def test_matched_and_total_counts(self) -> None:
        inv = _make_inventory(
            **{
                "1:A": (100, 0, 0, False),
                "2:B": (100, 0, 0, False),
            },
        )
        r1 = _make_recipe(
            1, "Recipe",
            **{"1:A": (50, 0, 0), "2:B": (50, 0, 0), "3:C": (50, 0, 0)},
        )
        results = MatchingEngine.suggest(inv, [r1], mode="partial")
        assert results[0].matched_ingredients == 2
        assert results[0].total_ingredients == 3
        assert results[0].score == 2 / 3


class TestMatchingEngineUrgencyBoost:
    def test_expiring_ranks_higher(self) -> None:
        inv1 = _make_inventory(
            **{
                "1:Chicken": (500, 0, 0, True),
                "2:Rice": (300, 0, 0, False),
            },
        )
        inv2 = _make_inventory(
            **{
                "1:Chicken": (500, 0, 0, False),
                "2:Rice": (300, 0, 0, False),
            },
        )
        r = _make_recipe(
            1, "Chicken Rice",
            **{"1:Chicken": (200, 0, 0), "2:Rice": (100, 0, 0)},
        )

        res1 = MatchingEngine.suggest(inv1, [r], mode="partial")
        res2 = MatchingEngine.suggest(inv2, [r], mode="partial")

        assert res1[0].urgency_boost > 0
        assert res2[0].urgency_boost == 0
        assert res1[0].score > res2[0].score

    def test_expiring_ingredients_listed(self) -> None:
        inv = _make_inventory(
            **{
                "1:Chicken": (500, 0, 0, True),
                "2:Rice": (300, 0, 0, False),
            },
        )
        r = _make_recipe(
            1, "Chicken Rice",
            **{"1:Chicken": (200, 0, 0), "2:Rice": (100, 0, 0)},
        )
        results = MatchingEngine.suggest(inv, [r], mode="partial")
        assert "Chicken" in results[0].expiring_ingredients

    def test_missing_ingredients_listed(self) -> None:
        inv = _make_inventory(**{"1:Tomato": (100, 0, 0, False)})
        r = _make_recipe(
            1, "Salad",
            **{"1:Tomato": (50, 0, 0), "2:Lettuce": (50, 0, 0)},
        )
        results = MatchingEngine.suggest(inv, [r], mode="partial")
        assert "Lettuce" in results[0].missing_ingredients


class TestMatchingEngineIngredientFirst:
    def test_filters_to_recipes_with_ingredient(self) -> None:
        inv = _make_inventory(
            **{
                "1:Zucchini": (500, 0, 0, False),
                "2:Pasta": (300, 0, 0, False),
            },
        )
        r1 = _make_recipe(
            1, "Zucchini Pasta",
            **{"1:Zucchini": (200, 0, 0), "2:Pasta": (100, 0, 0)},
        )
        r2 = _make_recipe(2, "Plain Pasta", **{"2:Pasta": (100, 0, 0)})

        results = MatchingEngine.suggest(
            inv, [r1, r2], mode="ingredient_first", ingredient_filter=1,
        )

        assert len(results) == 1
        assert results[0].recipe_id == 1

    def test_ingredient_first_sorted(self) -> None:
        inv = _make_inventory(
            **{
                "1:Cheese": (500, 0, 0, False),
                "2:Bread": (300, 0, 0, False),
            },
        )
        r1 = _make_recipe(
            1, "Cheese Toast",
            **{"1:Cheese": (100, 0, 0), "2:Bread": (50, 0, 0)},
        )
        r2 = _make_recipe(
            2, "Cheese Soup",
            **{"1:Cheese": (100, 0, 0), "3:Water": (100, 0, 0)},
        )

        results = MatchingEngine.suggest(
            inv, [r1, r2], mode="ingredient_first", ingredient_filter=1,
        )

        assert len(results) == 2
        assert results[0].recipe_id == 1
        assert results[0].score == 1.0
        assert results[1].recipe_id == 2
        assert results[1].score == 0.5


class TestMatchingEngineReservations:
    def test_reserved_subtracted(self) -> None:
        inv = _make_inventory(**{"1:Flour": (500, 0, 0, False)})
        r1 = _make_recipe(1, "Bread 1", **{"1:Flour": (200, 0, 0)})
        r2 = _make_recipe(2, "Bread 2", **{"1:Flour": (400, 0, 0)})

        reservations = {1: (200, 0, 0)}

        results = MatchingEngine.suggest(
            inv, [r1, r2], mode="exact",
            current_plan_reservations=reservations,
        )

        assert len(results) == 1
        assert results[0].recipe_id == 1

    def test_reservations_multiple_dim(self) -> None:
        inv = _make_inventory(
            **{
                "1:Flour": (500, 0, 0, False),
                "2:Oil": (0, 200, 0, False),
            },
        )
        r = _make_recipe(
            1, "Fried Bread",
            **{"1:Flour": (300, 0, 0), "2:Oil": (0, 50, 0)},
        )

        reservations = {1: (200, 0, 0)}

        results = MatchingEngine.suggest(
            inv, [r], mode="exact",
            current_plan_reservations=reservations,
        )
        assert len(results) == 1
        assert results[0].recipe_id == 1


class TestMatchingEngineDietaryFilter:
    def test_excludes_non_matching(self) -> None:
        inv = _make_inventory(
            **{
                "1:Tomato": (500, 0, 0, False),
                "2:Beef": (300, 0, 0, False),
            },
        )
        r1 = RecipeInfo(
            id=1, title="Tomato Soup",
            ingredients=[
                RecipeIngredientNeed(
                    ingredient_id=1, name="Tomato", grams=200,
                ),
            ],
            tag_names=["Vegetarisch"],
        )
        r2 = RecipeInfo(
            id=2, title="Beef Stew",
            ingredients=[
                RecipeIngredientNeed(
                    ingredient_id=2, name="Beef", grams=200,
                ),
            ],
            tag_names=["Fleisch"],
        )

        results = MatchingEngine.suggest(
            inv, [r1, r2], mode="partial", dietary_filter="Vegetarisch",
        )

        assert len(results) == 1
        assert results[0].recipe_id == 1

    def test_case_insensitive(self) -> None:
        inv = _make_inventory(**{"1:Tomato": (500, 0, 0, False)})
        r1 = RecipeInfo(
            id=1, title="Soup",
            ingredients=[
                RecipeIngredientNeed(
                    ingredient_id=1, name="Tomato", grams=200,
                ),
            ],
            tag_names=["Vegetarisch"],
        )

        results = MatchingEngine.suggest(
            inv, [r1], mode="partial", dietary_filter="vegetarisch",
        )
        assert len(results) == 1


# ----- API integration tests -----


async def _setup_match_data(
    client: AsyncClient,
    db_session: AsyncSession,
    username: str = "matchuser",
) -> tuple[dict, int, int, int, int]:
    from sqlalchemy import text

    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    cookies = resp.cookies

    await db_session.execute(
        text("INSERT INTO ingredients (id, name) VALUES (1001, 'Tomate')")
    )
    await db_session.execute(
        text("INSERT INTO ingredients (id, name) VALUES (1002, 'Pasta')")
    )
    await db_session.execute(
        text("INSERT INTO ingredients (id, name) VALUES (1003, 'Salat')")
    )
    household_id = resp.json()["household_id"]

    await db_session.execute(
        text(
            "INSERT INTO inventory_items "
            "(household_id, ingredient_id, quantity, unit, expiry_date, category) "
            f"VALUES ({household_id}, 1001, 500, 'g', NULL, 'raw')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO inventory_items "
            "(household_id, ingredient_id, quantity, unit, expiry_date, category) "
            f"VALUES ({household_id}, 1002, 300, 'g', NULL, 'raw')"
        )
    )

    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            f"VALUES (2001, 'Pasta Sauce', 4, {household_id})"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text, name) "
            "VALUES (2001, 0, 'Cook.', NULL)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (2001, 1001, 200, 'g', 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (2001, 1002, 100, 'g', 1)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes_fts (rowid, title, description, steps, "
            "ingredients, keywords, author, tags) "
            "VALUES (2001, 'Pasta Sauce', '', 'Cook.', '', '', '', '')"
        )
    )

    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            f"VALUES (2002, 'Salad', 2, {household_id})"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text, name) "
            "VALUES (2002, 0, 'Mix.', NULL)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (2002, 1001, 100, 'g', 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (2002, 1003, 50, 'g', 1)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes_fts (rowid, title, description, steps, "
            "ingredients, keywords, author, tags) "
            "VALUES (2002, 'Salad', '', 'Mix.', '', '', '', '')"
        )
    )

    await db_session.commit()

    return (cookies, 1001, 1002, 2001, 2002)


@pytest.mark.asyncio
async def test_match_exact_mode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cookies, _, _, r_full, _ = await _setup_match_data(
        client, db_session, "exactuser",
    )

    resp = await client.post(
        "/api/match", json={"mode": "exact"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    ids = [s["recipe_id"] for s in suggestions]
    assert r_full in ids
    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_match_partial_mode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cookies, _, _, r_full, r_partial = await _setup_match_data(
        client, db_session, "partialuser",
    )

    resp = await client.post(
        "/api/match", json={"mode": "partial"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 2
    assert suggestions[0]["recipe_id"] == r_full
    assert suggestions[0]["score"] == 1.0
    assert suggestions[1]["recipe_id"] == r_partial
    assert suggestions[1]["score"] == 0.5


@pytest.mark.asyncio
async def test_match_ingredient_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cookies, _, ing_pasta, r_full, _ = await _setup_match_data(
        client, db_session, "ingfirstuser",
    )

    resp = await client.post(
        "/api/match",
        json={"mode": "ingredient_first", "ingredient_filter": ing_pasta},
        cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["recipe_id"] == r_full


@pytest.mark.asyncio
async def test_match_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/match", json={"mode": "exact"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_match_empty_inventory(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={"username": "emptyuser", "password": "secret123"},
    )
    cookies = resp.cookies

    resp2 = await client.post(
        "/api/match", json={"mode": "exact"}, cookies=cookies,
    )
    assert resp2.status_code == 200
    assert resp2.json()["suggestions"] == []


@pytest.mark.asyncio
async def test_match_with_dietary_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cookies, _, _, r_full, _ = await _setup_match_data(
        client, db_session, "dietuser",
    )
    from sqlalchemy import text

    await db_session.execute(
        text(
            "INSERT INTO tags (id, name, \"group\", household_id) "
            "VALUES (3001, 'Pasta-Liebe', 'ingredient', NULL)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_tags (recipe_id, tag_id) "
            "VALUES (2001, 3001)"
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/match",
        json={"mode": "partial", "dietary_filter": 3001},
        cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["recipe_id"] == r_full


@pytest.mark.asyncio
async def test_match_score_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cookies, _, _, _, r_partial = await _setup_match_data(
        client, db_session, "scoreuser",
    )

    resp = await client.post(
        "/api/match", json={"mode": "partial"}, cookies=cookies,
    )
    data = resp.json()
    salad = [
        s for s in data["suggestions"] if s["recipe_id"] == r_partial
    ][0]
    assert salad["score"] == 0.5
    assert salad["matched_ingredients"] == 1
    assert salad["total_ingredients"] == 2
    assert "Salat" in salad["missing_ingredients"]
    assert salad["urgency_boost"] == 0.0


@pytest.mark.asyncio
async def test_match_dietary_filter_with_seeded_diet_tag(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cookies, _, _, r_full, _ = await _setup_match_data(
        client, db_session, "dietenduser",
    )
    from sqlalchemy import text

    diet_tag_result = await db_session.execute(
        text("SELECT id FROM tags WHERE name = 'VegetarianDiet'")
    )
    diet_tag_id = diet_tag_result.scalar_one()

    await db_session.execute(
        text(
            "INSERT INTO recipe_tags (recipe_id, tag_id) "
            f"VALUES ({r_full}, {diet_tag_id})"
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/match",
        json={"mode": "partial", "dietary_filter": diet_tag_id},
        cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["recipe_id"] == r_full


# ----- Cross-dimension matching tests -----


async def _setup_cross_dim_data(
    client: AsyncClient,
    db_session: AsyncSession,
    username: str,
) -> tuple[dict, int, int, int, int]:
    """Setup data for cross-dimension matching tests.

    Creates:
      - ingredient 2001 "Mehl" with grams_per_el=10
      - ingredient 2002 "Milch" without conversions (NULL)
      - inventory: 100g Mehl, 100ml Milch
      - recipe R1: "Pasta" needs 1 EL Mehl (=10g after conversion)
      - recipe R2: "Brot" needs 11 EL Mehl (=110g after conversion, too much)
      - recipe R3: "Milchshake" needs 1 EL Milch (=15ml old behaviour)
    """
    from sqlalchemy import text

    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    cookies = resp.cookies
    household_id = resp.json()["household_id"]

    await db_session.execute(
        text(
            "INSERT INTO ingredients (id, name, grams_per_el) "
            "VALUES (2001, 'Mehl', 10)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO ingredients (id, name) "
            "VALUES (2002, 'Milch')"
        )
    )

    await db_session.execute(
        text(
            "INSERT INTO inventory_items "
            "(household_id, ingredient_id, quantity, unit, expiry_date, category) "
            f"VALUES ({household_id}, 2001, 100, 'g', NULL, 'raw')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO inventory_items "
            "(household_id, ingredient_id, quantity, unit, expiry_date, category) "
            f"VALUES ({household_id}, 2002, 100, 'ml', NULL, 'raw')"
        )
    )

    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            f"VALUES (3001, 'Pasta', 4, {household_id})"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text, name) "
            "VALUES (3001, 0, 'Cook.', NULL)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (3001, 2001, 1, 'EL', 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes_fts (rowid, title, description, steps, "
            "ingredients, keywords, author, tags) "
            "VALUES (3001, 'Pasta', '', 'Cook.', '', '', '', '')"
        )
    )

    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            f"VALUES (3002, 'Brot', 4, {household_id})"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text, name) "
            "VALUES (3002, 0, 'Bake.', NULL)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (3002, 2001, 11, 'EL', 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes_fts (rowid, title, description, steps, "
            "ingredients, keywords, author, tags) "
            "VALUES (3002, 'Brot', '', 'Bake.', '', '', '', '')"
        )
    )

    await db_session.execute(
        text(
            "INSERT INTO recipes (id, title, servings, household_id) "
            f"VALUES (3003, 'Milchshake', 2, {household_id})"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_steps (recipe_id, position, text, name) "
            "VALUES (3003, 0, 'Mix.', NULL)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipe_ingredients "
            "(recipe_id, ingredient_id, quantity, unit, order_index) "
            "VALUES (3003, 2002, 1, 'EL', 0)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO recipes_fts (rowid, title, description, steps, "
            "ingredients, keywords, author, tags) "
            "VALUES (3003, 'Milchshake', '', 'Mix.', '', '', '', '')"
        )
    )

    await db_session.commit()
    return (cookies, 2001, 2002, 3001, 3002)


@pytest.mark.asyncio
async def test_cross_dimension_el_to_g_matches(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Recipe with 1 EL Mehl (10g after conversion) matches 100g inventory."""
    cookies, _, _, r_pasta, _ = await _setup_cross_dim_data(
        client, db_session, "xdimuser1",
    )

    resp = await client.post(
        "/api/match", json={"mode": "exact"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    ids = [s["recipe_id"] for s in suggestions]
    assert r_pasta in ids
    pasta = [s for s in suggestions if s["recipe_id"] == r_pasta][0]
    assert pasta["score"] == 1.0
    assert pasta["matched_ingredients"] == 1
    assert pasta["total_ingredients"] == 1
    assert pasta["missing_ingredients"] == []


@pytest.mark.asyncio
async def test_cross_dimension_el_to_g_insufficient(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Recipe with 11 EL Mehl (110g) is UNSATISFIED against 100g inventory."""
    cookies, _, _, _, r_brot = await _setup_cross_dim_data(
        client, db_session, "xdimuser2",
    )

    resp = await client.post(
        "/api/match", json={"mode": "exact"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    ids = [s["recipe_id"] for s in suggestions]
    assert r_brot not in ids


@pytest.mark.asyncio
async def test_cross_dimension_expiring_urgency(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Expiring EL inventory should trigger urgency boost."""
    from sqlalchemy import text

    cookies, _, _, r_pasta, _ = await _setup_cross_dim_data(
        client, db_session, "xdimuser3",
    )

    household_id_result = await db_session.execute(
        text("SELECT household_id FROM inventory_items LIMIT 1")
    )
    household_id = household_id_result.scalar_one()

    await db_session.execute(
        text(
            "INSERT INTO inventory_items "
            "(household_id, ingredient_id, quantity, unit, expiry_date, category) "
            f"VALUES ({household_id}, 2001, 5, 'g', DATE('now', '+2 days'), 'raw')"
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/match", json={"mode": "partial"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    pasta = [s for s in suggestions if s["recipe_id"] == r_pasta][0]
    assert pasta["urgency_boost"] > 0
    assert "Mehl" in pasta["expiring_ingredients"]


@pytest.mark.asyncio
async def test_cross_dimension_no_conversion_fallback(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ingredient without conversion: EL falls back to 15ml."""
    cookies, _, _, _, _ = await _setup_cross_dim_data(
        client, db_session, "xdimuser4",
    )

    resp = await client.post(
        "/api/match", json={"mode": "exact"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    titles = [s["title"] for s in suggestions]
    assert "Milchshake" in titles


@pytest.mark.asyncio
async def test_cross_dimension_partial_mode_score(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cross-dimension match counts toward matched_ingredients in partial mode."""
    cookies, _, _, r_pasta, _ = await _setup_cross_dim_data(
        client, db_session, "xdimuser5",
    )

    resp = await client.post(
        "/api/match", json={"mode": "partial"}, cookies=cookies,
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    pasta = [s for s in suggestions if s["recipe_id"] == r_pasta][0]
    assert pasta["matched_ingredients"] == 1
    assert pasta["total_ingredients"] == 1
    assert pasta["score"] == 1.0
