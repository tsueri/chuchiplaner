import hmac
import logging
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


def test_verify_admin_signup_code_correct() -> None:
    from app.services.auth import verify_admin_signup_code

    original = settings.admin_signup_code
    settings.admin_signup_code = "correct"
    try:
        assert verify_admin_signup_code("correct") is True
    finally:
        settings.admin_signup_code = original


def test_verify_admin_signup_code_wrong() -> None:
    from app.services.auth import verify_admin_signup_code

    original = settings.admin_signup_code
    settings.admin_signup_code = "correct"
    try:
        assert verify_admin_signup_code("wrong") is False
        assert verify_admin_signup_code("") is False
        assert verify_admin_signup_code(None) is False
    finally:
        settings.admin_signup_code = original


def test_verify_admin_signup_code_empty_config() -> None:
    from app.services.auth import verify_admin_signup_code

    original = settings.admin_signup_code
    settings.admin_signup_code = ""
    try:
        assert verify_admin_signup_code("correct") is False
        assert verify_admin_signup_code("") is False
    finally:
        settings.admin_signup_code = original


def test_verify_admin_signup_code_uses_compare_digest() -> None:
    from app.services import auth as auth_services

    original = settings.admin_signup_code
    settings.admin_signup_code = "secret"
    try:
        with patch.object(hmac, "compare_digest", wraps=hmac.compare_digest) as mock_cd:
            auth_services.verify_admin_signup_code("secret")
            mock_cd.assert_called_once_with("secret", "secret")
    finally:
        settings.admin_signup_code = original


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
    assert "secure" not in set_cookie_lower


@pytest.mark.asyncio
async def test_register_cookie_no_secure_by_default(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "nosecure",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    set_cookie_lower = set_cookie.lower()
    assert "secure" not in set_cookie_lower


@pytest.mark.asyncio
async def test_login_cookie_default_attributes(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "username": "cookiedef",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    response = await client.post(
        "/api/auth/login",
        json={"username": "cookiedef", "password": "secret123"},
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    set_cookie_lower = set_cookie.lower()
    assert "httponly" in set_cookie_lower
    assert "samesite=strict" in set_cookie_lower
    assert "secure" not in set_cookie_lower
    assert "max-age=604800" in set_cookie_lower


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "username": "dupuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "dupuser",
            "password": "another456",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "loginuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "badpwuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "meuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "logoutuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "persistuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "pwuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "pwuser2",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "pwuser3",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "pwuser4",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "pwuser5",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "identuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "ctuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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


@pytest.mark.asyncio
async def test_session_middleware_does_not_log_cookies(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="session")

    await client.post(
        "/api/auth/register",
        json={
            "username": "logtest",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    await client.post(
        "/api/auth/login",
        json={"username": "logtest", "password": "secret123"},
    )

    for record in caplog.records:
        msg = record.getMessage()
        assert "session_token" not in msg, (
            f"Log record at {record.levelname} contains session_token: {msg}"
        )
        assert "set-cookie" not in msg.lower(), (
            f"Log record at {record.levelname} contains set-cookie: {msg}"
        )


@pytest.mark.asyncio
async def test_register_admin_signup_code_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "adminsignup1",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "adminsignup1"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_register_admin_signup_code_wrong(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "adminsignup2",
            "password": "secret123",
            "admin_signup_code": "wrong-code",
        },
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_register_no_code_when_configured(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"username": "noruser", "password": "secret123"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_register_invite_code_still_works(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.services.household import create_household

    household = await create_household(db_session, "Test Household")
    invite = household.invite_code

    response = await client.post(
        "/api/auth/register",
        json={
            "username": "inviteduser",
            "password": "secret123",
            "invite_code": invite,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "inviteduser"
    assert data["role"] == "member"


@pytest.mark.asyncio
async def test_register_invite_code_invalid(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "badinvite",
            "password": "secret123",
            "invite_code": "invalid-code",
        },
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_register_no_code_unconfigured(client: AsyncClient) -> None:
    original = settings.admin_signup_code
    settings.admin_signup_code = ""
    try:
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "noconfiguser",
                "password": "secret123",
            },
        )
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
    finally:
        settings.admin_signup_code = original


@pytest.mark.asyncio
async def test_register_wrong_code_does_not_reveal_username_taken(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "username": "existing2",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "existing2",
            "password": "secret123",
            "admin_signup_code": "wrong-code",
        },
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert "username" not in data.get("detail", "").lower()
