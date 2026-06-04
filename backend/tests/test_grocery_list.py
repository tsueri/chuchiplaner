import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredient import Ingredient


async def _register(client: AsyncClient, username: str = "testuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    return {"cookies": resp.cookies, "data": resp.json()}


async def _create_ingredient(
    client: AsyncClient, cookies, name: str = "Zwiebel"
) -> dict:
    resp = await client.post(
        "/api/ingredients", json={"name": name}, cookies=cookies
    )
    return resp.json()


async def _create_recipe(
    client: AsyncClient,
    cookies,
    title: str = "Test Recipe",
    ingredients: list[dict] | None = None,
    servings: int = 1,
) -> dict:
    body: dict = {
        "title": title,
        "instructions": "Cook it.",
        "servings": servings,
    }
    if ingredients is not None:
        body["ingredients"] = ingredients
    resp = await client.post("/api/recipes", json=body, cookies=cookies)
    return resp.json()


async def _create_plan(
    client: AsyncClient, cookies, year, week
) -> dict:
    resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    return resp.json()


async def _plan_recipe(
    client: AsyncClient, cookies, year, week, day, meal, recipe_id
) -> None:
    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={"slots": [
            {"day_of_week": day, "meal_type": meal, "recipe_id": recipe_id}
        ]},
        cookies=cookies,
    )


async def _get_grocery_list(
    client: AsyncClient, cookies, plan_id: int
) -> dict:
    resp = await client.get(
        "/api/grocery-list", params={"week_plan_id": plan_id}, cookies=cookies
    )
    return resp.json()


