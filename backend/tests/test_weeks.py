import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household import Household
from app.services.week_plan import get_or_create_plan


async def _register(client: AsyncClient, username: str = "testuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    return {"cookies": resp.cookies, "data": resp.json()}


async def _create_ingredient(
    client: AsyncClient,
    cookies,
    name: str = "Zwiebel",
) -> dict:
    resp = await client.post(
        "/api/ingredients", json={"name": name}, cookies=cookies
    )
    return resp.json()


async def _create_recipe(
    client: AsyncClient,
    cookies,
    title: str = "Test Recipe",
) -> dict:
    body = {
        "title": title,
        "instructions": "Cook it.",
        "servings": 4,
    }
    resp = await client.post("/api/recipes", json=body, cookies=cookies)
    return resp.json()


async def _get_current_iso() -> tuple[int, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Zurich"))
    iso = now.isocalendar()
    return (iso[0], iso[1])


# ----- Basic week plan creation -----


@pytest.mark.asyncio
async def test_create_week_plan_creates_28_slots(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == year
    assert data["iso_week"] == week
    assert data["household_id"] is not None
    assert len(data["slots"]) == 28

    days = {s["day_of_week"] for s in data["slots"]}
    assert days == set(range(7))
    meal_types = {s["meal_type"] for s in data["slots"]}
    assert meal_types == {"breakfast", "lunch", "dinner", "dessert"}


@pytest.mark.asyncio
async def test_create_duplicate_week_returns_existing(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    resp1 = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    assert resp1.status_code == 200
    first_id = resp1.json()["id"]

    resp2 = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == first_id


# ----- Get week by year/iso_week -----


@pytest.mark.asyncio
async def test_get_week_plan(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == year
    assert data["iso_week"] == week
    assert len(data["slots"]) == 28


@pytest.mark.asyncio
async def test_get_nonexistent_week_returns_404(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser4")
    cookies = reg["cookies"]

    resp = await client.get("/api/weeks/1999/1", cookies=cookies)
    assert resp.status_code == 404


# ----- Plan recipe onto a slot -----


@pytest.mark.asyncio
async def test_plan_recipe_on_slot(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser5")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Pasta")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "lunch",
                "recipe_id": recipe["id"],
                "portions": 4,
            }]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    get_data = get_resp.json()
    updated_slot = next(
        s for s in get_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    assert updated_slot["recipe_id"] == recipe["id"]
    assert updated_slot["recipe_title"] == "Pasta"
    assert updated_slot["portions"] == 4


# ----- Unplan recipe from slot -----


@pytest.mark.asyncio
async def test_unplan_recipe_from_slot(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser6")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Salat")

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()

    monday_dinner = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )

    resp = await client.delete(
        f"/api/weeks/{year}/{week}/slots/{monday_dinner['id']}/recipe",
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    get_data = get_resp.json()
    updated_slot = next(
        s for s in get_data["slots"]
        if s["id"] == monday_dinner["id"]
    )
    assert updated_slot["recipe_id"] is None


# ----- Move recipe between slots -----


@pytest.mark.asyncio
async def test_move_recipe_to_another_slot(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser6b")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Risotto")

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()

    monday_lunch = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "lunch",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )

    await client.delete(
        f"/api/weeks/{year}/{week}/slots/{monday_lunch['id']}/recipe",
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slots = get_resp.json()["slots"]

    source = next(
        s for s in slots
        if s["id"] == monday_lunch["id"]
    )
    assert source["recipe_id"] is None

    target = next(
        s for s in slots
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )
    assert target["recipe_id"] == recipe["id"]
    assert target["recipe_title"] == "Risotto"


# ----- Copy from previous week -----


@pytest.mark.asyncio
async def test_copy_from_previous_week(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser7")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Suppe")

    # Use current week as source, next week as target
    next_week = week + 1
    next_year = year

    resp_source = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    assert resp_source.status_code == 200

    put_resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 2,
                "meal_type": "lunch",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )
    assert put_resp.status_code == 200

    get_source = await client.get(
        f"/api/weeks/{year}/{week}", cookies=cookies
    )
    source_slots = get_source.json()["slots"]
    source_wed = next(
        s for s in source_slots
        if s["day_of_week"] == 2 and s["meal_type"] == "lunch"
    )
    assert source_wed["recipe_id"] == recipe["id"]

    resp_new = await client.post(
        "/api/weeks",
        json={
            "year": next_year,
            "iso_week": next_week,
            "copy_from_previous": True,
        },
        cookies=cookies,
    )
    assert resp_new.status_code == 200
    new_slots = resp_new.json()["slots"]
    wed_lunch = next(
        s for s in new_slots
        if s["day_of_week"] == 2 and s["meal_type"] == "lunch"
    )
    assert wed_lunch["recipe_id"] == recipe["id"]


# ----- List weeks -----


@pytest.mark.asyncio
async def test_list_weeks(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser8")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Eintopf")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "lunch",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )

    resp = await client.get("/api/weeks", cookies=cookies)
    assert resp.status_code == 200
    weeks_list = resp.json()
    assert len(weeks_list) >= 1

    current = next(w for w in weeks_list if w["year"] == year and w["iso_week"] == week)
    assert current["planned_count"] >= 1
    assert current["total_slots"] > 0


# ----- Auth guards -----


@pytest.mark.asyncio
async def test_weeks_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/weeks")
    assert resp.status_code == 401

    resp = await client.post("/api/weeks", json={"year": 2025, "iso_week": 1})
    assert resp.status_code == 401

    resp = await client.get("/api/weeks/2025/1")
    assert resp.status_code == 401


# ----- Cannot modify nonexistent week -----


@pytest.mark.asyncio
async def test_update_nonexistent_week_returns_404(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser9")
    cookies = reg["cookies"]

    resp = await client.put(
        "/api/weeks/1999/1/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "lunch",
                "recipe_id": 1,
            }]
        },
        cookies=cookies,
    )
    assert resp.status_code == 404


# ----- Portion scaling -----


@pytest.mark.asyncio
async def test_update_slot_portions(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser10")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 3,
                "meal_type": "dinner",
                "portions": 6,
            }]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    thursday_dinner = next(
        s for s in get_resp.json()["slots"]
        if s["day_of_week"] == 3 and s["meal_type"] == "dinner"
    )
    assert thursday_dinner["portions"] == 6


