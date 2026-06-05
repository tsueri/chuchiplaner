import pytest
from httpx import AsyncClient


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


async def _get_current_iso() -> tuple[int, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Europe/Zurich"))
    iso = now.isocalendar()
    return (iso[0], iso[1])


# ----- Cook recipe without slot context -----


@pytest.mark.asyncio
async def test_cook_recipe_deducts_inventory(
    client: AsyncClient,
) -> None:
    """POST /api/recipes/:id/cook deducts scaled ingredients from raw inventory."""
    reg = await _register(client, "cookrecipe1")
    cookies = reg["cookies"]

    ing = await _create_ingredient(client, cookies, "Mehl")
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
            "title": "Brot",
            "instructions": "Backen.",
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
    recipe_id = recipe_resp.json()["id"]

    cook_resp = await client.post(
        f"/api/recipes/{recipe_id}/cook",
        json={"portions": 2},
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    cook_data = cook_resp.json()
    assert cook_data["cooked"] is True
    assert len(cook_data["deductions"]) == 1
    ded = cook_data["deductions"][0]
    assert ded["ingredient_name"] == "Mehl"
    assert ded["deducted"] == 200.0  # 400g * (2/4)
    assert ded["unit"] == "g"

    inv_get = await client.get("/api/inventory", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["quantity"] == 300.0


@pytest.mark.asyncio
async def test_cook_recipe_with_slot_context_marks_slot_cooked(
    client: AsyncClient,
) -> None:
    """Cook with slot_id/year/iso_week marks the MealSlot as cooked."""
    reg = await _register(client, "cookrecipe2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    ing = await _create_ingredient(client, cookies, "PastaZutat")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 200,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "instructions": "Kochen.",
            "servings": 2,
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 100,
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
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )

    await client.put(
        f"/api/weeks/{year}/{week}/slots",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "lunch",
                    "recipe_id": recipe_id,
                    "portions": 2,
                }
            ]
        },
        cookies=cookies,
    )

    cook_resp = await client.post(
        f"/api/recipes/{recipe_id}/cook",
        json={
            "portions": 2,
            "slot_id": slot["id"],
            "year": year,
            "iso_week": week,
        },
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    assert cook_resp.json()["cooked"] is True

    get_resp = await client.get(f"/api/weeks/{year}/{week}", cookies=cookies)
    week_slots = get_resp.json()["slots"]
    updated = next(s for s in week_slots if s["id"] == slot["id"])
    assert updated["cooked"] is True


@pytest.mark.asyncio
async def test_cook_recipe_insufficient_inventory_partial_deduction(
    client: AsyncClient,
) -> None:
    """Cook with less inventory than needed deducts whatever is available."""
    reg = await _register(client, "cookrecipe3")
    cookies = reg["cookies"]

    ing = await _create_ingredient(client, cookies, "Butter")
    ingredient_id = ing["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 50,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Butterbrot",
            "instructions": "Schmieren.",
            "servings": 1,
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 100,
                    "unit": "g",
                }
            ],
        },
        cookies=cookies,
    )
    recipe_id = recipe_resp.json()["id"]

    cook_resp = await client.post(
        f"/api/recipes/{recipe_id}/cook",
        json={"portions": 1},
        cookies=cookies,
    )
    assert cook_resp.status_code == 200
    ded = cook_resp.json()["deductions"][0]
    assert ded["deducted"] == 50.0

    inv_get = await client.get("/api/inventory", cookies=cookies)
    assert len(inv_get.json()) == 0  # depleted, deleted


@pytest.mark.asyncio
async def test_save_leftovers_creates_cooked_inventory_item(
    client: AsyncClient,
) -> None:
    """POST /api/recipes/:id/leftovers creates a cooked InventoryItem."""
    reg = await _register(client, "cookrecipe4")
    cookies = reg["cookies"]

    ing = await _create_ingredient(client, cookies, "RestZutat")
    ingredient_id = ing["id"]

    recipe_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Eintopf",
            "instructions": "Kochen.",
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

    leftovers_resp = await client.post(
        f"/api/recipes/{recipe_id}/leftovers",
        json={"portions_count": 2},
        cookies=cookies,
    )
    assert leftovers_resp.status_code == 200
    data = leftovers_resp.json()
    assert data["category"] == "cooked"
    assert data["quantity"] == 2.0
    assert data["unit"] == "Stück"
    assert data["source_recipe_id"] == recipe_id

    inv_get = await client.get("/api/inventory?category=cooked", cookies=cookies)
    items = inv_get.json()
    assert len(items) == 1
    assert items[0]["ingredient_name"] == "Eintopf (Reste)"
