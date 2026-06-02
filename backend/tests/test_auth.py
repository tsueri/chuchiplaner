import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "secret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "session_token=" in set_cookie
    set_cookie_lower = set_cookie.lower()
    assert "httponly" in set_cookie_lower
    assert "samesite=strict" in set_cookie_lower or "samesite=lax" in set_cookie_lower


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"username": "dupuser", "password": "secret123"},
    )
    response = await client.post(
        "/api/auth/register",
        json={"username": "dupuser", "password": "another456"},
    )
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_register_missing_fields(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"username": "nopass"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"username": "loginuser", "password": "secret123"},
    )
    response = await client.post(
        "/api/auth/login",
        json={"username": "loginuser", "password": "secret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "loginuser"

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "session_token=" in set_cookie


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"username": "badpwuser", "password": "secret123"},
    )
    response = await client.post(
        "/api/auth/login",
        json={"username": "badpwuser", "password": "wrongpass"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": "nouser", "password": "secret123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "meuser", "password": "secret123"},
    )
    cookies = register_resp.cookies

    response = await client.get("/api/auth/me", cookies=cookies)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "logoutuser", "password": "secret123"},
    )
    cookies = register_resp.cookies

    response = await client.post("/api/auth/logout", cookies=cookies)
    assert response.status_code == 200

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None

    me_response = await client.get("/api/auth/me", cookies=cookies)
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_session_persists_across_requests(client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/register",
        json={"username": "persistuser", "password": "secret123"},
    )
    cookies = login_resp.cookies

    for _ in range(3):
        response = await client.get("/api/auth/me", cookies=cookies)
        assert response.status_code == 200
        assert response.json()["username"] == "persistuser"