@pytest.mark.asyncio
async def test_updating_portions_preserves_recipe(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser10b")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Testessen")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "lunch",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "lunch",
                "portions": 8,
            }]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot = next(
        s for s in get_resp.json()["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    assert slot["recipe_id"] == recipe["id"]
    assert slot["portions"] == 8


# ----- Multiple slot update in one request -----


@pytest.mark.asyncio
async def test_bulk_update_slots(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser11")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe1 = await _create_recipe(client, cookies, "Breakfast1")
    recipe2 = await _create_recipe(client, cookies, "Breakfast2")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
        "slots": [
            {
                "day_of_week": 0,
                "meal_type": "breakfast",
                "recipe_id": recipe1["id"],
            },
            {
                "day_of_week": 1,
                "meal_type": "breakfast",
                "recipe_id": recipe2["id"],
            },
        ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slots = get_resp.json()["slots"]
    mon_bf = next(
        s for s in slots
        if s["day_of_week"] == 0 and s["meal_type"] == "breakfast"
    )
    tue_bf = next(
        s for s in slots
        if s["day_of_week"] == 1 and s["meal_type"] == "breakfast"
    )
    assert mon_bf["recipe_id"] == recipe1["id"]
    assert tue_bf["recipe_id"] == recipe2["id"]


# ----- Empty week creation -----


@pytest.mark.asyncio
async def test_create_empty_week(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser12")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week, "copy_from_previous": False},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    for s in data["slots"]:
        assert s["recipe_id"] is None


# ----- Dietary filter per slot -----


@pytest.mark.asyncio
async def test_set_dietary_filter_on_slot(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "weekuser13")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 1,
                "meal_type": "lunch",
                "dietary_filter_tag_id": 1,
            }]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    tue_lunch = next(
        s for s in get_resp.json()["slots"]
        if s["day_of_week"] == 1 and s["meal_type"] == "lunch"
    )
    assert tue_lunch["dietary_filter_tag_id"] == 1


# ----- Cook endpoint -----


@pytest.mark.asyncio
async def test_cook_slot_deducts_inventory(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "cookuser1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Poulet")
    ingredient_id = ing["id"]

    inv_resp = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )
    assert inv_resp.status_code == 201

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pouletgeschnetzeltes",
            "instructions": "Braten.",
            "servings": 4,
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": 400,
                "unit": "g",
            }],
        },
        cookies=cookies,
    )
    assert recipe_resp.status_code == 201
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()

    sunday_dinner = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 6 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 6,
                "meal_type": "dinner",
                "recipe_id": recipe_id,
                "portions": 2,
            }]
        },
        cookies=cookies,
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{sunday_dinner['id']}/cook",
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    cook_data = cook_resp.json()
    assert cook_data["cooked"] is True
    assert len(cook_data["deductions"]) == 1
    ded = cook_data["deductions"][0]
    assert ded["ingredient_name"] == "Poulet"
    assert ded["deducted"] == 200.0
    assert ded["unit"] == "g"

    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["quantity"] == 300.0


