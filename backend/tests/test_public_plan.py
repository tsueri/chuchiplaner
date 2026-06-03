import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, username: str = "testuser", invite_code: str | None = None) -> dict:
    body = {"username": username, "password": "secret123"}
    if invite_code is not None:
        body["invite_code"] = invite_code
    resp = await client.post(
        "/api/auth/register",
        json=body,
    )
    return {"cookies": resp.cookies, "data": resp.json()}


async def _create_recipe(
    client: AsyncClient,
    cookies,
    title: str = "Test Recipe",
    source_url: str | None = None,
    source_domain: str | None = None,
) -> dict:
    body: dict = {
        "title": title,
        "instructions": "Cook it.",
        "servings": 4,
    }
    if source_url:
        body["source_url"] = source_url
    if source_domain:
        body["source_domain"] = source_domain
    resp = await client.post("/api/recipes", json=body, cookies=cookies)
    return resp.json()


async def _get_current_iso() -> tuple[int, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Zurich"))
    iso = now.isocalendar()
    return (iso[0], iso[1])


# ----- Public plan endpoint -----


@pytest.mark.asyncio
async def test_public_plan_returns_404_for_private_week(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    resp = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_plan_returns_plan_when_public(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(
        client, cookies, "Pasta", "https://example.com/pasta", "example.com"
    )

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
                "portions": 4,
            }]
        },
        cookies=cookies,
    )

    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    resp = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["household_name"] == household["name"]
    assert data["year"] == year
    assert data["iso_week"] == week
    assert len(data["slots"]) == 28

    monday_lunch = next(
        s for s in data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "lunch"
    )
    assert monday_lunch["recipe"] is not None
    assert monday_lunch["recipe"]["title"] == "Pasta"
    assert monday_lunch["recipe"]["source_url"] == "https://example.com/pasta"
    assert monday_lunch["recipe"]["source_domain"] == "example.com"
    assert monday_lunch["portions"] == 4


@pytest.mark.asyncio
async def test_public_plan_returns_404_for_nonexistent_slug(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/public/plan/no-such-slug/2026/23")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_plan_returns_404_when_toggled_back_to_private(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest3")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    resp1 = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp1.status_code == 200

    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": False},
        cookies=cookies,
    )

    resp2 = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_public_plan_no_auth_required(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest4")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    # Make request without auth cookies
    resp = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}",
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_plan_source_attribution(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest5")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(
        client, cookies, "Gulasch",
        source_url="https://fooby.ch/gulasch",
        source_domain="fooby.ch",
    )

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
                "meal_type": "dinner",
                "recipe_id": recipe["id"],
            }]
        },
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    resp = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp.status_code == 200
    data = resp.json()

    monday_dinner = next(
        s for s in data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )
    assert monday_dinner["recipe"]["title"] == "Gulasch"
    assert monday_dinner["recipe"]["source_domain"] == "fooby.ch"
    assert monday_dinner["recipe"]["source_url"] == "https://fooby.ch/gulasch"


@pytest.mark.asyncio
async def test_public_plan_slot_without_recipe_has_null_recipe(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest6")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    resp = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp.status_code == 200
    data = resp.json()

    monday_breakfast = next(
        s for s in data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "breakfast"
    )
    assert monday_breakfast["recipe"] is None


@pytest.mark.asyncio
async def test_public_plan_cooked_slot_shows_cooked(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "pubtest7")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    recipe = await _create_recipe(client, cookies, "Salat")

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    plan_resp = await client.get(
        f"/api/weeks/{year}/{week}", cookies=cookies
    )
    slot = next(
        s for s in plan_resp.json()["slots"]
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
    await client.post(
        f"/api/weeks/{year}/{week}/slots/{slot['id']}/cook",
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()

    resp = await client.get(
        f"/api/public/plan/{household['slug']}/{year}/{week}"
    )
    assert resp.status_code == 200
    data = resp.json()

    dinner = next(
        s for s in data["slots"]
        if s["day_of_week"] == 0 and s["meal_type"] == "dinner"
    )
    assert dinner["cooked"] is True


# ----- Visibility toggle endpoint -----


@pytest.mark.asyncio
async def test_visibility_toggle_set_public(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "vistest1")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is True

    get_resp = await client.get(
        f"/api/weeks/{year}/{week}", cookies=cookies
    )
    assert get_resp.json()["is_public"] is True


@pytest.mark.asyncio
async def test_visibility_toggle_set_private(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "vistest2")
    cookies = reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=cookies,
    )
    await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": False},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is False

    get_resp = await client.get(
        f"/api/weeks/{year}/{week}", cookies=cookies
    )
    assert get_resp.json()["is_public"] is False


@pytest.mark.asyncio
async def test_visibility_toggle_requires_admin(
    client: AsyncClient,
) -> None:
    admin_reg = await _register(client, "vistadmin")
    admin_cookies = admin_reg["cookies"]
    invite_code = (
        await client.get("/api/household", cookies=admin_cookies)
    ).json()["invite_code"]

    member_reg = await _register(client, "vistmember", invite_code)
    member_cookies = member_reg["cookies"]
    year, week = await _get_current_iso()

    await client.post(
        "/api/weeks",
        json={"year": year, "iso_week": week},
        cookies=admin_cookies,
    )

    resp = await client.put(
        f"/api/weeks/{year}/{week}/visibility",
        json={"is_public": True},
        cookies=member_cookies,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_visibility_toggle_nonexistent_week_returns_404(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "vistest3")
    cookies = reg["cookies"]

    resp = await client.put(
        "/api/weeks/1999/1/visibility",
        json={"is_public": True},
        cookies=cookies,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_visibility_toggle_requires_auth(
    client: AsyncClient,
) -> None:
    resp = await client.put(
        "/api/weeks/2026/1/visibility",
        json={"is_public": True},
    )
    assert resp.status_code == 401


# ----- Household default_public -----


@pytest.mark.asyncio
async def test_household_has_default_public(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "defpubtest")
    cookies = reg["cookies"]

    household = (await client.get("/api/household", cookies=cookies)).json()
    assert "default_public" in household
    assert household["default_public"] is False


@pytest.mark.asyncio
async def test_admin_can_update_default_public(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "defpubadmin")
    cookies = reg["cookies"]

    resp = await client.put(
        "/api/household",
        json={"default_public": True},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["default_public"] is True

    household = (await client.get("/api/household", cookies=cookies)).json()
    assert household["default_public"] is True


@pytest.mark.asyncio
async def test_new_weeks_inherit_default_public(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "inheritpub")
    cookies = reg["cookies"]

    await client.put(
        "/api/household",
        json={"default_public": True},
        cookies=cookies,
    )

    year, week = await _get_current_iso()
    next_week = week + 1
    next_year = year

    resp = await client.post(
        "/api/weeks",
        json={"year": next_year, "iso_week": next_week},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is True


@pytest.mark.asyncio
async def test_new_weeks_not_public_when_default_public_false(
    client: AsyncClient,
) -> None:
    reg = await _register(client, "noinheritpub")
    cookies = reg["cookies"]

    year, week = await _get_current_iso()
    next_week = week + 1
    next_year = year

    resp = await client.post(
        "/api/weeks",
        json={"year": next_year, "iso_week": next_week},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is False
