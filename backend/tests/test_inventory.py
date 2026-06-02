import pytest
from datetime import date, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_inventory_item(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser1", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    create_resp = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}
    )
    ingredient_id = create_resp.json()["id"]

    response = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 500.0,
            "unit": "g",
            "category": "raw",
            "expiry_date": "2026-06-10",
        },
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ingredient_id"] == ingredient_id
    assert data["quantity"] == 500.0
    assert data["unit"] == "g"
    assert data["category"] == "raw"
    assert data["expiry_date"] == "2026-06-10"
    assert "id" in data
    assert "ingredient_name" in data


@pytest.mark.asyncio
async def test_list_inventory_sorted_by_expiry(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser2", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    ing1 = await client.post("/api/ingredients", json={"name": "Tomate"})
    ing2 = await client.post("/api/ingredients", json={"name": "Zwiebel"})
    ing3 = await client.post("/api/ingredients", json={"name": "Kartoffel"})
    id1 = ing1.json()["id"]
    id2 = ing2.json()["id"]
    id3 = ing3.json()["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": id1,
            "quantity": 3,
            "unit": "St\u00fcck",
            "category": "raw",
            "expiry_date": "2026-06-20",
        },
        cookies=cookies,
    )
    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": id2,
            "quantity": 2,
            "unit": "St\u00fcck",
            "category": "raw",
            "expiry_date": "2026-06-10",
        },
        cookies=cookies,
    )
    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": id3,
            "quantity": 1,
            "unit": "kg",
            "category": "raw",
        },
        cookies=cookies,
    )

    response = await client.get("/api/inventory", cookies=cookies)
    assert response.status_code == 200
    data = response.json()

    # Sorted by expiry: 2026-06-10 first, then 2026-06-20, then null last
    assert data[0]["expiry_date"] == "2026-06-10"
    assert data[1]["expiry_date"] == "2026-06-20"
    assert data[2]["expiry_date"] is None


@pytest.mark.asyncio
async def test_update_inventory_item(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser3", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    ing_resp = await client.post("/api/ingredients", json={"name": "Rahm"})
    ingredient_id = ing_resp.json()["id"]

    create_resp = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 200,
            "unit": "ml",
            "category": "raw",
            "expiry_date": "2026-06-15",
        },
        cookies=cookies,
    )
    item_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/inventory/{item_id}",
        json={
            "quantity": 300,
            "unit": "g",
            "category": "cooked",
            "expiry_date": "2026-06-18",
        },
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 300
    assert data["unit"] == "g"
    assert data["category"] == "cooked"
    assert data["expiry_date"] == "2026-06-18"


@pytest.mark.asyncio
async def test_delete_inventory_item(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser4", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    ing_resp = await client.post("/api/ingredients", json={"name": "Milch"})
    ingredient_id = ing_resp.json()["id"]

    create_resp = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 1,
            "unit": "l",
            "category": "raw",
        },
        cookies=cookies,
    )
    item_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/inventory/{item_id}", cookies=cookies
    )
    assert del_resp.status_code == 204

    list_resp = await client.get("/api/inventory", cookies=cookies)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_inventory_expiry_optional(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser5", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    ing_resp = await client.post("/api/ingredients", json={"name": "Salz"})
    ingredient_id = ing_resp.json()["id"]

    response = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "quantity": 500,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["expiry_date"] is None


@pytest.mark.asyncio
async def test_inventory_category_filter(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser6", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    ing1 = await client.post("/api/ingredients", json={"name": "Brokkoli"})
    ing2 = await client.post("/api/ingredients", json={"name": "H\u00e4hnchen"})
    ing3 = await client.post("/api/ingredients", json={"name": "Erbsen"})
    id1 = ing1.json()["id"]
    id2 = ing2.json()["id"]
    id3 = ing3.json()["id"]

    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": id1,
            "quantity": 1,
            "unit": "St\u00fcck",
            "category": "raw",
        },
        cookies=cookies,
    )
    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": id2,
            "quantity": 300,
            "unit": "g",
            "category": "cooked",
        },
        cookies=cookies,
    )
    await client.post(
        "/api/inventory",
        json={
            "ingredient_id": id3,
            "quantity": 400,
            "unit": "g",
            "category": "frozen",
        },
        cookies=cookies,
    )

    raw_resp = await client.get(
        "/api/inventory", params={"category": "raw"}, cookies=cookies
    )
    assert raw_resp.status_code == 200
    assert len(raw_resp.json()) == 1
    assert raw_resp.json()[0]["category"] == "raw"

    cooked_resp = await client.get(
        "/api/inventory", params={"category": "cooked"}, cookies=cookies
    )
    assert cooked_resp.status_code == 200
    assert len(cooked_resp.json()) == 1
    assert cooked_resp.json()[0]["category"] == "cooked"

    frozen_resp = await client.get(
        "/api/inventory", params={"category": "frozen"}, cookies=cookies
    )
    assert frozen_resp.status_code == 200
    assert len(frozen_resp.json()) == 1
    assert frozen_resp.json()[0]["category"] == "frozen"


@pytest.mark.asyncio
async def test_inventory_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/inventory")
    assert response.status_code == 401

    response = await client.post(
        "/api/inventory",
        json={
            "ingredient_id": 1,
            "quantity": 1,
            "unit": "g",
            "category": "raw",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_inventory_empty(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser7", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    response = await client.get("/api/inventory", cookies=cookies)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_update_nonexistent_inventory_item(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser8", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    response = await client.put(
        "/api/inventory/9999",
        json={
            "quantity": 1,
            "unit": "g",
            "category": "raw",
        },
        cookies=cookies,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_inventory_item(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "invuser9", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    response = await client.delete("/api/inventory/9999", cookies=cookies)
    assert response.status_code == 404
