import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_ingredient(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ingredients",
        json={"name": "Pouletbrust"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Pouletbrust"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_ingredients(client: AsyncClient) -> None:
    await client.post("/api/ingredients", json={"name": "Tomate"})
    await client.post("/api/ingredients", json={"name": "Zwiebel"})

    response = await client.get("/api/ingredients")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert names == {"Tomate", "Zwiebel"}


@pytest.mark.asyncio
async def test_search_ingredients(client: AsyncClient) -> None:
    await client.post("/api/ingredients", json={"name": "Pouletbrust"})
    await client.post("/api/ingredients", json={"name": "Pouletschenkel"})
    await client.post("/api/ingredients", json={"name": "Tomate"})

    response = await client.get("/api/ingredients", params={"q": "poulet"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert "Pouletbrust" in names
    assert "Pouletschenkel" in names


@pytest.mark.asyncio
async def test_create_duplicate_ingredient(client: AsyncClient) -> None:
    await client.post("/api/ingredients", json={"name": "Tomate"})
    response = await client.post("/api/ingredients", json={"name": "Tomate"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_ingredient_empty_name(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_ingredients_returns_conversion_fields(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Mehl"})
    assert response.status_code == 201

    response = await client.get("/api/ingredients", params={"q": "Mehl"})
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
    response = await client.post("/api/ingredients", json={"name": "Zucker"})
    ingredient_id = response.json()["id"]

    response = await client.get(f"/api/ingredients/{ingredient_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ingredient_id
    assert data["name"] == "Zucker"
    assert data["grams_per_el"] is None
    assert data["ml_per_el"] is None


@pytest.mark.asyncio
async def test_get_ingredient_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/ingredients/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_ingredient_set_conversion(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Salz"})
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grams_per_el"] == 10
    assert data["ml_per_el"] is None


@pytest.mark.asyncio
async def test_patch_ingredient_mutual_exclusivity(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Honig"})
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10, "ml_per_el": 15},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_ingredient_clear_value(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Butter"})
    ingredient_id = response.json()["id"]

    await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": 10},
    )

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_el": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grams_per_el"] is None


@pytest.mark.asyncio
async def test_patch_ingredient_not_found(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/ingredients/99999",
        json={"grams_per_el": 10},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_ingredient_mutual_exclusivity_tl(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Zimt"})
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_tl": 5, "ml_per_tl": 5},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_ingredient_unchanged(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Käse"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Käse"
    assert data["grams_per_el"] is None


@pytest.mark.asyncio
async def test_patch_ingredient_msp_conversion(client: AsyncClient) -> None:
    response = await client.post("/api/ingredients", json={"name": "Muskat"})
    ingredient_id = response.json()["id"]

    response = await client.patch(
        f"/api/ingredients/{ingredient_id}",
        json={"grams_per_msp": 1, "grams_per_pris": 0.5},
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
    # First register to get a session
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "aliasuser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    # Create an ingredient
    create_resp = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}
    )
    ingredient_id = create_resp.json()["id"]

    # Add an alias
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
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "aliaslistuser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    create_resp = await client.post(
        "/api/ingredients", json={"name": "Rahm"}
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