@pytest.mark.asyncio
async def test_cook_empty_inventory_quantity_removed(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "cookuser2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Milch")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 200,
            "unit": "ml",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Milchreis",
            "instructions": "Kochen.",
            "servings": 4,
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": 200,
                "unit": "ml",
            }],
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    monday_bf = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "breakfast"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "breakfast",
                "recipe_id": recipe_id,
                "portions": 4,
            }]
        },
        cookies=cookies,
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{monday_bf['id']}/cook",
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    cook_data = cook_resp.json()
    ded = cook_data["deductions"][0]
    assert ded["deducted"] == 200.0

    inv_get = await client.get("/api/inventory", cookies=cookies)
    assert inv_get.status_code == 200
    assert len(inv_get.json()) == 0


@pytest.mark.asyncio
async def test_cook_unplanned_slot_fails(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "cookuser3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    empty_slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{empty_slot['id']}/cook",
        cookies=cookies,
    )
    assert cook_resp.status_code == 400
    assert "recipe" in cook_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cook_already_cooked_slot_fails(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "cookuser4")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Rind")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 1000,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Rindsgulasch",
            "instructions": "Schmoren.",
            "servings": 4,
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": 500,
                "unit": "g",
            }],
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe_id,
            }]
        },
        cookies=cookies,
    )

    cook1 = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        cookies=cookies,
    )
    assert cook1.status_code == 200

    cook2 = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        cookies=cookies,
    )
    assert cook2.status_code == 400
    detail = cook2.json()["detail"].lower()
    assert "bereits" in detail or "already" in detail


# ----- Leftovers endpoint -----


@pytest.mark.asyncio
async def test_create_leftovers(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "leftover1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Bolognese",
            "instructions": "Simmern.",
            "servings": 4,
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe_id,
            }]
        },
        cookies=cookies,
    )

    resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/leftovers",
        json={"portions_count": 3},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingredient_name"] == "Bolognese (Reste)"
    assert data["quantity"] == 3.0
    assert data["unit"] == "Stück"
    assert data["category"] == "cooked"
    assert data["source_recipe_id"] == recipe_id

    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["ingredient_name"] == "Bolognese (Reste)"
    assert items[0]["category"] == "cooked"
    assert items[0]["quantity"] == 3.0


@pytest.mark.asyncio
async def test_leftovers_on_unplanned_slot_fails(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "leftover2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    empty_slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{empty_slot['id']}/leftovers",
        json={"portions_count": 2},
        cookies=cookies,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_leftovers_shown_in_inventory(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "leftover3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Suppe",
            "instructions": "Kochen.",
            "servings": 4,
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 1 and s["meal_type"] == "lunch"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 1,
                "meal_type": "lunch",
                "recipe_id": recipe_id,
            }]
        },
        cookies=cookies,
    )

    await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/leftovers",
        json={"portions_count": 2},
        cookies=cookies,
    )

    cooked_resp = await client.get(
        "/api/inventory", params={"category": "cooked"}, cookies=cookies
    )
    assert cooked_resp.status_code == 200
    items = cooked_resp.json()
    assert len(items) == 1
    assert items[0]["ingredient_name"] == "Suppe (Reste)"
    assert items[0]["source_recipe_id"] == recipe_id


# ----- Meal template syncs to editable week plans -----


@pytest.mark.asyncio
async def test_meal_template_update_syncs_to_existing_week_plan(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "templatesync")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
                {
                    "day_of_week": day,
                    "meal_type": "dinner",
                    "default_portions": 6,
                }
                for day in range(7)
            ]
            + [
                {
                    "day_of_week": 5,
                    "meal_type": "breakfast",
                    "active": False,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    get_data = get_resp.json()

    for slot in get_data["slots"]:
        if slot["meal_type"] == "dinner":
            assert slot["portions"] == 6, (
                f"Dinner slot ({slot['day_of_week']}) should have portions=6"
            )
        elif slot["meal_type"] == "breakfast" and slot["day_of_week"] == 5:
            assert slot["active"] is False, "Saturday breakfast should be inactive"


@pytest.mark.asyncio
async def test_meal_template_deactivate_preserves_planned_recipe(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "templatesync2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Brunch")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 5,
                "meal_type": "breakfast",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )

    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [{
                "day_of_week": 5,
                "meal_type": "breakfast",
                "active": False,
            }]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    sat_bf = next(
        s for s in get_resp.json()["slots"]
        if s["day_of_week"] == 5 and s["meal_type"] == "breakfast"
    )
    assert sat_bf["recipe_id"] == recipe["id"], (
        "Slot with planned recipe should keep its recipe"
    )


@pytest.mark.asyncio
async def test_plan_creation_falls_back_to_household_default_size(
    db_session: AsyncSession,
) -> None:
    household = Household(
        name="fallback",
        slug="fallback",
        invite_code="abc12345",
        default_size=5,
    )
    db_session.add(household)
    await db_session.flush()

    plan = await get_or_create_plan(
        db_session, household.id, 2030, 1, copy_from_previous=False
    )

    for slot in plan.slots:
        assert slot.portions == 5, (
            f"slot ({slot.day_of_week}, {slot.meal_type}) "
            f"should fall back to default_size=5, got {slot.portions}"
        )


# ----- Cross-dimension cooking (Slice 6) -----


@pytest.mark.asyncio
async def test_cook_el_to_g_cross_dimension(
    client: AsyncClient,
) -> None:
    """2 EL Mehl (grams_per_el=10) should deduct 20g from 200g inventory."""
    reg = await _register(client, "cookcross1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Mehl")
    ingredient_id = ing["id"]

    await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10},
        cookies=cookies,
    )

    inv_resp = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 200,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )
    assert inv_resp.status_code == 201

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pfannkuchen",
            "instructions": "Backen.",
            "servings": 1,
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": 2,
                "unit": "EL",
            }],
        },
        cookies=cookies,
    )
    assert recipe_resp.status_code == 201
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe_id,
                "portions": 1,
            }]
        },
        cookies=cookies,
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    cook_data = cook_resp.json()
    assert cook_data["cooked"] is True
    ded = cook_data["deductions"][0]
    assert ded["ingredient_name"] == "Mehl"
    assert ded["deducted"] == 20.0
    assert ded["unit"] == "g"

    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["quantity"] == 180.0