async def _get_current_iso() -> tuple[int, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Zurich"))
    iso = now.isocalendar()
    return (iso[0], iso[1])


# ----- GET grocery list for a week plan -----


@pytest.mark.asyncio
async def test_empty_week_plan_returns_empty_grocery_list(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    plan = await _create_plan(client, cookies, year, week)
    data = await _get_grocery_list(client, cookies, plan["id"])

    assert data["household_id"] is not None
    assert data["week_plan_id"] == plan["id"]
    assert data["items"] == []


@pytest.mark.asyncio
async def test_grocery_list_generates_from_planned_recipes(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Tomate")
    recipe = await _create_recipe(
        client, cookies, "Tomatensuppe",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 500, "unit": "g", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Tomate"
    assert data["items"][0]["quantity"] == 500.0
    assert data["items"][0]["unit"] == "g"
    assert data["items"][0]["checked"] is False
    breakdown = data["items"][0]["recipe_breakdown"]
    assert len(breakdown) == 1
    assert breakdown[0]["recipe_title"] == "Tomatensuppe"


@pytest.mark.asyncio
async def test_grocery_list_deducts_inventory(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Mehl")
    recipe = await _create_recipe(
        client, cookies, "Pfannkuchen",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 300, "unit": "g", "order_index": 0}
        ],
    )

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing["id"],
            "quantity": 100,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Mehl"
    assert data["items"][0]["quantity"] == 200.0


@pytest.mark.asyncio
async def test_grocery_list_item_fully_covered_not_included(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery4")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Zucker")
    recipe = await _create_recipe(
        client, cookies, "Kuchen",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 200, "unit": "g", "order_index": 0}
        ],
    )

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing["id"],
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 0


# ----- CRUD items -----


@pytest.mark.asyncio
async def test_update_grocery_list_item(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery5")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Eier")
    recipe = await _create_recipe(
        client, cookies, "Omelett",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 6, "unit": "St\u00fcck",
             "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    item_id = data["items"][0]["id"]

    put_resp = await client.put(
        f"/api/grocery-list/items/{item_id}",
        json={"quantity": 12, "checked": True},
        cookies=cookies,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["quantity"] == 12.0
    assert put_resp.json()["checked"] is True


@pytest.mark.asyncio
async def test_add_manual_item(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery6")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    plan = await _create_plan(client, cookies, year, week)
    data = await _get_grocery_list(client, cookies, plan["id"])
    list_id = data["id"]

    add_resp = await client.post(
        "/api/grocery-list/items",
        params={"list_id": list_id},
        json={"name": "Servietten", "quantity": 1, "unit": "Packung"},
        cookies=cookies,
    )
    assert add_resp.status_code == 201
    added = add_resp.json()
    assert added["name"] == "Servietten"
    assert added["quantity"] == 1.0
    assert added["unit"] == "Packung"


@pytest.mark.asyncio
async def test_delete_item(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery7")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "K\u00e4se")
    recipe = await _create_recipe(
        client, cookies, "K\u00e4seplatte",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 200, "unit": "g", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    item_id = data["items"][0]["id"]

    del_resp = await client.delete(
        f"/api/grocery-list/items/{item_id}", cookies=cookies
    )
    assert del_resp.status_code == 204

    data2 = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data2["items"]) == 0


# ----- Complete / transfer to inventory -----


@pytest.mark.asyncio
async def test_complete_transfers_to_inventory(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery8")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Butter")
    recipe = await _create_recipe(
        client, cookies, "Guetzli",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 250, "unit": "g", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    list_id = data["id"]
    items = data["items"]

    butter_item = next(i for i in items if i["name"] == "Butter")
    await client.put(
        f"/api/grocery-list/items/{butter_item['id']}",
        json={"checked": True},
        cookies=cookies,
    )

    comp_resp = await client.post(
        "/api/grocery-list/complete",
        params={"list_id": list_id},
        cookies=cookies,
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["transferred_count"] == 1

    inv_resp = await client.get(
        "/api/inventory", params={"category": "raw"}, cookies=cookies
    )
    items = inv_resp.json()
    assert len(items) == 1
    assert items[0]["ingredient_name"] == "Butter"
    assert items[0]["quantity"] == 250.0

    # After completion, a new empty list is returned for the same plan
    data2 = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data2["items"]) == 0
    assert data2["completed_at"] is None


@pytest.mark.asyncio
async def test_checked_items_transferred(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery9")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing1 = await _create_ingredient(client, cookies, "Mehl")
    ing2 = await _create_ingredient(client, cookies, "Eier")
    recipe = await _create_recipe(
        client, cookies, "Pasta",
        ingredients=[
            {"ingredient_id": ing1["id"], "quantity": 500, "unit": "g",
             "order_index": 0},
            {"ingredient_id": ing2["id"], "quantity": 3, "unit": "St\u00fcck",
             "order_index": 1},
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    list_id = data["id"]
    items = data["items"]

    mehl_item = next(i for i in items if i["name"] == "Mehl")
    await client.put(
        f"/api/grocery-list/items/{mehl_item['id']}",
        json={"checked": True},
        cookies=cookies,
    )

    comp_resp = await client.post(
        "/api/grocery-list/complete",
        params={"list_id": list_id},
        cookies=cookies,
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["transferred_count"] == 1

    inv_resp = await client.get(
        "/api/inventory", params={"category": "raw"}, cookies=cookies
    )
    items_inv = inv_resp.json()
    assert len(items_inv) == 1
    assert items_inv[0]["ingredient_name"] == "Mehl"


# ----- Regenerate -----


@pytest.mark.asyncio
async def test_regenerate_updates_items(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery10")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Kartoffel")
    recipe = await _create_recipe(
        client, cookies, "Stocki",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 1000, "unit": "g",
             "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing["id"],
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    regen_resp = await client.post(
        "/api/grocery-list/generate",
        params={"week_plan_id": plan["id"]},
        cookies=cookies,
    )
    regen_data = regen_resp.json()
    assert len(regen_data["items"]) == 1
    assert regen_data["items"][0]["quantity"] == 500.0


# ----- Share -----


@pytest.mark.asyncio
async def test_get_share_token_creates_token(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery11")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    plan = await _create_plan(client, cookies, year, week)
    data = await _get_grocery_list(client, cookies, plan["id"])
    list_id = data["id"]

    share_resp = await client.get(
        f"/api/grocery-list/{list_id}/share", cookies=cookies
    )
    assert share_resp.status_code == 200
    token = share_resp.json()["token"]
    assert len(token) > 0


@pytest.mark.asyncio
async def test_shared_list_accessible_without_auth(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery12")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Salat")
    recipe = await _create_recipe(
        client, cookies, "Salatteller",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 300, "unit": "g", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    list_id = data["id"]

    share_resp = await client.get(
        f"/api/grocery-list/{list_id}/share", cookies=cookies
    )
    token = share_resp.json()["token"]

    pub_resp = await client.get(
        f"/api/grocery-list/share/{token}"
    )
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert pub_data["household_name"] is not None
    assert len(pub_data["items"]) == 1
    assert pub_data["items"][0]["name"] == "Salat"


# ----- Auth and error cases -----


@pytest.mark.asyncio
async def test_grocery_list_requires_auth(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/grocery-list")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_nonexistent_item_returns_404(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery13")
    cookies = reg["cookies"]

    resp = await client.put(
        "/api/grocery-list/items/99999",
        json={"quantity": 5},
        cookies=cookies,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grocery_list_without_plan_is_empty(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery15")
    cookies = reg["cookies"]

    resp = await client.get("/api/grocery-list", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["week_plan_id"] is None
    assert data["items"] == []


@pytest.mark.asyncio
async def test_multiple_recipes_aggregate_ingredients(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery16")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Zwiebel")
    recipe1 = await _create_recipe(
        client, cookies, "Suppe",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 200, "unit": "g", "order_index": 0}
        ],
    )
    recipe2 = await _create_recipe(
        client, cookies, "Salat",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 100, "unit": "g", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe1["id"])
    await _plan_recipe(client, cookies, year, week, 1, "lunch", recipe2["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Zwiebel"
    assert data["items"][0]["quantity"] == 300.0
    breakdown = data["items"][0]["recipe_breakdown"]
    assert len(breakdown) == 2


@pytest.mark.asyncio
async def test_delete_nonexistent_item_returns_404(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery17")
    cookies = reg["cookies"]

    resp = await client.delete(
        "/api/grocery-list/items/99999", cookies=cookies
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_add_item_to_completed_list(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery18")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    plan = await _create_plan(client, cookies, year, week)
    data = await _get_grocery_list(client, cookies, plan["id"])
    list_id = data["id"]

    await client.post(
        "/api/grocery-list/complete",
        params={"list_id": list_id},
        cookies=cookies,
    )

    resp = await client.post(
        "/api/grocery-list/items",
        params={"list_id": list_id},
        json={"name": "Extra", "quantity": 1, "unit": "St\u00fcck"},
        cookies=cookies,
    )
    assert resp.status_code == 400


# ----- Cross-dimension matching (ingredient-aware conversions) -----


@pytest.mark.asyncio
async def test_el_to_grams_deducts_inventory_cross_dimension(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(client, "grocery19")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Mehl")
    result = await db_session.execute(
        select(Ingredient).where(Ingredient.id == ing["id"])
    )
    mehl = result.scalar_one()
    mehl.grams_per_el = 10.0
    await db_session.flush()

    recipe = await _create_recipe(
        client, cookies, "Pfannkuchen",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 500, "unit": "g", "order_index": 0}
        ],
    )

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing["id"],
            "quantity": 2,
            "unit": "EL",
            "category": "raw",
        },
        cookies=cookies,
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Mehl"
    assert data["items"][0]["quantity"] == 480.0
    assert data["items"][0]["unit"] == "g"


@pytest.mark.asyncio
async def test_tl_to_grams_cross_dimension_deduction(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(client, "grocery20")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Salz")
    result = await db_session.execute(
        select(Ingredient).where(Ingredient.id == ing["id"])
    )
    salz = result.scalar_one()
    salz.grams_per_tl = 5.0
    await db_session.flush()

    recipe = await _create_recipe(
        client, cookies, "Brot",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 10, "unit": "TL", "order_index": 0}
        ],
    )

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing["id"],
            "quantity": 20,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Salz"
    assert data["items"][0]["quantity"] == 30.0
    assert data["items"][0]["unit"] == "g"


@pytest.mark.asyncio
async def test_no_conversion_preserves_old_el_ml_behavior(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "grocery21")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Öl")
    recipe = await _create_recipe(
        client, cookies, "Dressing",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 2, "unit": "EL", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 30.0
    assert data["items"][0]["unit"] == "ml"


@pytest.mark.asyncio
async def test_recipe_breakdown_shows_g_unit_when_el_converted_to_g(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(client, "grocery22")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Honig")
    result = await db_session.execute(
        select(Ingredient).where(Ingredient.id == ing["id"])
    )
    honig = result.scalar_one()
    honig.grams_per_el = 20.0
    await db_session.flush()

    recipe = await _create_recipe(
        client, cookies, "Honigkuchen",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 3, "unit": "EL", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 60.0
    assert data["items"][0]["unit"] == "g"
    breakdown = data["items"][0]["recipe_breakdown"]
    assert len(breakdown) == 1
    assert breakdown[0]["unit"] == "g"
    assert breakdown[0]["quantity"] == 60.0


@pytest.mark.asyncio
async def test_mixed_units_aggregate_correctly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(client, "grocery23")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Mehl")
    result = await db_session.execute(
        select(Ingredient).where(Ingredient.id == ing["id"])
    )
    mehl = result.scalar_one()
    mehl.grams_per_el = 10.0
    await db_session.flush()

    recipe1 = await _create_recipe(
        client, cookies, "Kuchen",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 200, "unit": "g", "order_index": 0}
        ],
    )
    recipe2 = await _create_recipe(
        client, cookies, "Pfannkuchen",
        ingredients=[
            {"ingredient_id": ing["id"], "quantity": 3, "unit": "EL", "order_index": 0}
        ],
    )

    plan = await _create_plan(client, cookies, year, week)
    await _plan_recipe(client, cookies, year, week, 0, "lunch", recipe1["id"])
    await _plan_recipe(client, cookies, year, week, 1, "lunch", recipe2["id"])

    data = await _get_grocery_list(client, cookies, plan["id"])
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Mehl"
    assert data["items"][0]["quantity"] == 230.0
    assert data["items"][0]["unit"] == "g"
