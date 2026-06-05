import pytest
from httpx import AsyncClient


async def _register_admin(client: AsyncClient, username: str = "adminuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    assert resp.status_code == 200
    return {"cookies": resp.cookies, "data": resp.json()}


async def _register_member(
    client: AsyncClient, admin_cookies, username: str = "memberuser"
) -> dict:
    hh_resp = await client.get("/api/household", cookies=admin_cookies)
    invite_code = hh_resp.json()["invite_code"]
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "invite_code": invite_code,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"
    return {"cookies": resp.cookies, "data": resp.json()}


# ── auth matrix ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_ingredients_no_session_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/ingredients")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_ingredients_no_session_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Test"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_ingredients_member_returns_200(client: AsyncClient) -> None:
    admin = await _register_admin(client, "admin_auth1")
    member = await _register_member(client, admin["cookies"], "member_auth1")
    response = await client.get("/api/ingredients", cookies=member["cookies"])
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_ingredients_member_returns_403(client: AsyncClient) -> None:
    admin = await _register_admin(client, "admin_auth2")
    member = await _register_member(client, admin["cookies"], "member_auth2")
    response = await client.post(
        "/api/ingredients", json={"name": "Test"}, cookies=member["cookies"]
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_post_ingredients_admin_returns_201(client: AsyncClient) -> None:
    admin = await _register_admin(client, "admin_auth3")
    response = await client.post(
        "/api/ingredients", json={"name": "AdminIngredient"}, cookies=admin["cookies"]
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_patch_ingredients_member_returns_403(client: AsyncClient) -> None:
    admin = await _register_admin(client, "admin_auth4")
    member = await _register_member(client, admin["cookies"], "member_auth4")
    create_resp = await client.post(
        "/api/ingredients", json={"name": "Z"}, cookies=admin["cookies"]
    )
    ing_id = create_resp.json()["id"]
    response = await client.patch(
        f"/api/ingredients/{ing_id}", json={"name": "Z2"}, cookies=member["cookies"]
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_ingredients_member_returns_403(client: AsyncClient) -> None:
    admin = await _register_admin(client, "admin_auth5")
    member = await _register_member(client, admin["cookies"], "member_auth5")
    create_resp = await client.post(
        "/api/ingredients", json={"name": "D"}, cookies=admin["cookies"]
    )
    ing_id = create_resp.json()["id"]
    response = await client.delete(
        f"/api/ingredients/{ing_id}", cookies=member["cookies"]
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_ingredient_no_session_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/ingredients/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_ingredients_no_session_returns_401(client: AsyncClient) -> None:
    response = await client.patch("/api/ingredients/1", json={"name": "X"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_ingredients_no_session_returns_401(client: AsyncClient) -> None:
    response = await client.delete("/api/ingredients/1")
    assert response.status_code == 401


# ── existing behaviour, now with auth ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_ingredient(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients",
        json={"name": "Pouletbrust"},
        cookies=admin["cookies"],
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Pouletbrust"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_ingredients(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    await client.post(
        "/api/ingredients", json={"name": "Tomate"}, cookies=admin["cookies"]
    )
    await client.post(
        "/api/ingredients", json={"name": "Zwiebel"}, cookies=admin["cookies"]
    )

    response = await client.get("/api/ingredients", cookies=admin["cookies"])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert names == {"Tomate", "Zwiebel"}


@pytest.mark.asyncio
async def test_search_ingredients(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}, cookies=admin["cookies"]
    )
    await client.post(
        "/api/ingredients", json={"name": "Pouletschenkel"}, cookies=admin["cookies"]
    )
    await client.post(
        "/api/ingredients", json={"name": "Tomate"}, cookies=admin["cookies"]
    )

    response = await client.get(
        "/api/ingredients", params={"q": "poulet"}, cookies=admin["cookies"]
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert "Pouletbrust" in names
    assert "Pouletschenkel" in names


@pytest.mark.asyncio
async def test_create_duplicate_ingredient(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    await client.post(
        "/api/ingredients", json={"name": "Tomate"}, cookies=admin["cookies"]
    )
    response = await client.post(
        "/api/ingredients", json={"name": "Tomate"}, cookies=admin["cookies"]
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_ingredient_empty_name(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": ""}, cookies=admin["cookies"]
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_ingredients_returns_conversion_fields(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Mehl"}, cookies=admin["cookies"]
    )
    assert response.status_code == 201

    response = await client.get(
        "/api/ingredients", params={"q": "Mehl"}, cookies=admin["cookies"]
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert "grams_per_el" in item
    assert item["grams_per_el"] is None
    assert "ml_per_el" in item
    assert "grams_per_tl" in item
    assert "ml_per_tl" in item
    assert "grams_per_msp" in item
    assert "ml_per_msp" in item
    assert "grams_per_pris" in item
    assert "ml_per_pris" in item


@pytest.mark.asyncio
async def test_get_ingredient_returns_conversion_fields(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Zucker"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.get(
        f"/api/ingredients/{ingredient_id}", cookies=admin["cookies"]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ingredient_id
    assert data["name"] == "Zucker"
    assert data["grams_per_el"] is None
    assert data["ml_per_el"] is None


@pytest.mark.asyncio
async def test_get_ingredient_not_found(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.get("/api/ingredients/99999", cookies=admin["cookies"])
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_ingredient_set_conversion(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Salz"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10},
        cookies=admin["cookies"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grams_per_el"] == 10
    assert data["ml_per_el"] is None


@pytest.mark.asyncio
async def test_patch_ingredient_mutual_exclusivity(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Honig"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10, "ml_per_el": 15},
        cookies=admin["cookies"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_ingredient_clear_value(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Butter"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10},
        cookies=admin["cookies"],
    )

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": None},
        cookies=admin["cookies"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grams_per_el"] is None


@pytest.mark.asyncio
async def test_patch_ingredient_not_found(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.patch(
        "/api/ingredients/99999",
        json={"grams_per_el": 10},
        cookies=admin["cookies"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_ingredient_mutual_exclusivity_tl(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Zimt"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_tl": 5, "ml_per_tl": 5},
        cookies=admin["cookies"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_ingredient_unchanged(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Käse"}, cookies=admin["cookies"]
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Käse"
    assert data["grams_per_el"] is None


@pytest.mark.asyncio
async def test_patch_ingredient_msp_conversion(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Muskat"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_msp": 1, "grams_per_pris": 0.5},
        cookies=admin["cookies"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grams_per_msp"] == 1
    assert data["grams_per_pris"] == 0.5
    assert data["ml_per_msp"] is None
    assert data["ml_per_pris"] is None


@pytest.mark.asyncio
async def test_add_alias(
    client: AsyncClient,
) -> None:
    admin = await _register_admin(client, "aliasuser")
    cookies = admin["cookies"]

    create_resp = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}, cookies=cookies
    )
    ingredient_id = create_resp.json()["id"]

    response = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["alias_name"] == "Hähnchenbrust"
    assert data["ingredient_id"] == ingredient_id
    assert "id" in data


@pytest.mark.asyncio
async def test_list_aliases(client: AsyncClient) -> None:
    admin = await _register_admin(client, "aliaslistuser")
    cookies = admin["cookies"]

    create_resp = await client.post(
        "/api/ingredients", json={"name": "Rahm"}, cookies=cookies
    )
    ingredient_id = create_resp.json()["id"]

    await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Sahne"},
        cookies=cookies,
    )

    response = await client.get("/api/household/aliases", cookies=cookies)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["alias_name"] == "Sahne"
    assert data[0]["ingredient_id"] == ingredient_id


@pytest.mark.asyncio
async def test_add_alias_unauthenticated(client: AsyncClient) -> None:
    response = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": 1, "alias_name": "Test"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_ingredient_rename(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Rüebli"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"name": "Karotte"},
        cookies=admin["cookies"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Karotte"


@pytest.mark.asyncio
async def test_patch_ingredient_rename_duplicate(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    await client.post(
        "/api/ingredients", json={"name": "Apfel"}, cookies=admin["cookies"]
    )
    response = await client.post(
        "/api/ingredients", json={"name": "Birne"}, cookies=admin["cookies"]
    )
    birne_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{birne_id}",
        json={"name": "Apfel"},
        cookies=admin["cookies"],
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_ingredient_rename_not_found(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.patch(
        "/api/ingredients/99999",
        json={"name": "NichtDa"},
        cookies=admin["cookies"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_ingredient(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.post(
        "/api/ingredients", json={"name": "Randen"}, cookies=admin["cookies"]
    )
    ingredient_id = response.json()["id"]

    response = await client.delete(
        f"/api/ingredients/{ingredient_id}", cookies=admin["cookies"]
    )
    assert response.status_code == 204

    response = await client.get(
        f"/api/ingredients/{ingredient_id}", cookies=admin["cookies"]
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_ingredient_not_found(client: AsyncClient) -> None:
    admin = await _register_admin(client)
    response = await client.delete("/api/ingredients/99999", cookies=admin["cookies"])
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_ingredient_blocked_by_inventory(
    client: AsyncClient,
) -> None:
    admin = await _register_admin(client, "delblock1")
    cookies = admin["cookies"]

    create_resp = await client.post(
        "/api/ingredients", json={"name": "Blockiert"}, cookies=cookies
    )
    ingredient_id = create_resp.json()["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 1.0,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )

    response = await client.delete(f"/api/ingredients/{ingredient_id}", cookies=cookies)
    assert response.status_code == 409
    data = response.json()
    assert "Inventar" in data["detail"]
