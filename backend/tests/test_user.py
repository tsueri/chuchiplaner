import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, username: str = "testuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    return {"cookies": resp.cookies, "data": resp.json()}


async def _create_recipe(
    client: AsyncClient, cookies, title: str = "Test Recipe"
) -> dict:
    body = {"title": title, "instructions": "Cook it.", "servings": 3}
    resp = await client.post("/api/recipes", json=body, cookies=cookies)
    return resp.json()


@pytest.mark.asyncio
async def test_user_favorites_empty(client: AsyncClient) -> None:
    auth = await _register(client, "favuser")
    cookies = auth["cookies"]

    resp = await client.get("/api/auth/user/favorites", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_favorites_with_items(client: AsyncClient) -> None:
    auth = await _register(client, "favuser2")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Favorite Dish")
    recipe_id = recipe["id"]

    await client.post(
        f"/api/recipes/{recipe_id}/favorite", cookies=cookies
    )

    resp = await client.get("/api/auth/user/favorites", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Favorite Dish"
    assert data[0]["is_favorited"] is True


@pytest.mark.asyncio
async def test_user_favorites_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/user/favorites")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_user_notes_empty(client: AsyncClient) -> None:
    auth = await _register(client, "noteuser_empty")
    cookies = auth["cookies"]

    resp = await client.get("/api/auth/user/notes", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_notes_with_items(client: AsyncClient) -> None:
    auth = await _register(client, "mynoteuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Noted Recipe")
    recipe_id = recipe["id"]

    await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "Add more garlic.", "visibility": "private"},
        cookies=cookies,
    )

    resp = await client.get("/api/auth/user/notes", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["text"] == "Add more garlic."
    assert data[0]["recipe_title"] == "Noted Recipe"
    assert data[0]["username"] == "mynoteuser"


@pytest.mark.asyncio
async def test_user_notes_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/user/notes")
    assert resp.status_code == 401
