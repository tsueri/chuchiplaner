import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household import Household
from app.services.week_plan import get_or_create_plan


async def _register(client: AsyncClient, username: str = "testuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    return {"cookies": resp.cookies, "data": resp.json()}


async def _create_ingredient(
    client: AsyncClient,
    cookies,
    name: str = "Zwiebel",
) -> dict:
    resp = await client.post("/api/ingredients", json={"name": name}, cookies=cookies)
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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": recipe["id"],
                    "portions": 4,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    get_data = get_resp.json()
    updated_slot = next(
        s
        for s in get_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    assert updated_slot["planned_recipes"][0]["recipe_id"] == recipe["id"]
    assert updated_slot["planned_recipes"][0]["recipe_title"] == "Pasta"
    assert updated_slot["planned_recipes"][0]["portions"] == 4
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "planned_recipes": [],
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    get_data = get_resp.json()
    updated_slot = next(s for s in get_data["slots"] if s["id"] == monday_dinner["id"])
    assert len(updated_slot["planned_recipes"]) == 0


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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "planned_recipes": [],
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slots = get_resp.json()["slots"]

    source = next(s for s in slots if s["id"] == monday_lunch["id"])
    assert len(source["planned_recipes"]) == 0

    target = next(
        s for s in slots if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )
    assert target["planned_recipes"][0]["recipe_id"] == recipe["id"]
    assert target["planned_recipes"][0]["recipe_title"] == "Risotto"


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
            "slots": [
                {
                    "day_of_week": 2,
                    "meal_type": "lunch",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )
    assert put_resp.status_code == 200

    get_source = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    source_slots = get_source.json()["slots"]
    source_wed = next(
        s for s in source_slots if s["day_of_week"] == 2 and s["meal_type"] == "lunch"
    )
    assert source_wed["planned_recipes"][0]["recipe_id"] == recipe["id"]

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
        s for s in new_slots if s["day_of_week"] == 2 and s["meal_type"] == "lunch"
    )
    assert wed_lunch["planned_recipes"][0]["recipe_id"] == recipe["id"]


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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": recipe["id"],
                }
            ]
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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": 1,
                }
            ]
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
            "slots": [
                {
                    "day_of_week": 3,
                    "meal_type": "dinner",
                    "portions": 6,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    thursday_dinner = next(
        s
        for s in get_resp.json()["slots"]
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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "portions": 8,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot = next(
        s
        for s in get_resp.json()["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    assert slot["planned_recipes"][0]["recipe_id"] == recipe["id"]
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
        s for s in slots if s["day_of_week"] == 0 and s["meal_type"] == "breakfast"
    )
    tue_bf = next(
        s for s in slots if s["day_of_week"] == 1 and s["meal_type"] == "breakfast"
    )
    assert mon_bf["planned_recipes"][0]["recipe_id"] == recipe1["id"]
    assert tue_bf["planned_recipes"][0]["recipe_id"] == recipe2["id"]


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
        assert len(s["planned_recipes"]) == 0


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
            "slots": [
                {
                    "day_of_week": 1,
                    "meal_type": "lunch",
                    "dietary_filter_tag_id": 1,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    tue_lunch = next(
        s
        for s in get_resp.json()["slots"]
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
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 400,
                    "unit": "g",
                }
            ],
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 6 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 6,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                    "portions": 2,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(
        s for s in get_resp.json()["slots"] if s["id"] == sunday_dinner["id"]
    )
    pr = slot_data["planned_recipes"][0]

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{sunday_dinner['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
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
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 200,
                    "unit": "ml",
                }
            ],
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "breakfast"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "breakfast",
                    "recipe_id": recipe_id,
                    "portions": 4,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == monday_bf["id"])
    pr = slot_data["planned_recipes"][0]

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{monday_bf['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{empty_slot['id']}/cook",
        json={"planned_recipe_id": 9999},
        cookies=cookies,
    )
    assert cook_resp.status_code == 404


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
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 500,
                    "unit": "g",
                }
            ],
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == slot["id"])
    pr = slot_data["planned_recipes"][0]

    cook1 = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
        cookies=cookies,
    )
    assert cook1.status_code == 200

    cook2 = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
        cookies=cookies,
    )
    assert cook2.status_code == 400
    detail = cook2.json()["detail"].lower()
    assert "already" in detail or "bereits" in detail


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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == slot["id"])
    pr = slot_data["planned_recipes"][0]

    resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/leftovers",
        json={"planned_recipe_id": pr["id"], "portions_count": 3},
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{empty_slot['id']}/leftovers",
        json={"planned_recipe_id": 9999, "portions_count": 2},
        cookies=cookies,
    )
    assert resp.status_code == 404


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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 1 and s["meal_type"] == "lunch"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 1,
                    "meal_type": "lunch",
                    "recipe_id": recipe_id,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == slot["id"])
    pr = slot_data["planned_recipes"][0]

    await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/leftovers",
        json={"planned_recipe_id": pr["id"], "portions_count": 2},
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
            "slots": [
                {
                    "day_of_week": 5,
                    "meal_type": "breakfast",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )

    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
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
    sat_bf = next(
        s
        for s in get_resp.json()["slots"]
        if s["day_of_week"] == 5 and s["meal_type"] == "breakfast"
    )
    assert sat_bf["planned_recipes"][0]["recipe_id"] == recipe["id"], (
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
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 2,
                    "unit": "EL",
                }
            ],
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                    "portions": 1,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == slot["id"])
    pr = slot_data["planned_recipes"][0]

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
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
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 1,
                    "unit": "TL",
                }
            ],
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                    "portions": 1,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == slot["id"])
    pr = slot_data["planned_recipes"][0]

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
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
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 2,
                    "unit": "EL",
                }
            ],
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
        s
        for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                    "portions": 1,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(s for s in get_resp.json()["slots"] if s["id"] == slot["id"])
    pr = slot_data["planned_recipes"][0]

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
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
    from app.models.week_plan import MealSlot, PlannedRecipe, WeekPlan
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
        portions=4,
    )
    db_session.add(slot)
    await db_session.flush()

    planned = PlannedRecipe(
        meal_slot_id=slot.id,
        recipe_id=recipe.id,
        portions=4,
        order_index=0,
    )
    db_session.add(planned)
    await db_session.flush()

    reservations = await compute_reservations(db_session, plan.id)
    assert ingredient.id in reservations
    assert pytest.approx(reservations[ingredient.id]["grams"]) == 20.0
    assert reservations[ingredient.id]["milliliters"] == 0.0
    assert reservations[ingredient.id]["pieces"] == 0.0


