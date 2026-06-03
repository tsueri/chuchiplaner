import pytest
from httpx import AsyncClient


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