@pytest.mark.asyncio
async def test_cook_tl_to_g_cross_dimension(
    client: AsyncClient,
) -> None:
    """1 TL Salz (grams_per_tl=5) should deduct 5g from 100g inventory."""
    reg = await _register(client, "cookcross2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Salz")
    ingredient_id = ing["id"]

    await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_tl": 5},
        cookies=cookies,
    )

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 100,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Salziges Brot",
            "instructions": "Backen.",
            "servings": 1,
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": 1,
                "unit": "TL",
            }],
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe_id,
                "portions": 1,
            }]
        },
        cookies=cookies,
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    ded = cook_resp.json()["deductions"][0]
    assert ded["deducted"] == 5.0
    assert ded["unit"] == "g"

    inv_get = await client.get("/api/inventory", cookies=cookies)
    assert inv_get.json()[0]["quantity"] == 95.0


@pytest.mark.asyncio
async def test_cook_no_spoon_conversion_falls_back_to_ml(
    client: AsyncClient,
) -> None:
    """Without conversion data, EL still normalizes to 15ml and deducts."""
    reg = await _register(client, "cookcross3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Wasser2")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 100,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Wassersuppe",
            "instructions": "Kochen.",
            "servings": 1,
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": 2,
                "unit": "EL",
            }],
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [{
                "day_of_week": 0,
                "meal_type": "dinner",
                "recipe_id": recipe_id,
                "portions": 1,
            }]
        },
        cookies=cookies,
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    assert cook_resp.json()["cooked"] is True
    ded = cook_resp.json()["deductions"][0]
    assert ded["deducted"] == 30.0
    assert ded["unit"] == "ml"

    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["quantity"] == 70.0


@pytest.mark.asyncio
async def test_compute_reservations_with_spoon_conversions(
    db_session: AsyncSession,
) -> None:
    from app.models.household import Household
    from app.models.ingredient import Ingredient
    from app.models.recipe import Recipe, RecipeIngredient
    from app.models.week_plan import MealSlot, WeekPlan
    from app.services.week_plan import compute_reservations

    household = Household(
        name="res-test",
        slug="res-test",
        invite_code="res12345",
    )
    db_session.add(household)
    await db_session.flush()

    ingredient = Ingredient(name="ResMehl", grams_per_el=10.0)
    db_session.add(ingredient)
    await db_session.flush()

    recipe = Recipe(
        title="ResTest",
        household_id=household.id,
        servings=4,
    )
    db_session.add(recipe)
    await db_session.flush()

    ri = RecipeIngredient(
        recipe_id=recipe.id,
        ingredient_id=ingredient.id,
        quantity=2,
        unit="EL",
        order_index=0,
    )
    db_session.add(ri)
    await db_session.flush()

    plan = WeekPlan(
        household_id=household.id,
        year=2030,
        iso_week=1,
    )
    db_session.add(plan)
    await db_session.flush()

    slot = MealSlot(
        week_plan_id=plan.id,
        day_of_week=0,
        meal_type="dinner",
        recipe_id=recipe.id,
        portions=4,
    )
    db_session.add(slot)
    await db_session.flush()

    reservations = await compute_reservations(db_session, plan.id)
    assert ingredient.id in reservations
    assert pytest.approx(reservations[ingredient.id]["grams"]) == 20.0
    assert reservations[ingredient.id]["milliliters"] == 0.0
    assert reservations[ingredient.id]["pieces"] == 0.0