# ----- Multi-recipe slot CRUD (Slice 2) -----


@pytest.mark.asyncio
async def test_plan_multiple_recipes_on_slot(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "multiuser1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe1 = await _create_recipe(client, cookies, "Suppe")
    recipe2 = await _create_recipe(client, cookies, "Salat")

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
                    "meal_type": "lunch",
                    "planned_recipes": [
                        {"recipe_id": recipe1["id"], "portions": 3},
                        {"recipe_id": recipe2["id"], "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot = next(
        s
        for s in get_resp.json()["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    assert len(slot["planned_recipes"]) == 2
    pr0 = slot["planned_recipes"][0]
    pr1 = slot["planned_recipes"][1]
    assert pr0["recipe_id"] == recipe1["id"]
    assert pr0["recipe_title"] == "Suppe"
    assert pr0["portions"] == 3
    assert pr1["recipe_id"] == recipe2["id"]
    assert pr1["recipe_title"] == "Salat"
    assert pr1["portions"] == 2


@pytest.mark.asyncio
async def test_remove_one_planned_recipe_from_multi_slot(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "multiuser2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe1 = await _create_recipe(client, cookies, "Pasta")
    recipe2 = await _create_recipe(client, cookies, "Dessert")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "planned_recipes": [
                        {"recipe_id": recipe1["id"], "portions": 4},
                        {"recipe_id": recipe2["id"], "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    _ = next(
        s
        for s in get_resp.json()["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )
    resp = await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "planned_recipes": [
                        {"recipe_id": recipe2["id"], "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp2 = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot2 = next(
        s
        for s in get_resp2.json()["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )
    assert len(slot2["planned_recipes"]) == 1
    assert slot2["planned_recipes"][0]["recipe_id"] == recipe2["id"]


@pytest.mark.asyncio
async def test_reservations_with_multi_recipe_slots(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "multiuser3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing1 = await _create_ingredient(client, cookies, "Tomate")
    ingredient_id1 = ing1["id"]

    ing2 = await _create_ingredient(client, cookies, "Gurke")
    ingredient_id2 = ing2["id"]

    recipe1 = await client.post(
        "/api/recipes",
        json={
            "title": "Tomatensalat",
            "instructions": "Schneiden.",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": ingredient_id1, "quantity": 200, "unit": "g"},
            ],
        },
        cookies=cookies,
    )
    recipe1_id = recipe1.json()["id"]

    recipe2 = await client.post(
        "/api/recipes",
        json={
            "title": "Gurkensalat",
            "instructions": "Schneiden.",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": ingredient_id2, "quantity": 150, "unit": "g"},
            ],
        },
        cookies=cookies,
    )
    recipe2_id = recipe2.json()["id"]

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "planned_recipes": [
                        {"recipe_id": recipe1_id, "portions": 4},
                        {"recipe_id": recipe2_id, "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )

    res_resp = await client.get(
        f"/api/weeks/{year}/{week}/reservations", cookies=cookies
    )
    assert res_resp.status_code == 200
    reservations = res_resp.json()
    assert str(ingredient_id1) in reservations
    assert str(ingredient_id2) in reservations
    assert reservations[str(ingredient_id1)]["grams"] == 400.0  # (200/2) * 4
    assert reservations[str(ingredient_id2)]["grams"] == 150.0  # (150/2) * 2


# ----- Per-recipe cooking (Slice 3) -----


@pytest.mark.asyncio
async def test_cook_planned_recipe_deducts_inventory(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prcook1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Poulet")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pouletgeschnetzeltes",
            "instructions": "Braten.",
            "servings": 4,
            "ingredients": [
                {"ingredient_id": ingredient_id, "quantity": 400, "unit": "g"}
            ],
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
        if s["day_of_week"] == 6 and s["meal_type"] == "dinner"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 6,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                    "portions": 2,
                }
            ]
        },
        cookies=cookies,
    )

    # Get slot with planned_recipe_id
    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(
        s for s in get_resp.json()["slots"]
        if s["id"] == slot["id"]
    )
    pr = slot_data["planned_recipes"][0]

    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
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
async def test_cook_already_cooked_planned_recipe_fails(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prcook2")
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
            "ingredients": [
                {"ingredient_id": ingredient_id, "quantity": 500, "unit": "g"}
            ],
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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "recipe_id": recipe_id,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(
        s for s in get_resp.json()["slots"]
        if s["id"] == slot["id"]
    )
    pr = slot_data["planned_recipes"][0]

    cook1 = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
        cookies=cookies,
    )
    assert cook1.status_code == 200

    cook2 = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
        cookies=cookies,
    )
    assert cook2.status_code == 400
    detail = cook2.json()["detail"].lower()
    assert "already" in detail or "bereits" in detail


@pytest.mark.asyncio
async def test_cook_planned_recipe_wrong_slot_fails(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prcook3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "Fisch")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe = await _create_recipe(client, cookies, "Fischfilet")
    recipe_id = recipe["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot_a = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    slot_b = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )

    # Plan recipe to slot A
    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": recipe_id,
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_a_data = next(
        s for s in get_resp.json()["slots"]
        if s["id"] == slot_a["id"]
    )
    pr = slot_a_data["planned_recipes"][0]

    # Try to cook with PR ID but wrong slot ID
    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot_b['id']}/cook",
        json={"planned_recipe_id": pr["id"]},
        cookies=cookies,
    )
    assert cook_resp.status_code == 404


@pytest.mark.asyncio
async def test_cook_slot_with_no_planned_recipes_fails(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prcook4")
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
        json={"planned_recipe_id": 9999},
        cookies=cookies,
    )
    assert cook_resp.status_code == 404


@pytest.mark.asyncio
async def test_cook_multiple_recipes_in_slot_only_one_cooked(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prcook5")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing1 = await _create_ingredient(client, cookies, "Mehl")
    ing2 = await _create_ingredient(client, cookies, "Zucker")

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing1["id"],
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )
    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing2["id"],
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe1_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Kuchen",
            "instructions": "Backen.",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": ing1["id"], "quantity": 200, "unit": "g"}
            ],
        },
        cookies=cookies,
    )
    recipe1_id = recipe1_resp.json()["id"]

    recipe2_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Glasur",
            "instructions": "Ruehren.",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": ing2["id"], "quantity": 100, "unit": "g"}
            ],
        },
        cookies=cookies,
    )
    recipe2_id = recipe2_resp.json()["id"]

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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "planned_recipes": [
                        {"recipe_id": recipe1_id, "portions": 4},
                        {"recipe_id": recipe2_id, "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(
        s for s in get_resp.json()["slots"]
        if s["id"] == slot["id"]
    )
    pr2 = slot_data["planned_recipes"][1]

    # Cook only the second PlannedRecipe
    cook_resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr2["id"]},
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    ded = cook_resp.json()["deductions"]
    assert len(ded) == 1
    assert ded[0]["ingredient_name"] == "Zucker"

    # Verify only pr2 is cooked, pr1 is not
    get_resp2 = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data2 = next(
        s for s in get_resp2.json()["slots"]
        if s["id"] == slot["id"]
    )
    pr1_after = next(
        p for p in slot_data2["planned_recipes"]
        if p["recipe_id"] == recipe1_id
    )
    pr2_after = next(
        p for p in slot_data2["planned_recipes"]
        if p["recipe_id"] == recipe2_id
    )
    assert pr1_after["cooked"] is False
    assert pr2_after["cooked"] is True

    # Ingredient 2 inventory was deducted, ingredient 1 wasn't
    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    mehl = next(i for i in items if i["ingredient_name"] == "Mehl")
    zucker = next(i for i in items if i["ingredient_name"] == "Zucker")
    assert mehl["quantity"] == 500.0  # unchanged
    assert zucker["quantity"] == 400.0  # 500 - (100/2)*2 = 500 - 100 = 400


@pytest.mark.asyncio
async def test_leftovers_per_planned_recipe(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prleftover1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe1 = await _create_recipe(client, cookies, "Pasta")
    recipe2 = await _create_recipe(client, cookies, "Salat")

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
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "dinner",
                    "planned_recipes": [
                        {"recipe_id": recipe1["id"], "portions": 4},
                        {"recipe_id": recipe2["id"], "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(
        s for s in get_resp.json()["slots"]
        if s["id"] == slot["id"]
    )
    pr2 = slot_data["planned_recipes"][1]

    resp = await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/leftovers",
        json={"planned_recipe_id": pr2["id"], "portions_count": 3},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingredient_name"] == "Salat (Reste)"
    assert data["quantity"] == 3.0
    assert data["source_recipe_id"] == recipe2["id"]

    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["ingredient_name"] == "Salat (Reste)"
    assert items[0]["source_recipe_id"] == recipe2["id"]


@pytest.mark.asyncio
async def test_compute_reservations_skips_cooked_planned_recipes(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "prres1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing1 = await _create_ingredient(client, cookies, "Tomate")
    ing2 = await _create_ingredient(client, cookies, "Gurke")

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing1["id"],
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )
    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ing2["id"],
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe1 = await client.post(
        "/api/recipes",
        json={
            "title": "Tomatensalat2",
            "instructions": "Schneiden.",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": ing1["id"], "quantity": 200, "unit": "g"},
            ],
        },
        cookies=cookies,
    )
    recipe1_id = recipe1.json()["id"]

    recipe2 = await client.post(
        "/api/recipes",
        json={
            "title": "Gurkensalat2",
            "instructions": "Schneiden.",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": ing2["id"], "quantity": 150, "unit": "g"},
            ],
        },
        cookies=cookies,
    )
    recipe2_id = recipe2.json()["id"]

    create_resp = await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_data = create_resp.json()
    slot = next(
        s for s in plan_data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "planned_recipes": [
                        {"recipe_id": recipe1_id, "portions": 4},
                        {"recipe_id": recipe2_id, "portions": 2},
                    ],
                }
            ]
        },
        cookies=cookies,
    )

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot_data = next(
        s for s in get_resp.json()["slots"]
        if s["id"] == slot["id"]
    )
    pr1 = slot_data["planned_recipes"][0]

    # Cook the first PR
    await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        json={"planned_recipe_id": pr1["id"]},
        cookies=cookies,
    )

    res_resp = await client.get(
        f"/api/weeks/{year}/{week}/reservations", cookies=cookies
    )
    assert res_resp.status_code == 200
    reservations = res_resp.json()
    # Tomate (cooked) should not be in reservations
    assert str(ing1["id"]) not in reservations
    # Gurke (uncooked) should still be in reservations
    assert str(ing2["id"]) in reservations
    assert reservations[str(ing2["id"])]["grams"] == 150.0


@pytest.mark.asyncio
async def test_delete_recipe_endpoint_removed(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "nodel1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Pizza")

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
                    "meal_type": "lunch",
                    "recipe_id": recipe["id"],
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    slot = get_resp.json()["slots"][0]

    del_resp = await client.delete(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/recipe",
        cookies=cookies,
    )
    assert del_resp.status_code == 404
