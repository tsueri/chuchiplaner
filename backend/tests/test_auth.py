from unittest.mock import patch

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
    assert data["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": "nouser", "password": "secret123"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid credentials"


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


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "pwuser", "password": "secret123"},
    )
    cookies = register_resp.cookies

    response = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "newsecret456"},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    await client.post("/api/auth/logout", cookies=cookies)

    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "pwuser", "password": "newsecret456"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "pwuser2", "password": "secret123"},
    )
    cookies = register_resp.cookies

    response = await client.put(
        "/api/auth/password",
        json={"current_password": "wrongpass", "new_password": "newsecret456"},
        cookies=cookies,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


@pytest.mark.asyncio
async def test_change_password_same_as_current(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "pwuser3", "password": "secret123"},
    )
    cookies = register_resp.cookies

    response = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "secret123"},
        cookies=cookies,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "New password must differ from current password"


@pytest.mark.asyncio
async def test_change_password_too_short(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "pwuser4", "password": "secret123"},
    )
    cookies = register_resp.cookies

    response = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "short"},
        cookies=cookies,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_requires_auth(client: AsyncClient) -> None:
    response = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "newsecret456"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient) -> None:
    """7-character password should be rejected (min_length=8)."""
    response = await client.post(
        "/api/auth/register",
        json={"username": "shortpw", "password": "1234567"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invite_code_bad_chars_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "badchars",
            "password": "secret123",
            "invite_code": "bad char!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_new_too_short_7chars(client: AsyncClient) -> None:
    """7-character new_password should be rejected, same as register case."""
    register_resp = await client.post(
        "/api/auth/register",
        json={"username": "pwuser5", "password": "secret123"},
    )
    cookies = register_resp.cookies
    response = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "1234567"},
        cookies=cookies,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invite_code_too_short_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "shortcode",
            "password": "secret123",
            "invite_code": "abc",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_nonexistent_identical_to_wrong_password(
    client: AsyncClient,
) -> None:
    """Unknown-user 401 response equals wrong-password 401 response."""
    await client.post(
        "/api/auth/register",
        json={"username": "identuser", "password": "secret123"},
    )
    wrong_pw_resp = await client.post(
        "/api/auth/login",
        json={"username": "identuser", "password": "wrongpass"},
    )
    nonexistent_resp = await client.post(
        "/api/auth/login",
        json={"username": "nouser", "password": "anypass"},
    )
    assert wrong_pw_resp.status_code == 401
    assert nonexistent_resp.status_code == 401
    assert wrong_pw_resp.json() == nonexistent_resp.json()


@pytest.mark.asyncio
async def test_login_constant_time_verify(
    client: AsyncClient,
) -> None:
    """Both branches call verify_password once; dummy hash for unknown user."""
    await client.post(
        "/api/auth/register",
        json={"username": "ctuser", "password": "secret123"},
    )

    from app.api import auth as auth_module

    # Nonexistent user — verify_password must be called with DUMMY_HASH
    with patch.object(
        auth_module,
        "verify_password",
        wraps=auth_module.verify_password,
    ) as mock_verify:
        await client.post(
            "/api/auth/login",
            json={"username": "nouser", "password": "somepass"},
        )
        assert mock_verify.call_count == 1
        passed_hash = mock_verify.call_args[0][1]
        assert passed_hash == auth_module._DUMMY_HASH
        assert len(passed_hash) > 0

    # Wrong password — verify_password must be called exactly once
    with patch.object(
        auth_module,
        "verify_password",
        wraps=auth_module.verify_password,
    ) as mock_verify:
        await client.post(
            "/api/auth/login",
            json={"username": "ctuser", "password": "wrongpass"},
        )
        assert mock_verify.call_count == 1


@pytest.mark.asyncio
async def test_register_invite_code_too_long_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "longcode",
            "password": "secret123",
            "invite_code": "a" * 33,
        },
    )
    assert response.status_code == 422
