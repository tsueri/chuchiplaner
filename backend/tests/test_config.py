import pytest
from httpx import AsyncClient

from app.core.config import Settings


def test_settings_default_signup_disabled() -> None:
    """Settings() with no env vars yields signup_enabled=False."""
    s = Settings()
    assert s.signup_enabled is False


def test_settings_signup_enabled_true_via_env(monkeypatch) -> None:
    """CHUCHI_SIGNUP_ENABLED=true yields signup_enabled=True."""
    monkeypatch.setenv("CHUCHI_SIGNUP_ENABLED", "true")
    s = Settings()
    assert s.signup_enabled is True


def test_settings_signup_enabled_false_via_env(monkeypatch) -> None:
    """CHUCHI_SIGNUP_ENABLED=false yields signup_enabled=False."""
    monkeypatch.setenv("CHUCHI_SIGNUP_ENABLED", "false")
    s = Settings()
    assert s.signup_enabled is False


@pytest.mark.asyncio
async def test_register_403_when_signup_disabled(client: AsyncClient) -> None:
    """When signup_enabled=False, POST /api/auth/register returns 403."""
    from unittest.mock import patch

    from app.core import config

    with patch.object(config.settings, "signup_enabled", False):
        resp = await client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "secret123"},
        )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"] == "Sign-ups are closed on this instance"
