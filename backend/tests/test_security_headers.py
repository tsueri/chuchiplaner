from unittest import mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


def test_make_header_set_defaults() -> None:
    from app.core.security_headers import make_header_set

    headers = make_header_set()

    assert headers["Content-Security-Policy"] == (
        "default-src 'self'; "
        "img-src 'self' https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    )
    assert len(headers) == 5


def test_make_header_set_custom_csp() -> None:
    from app.core.security_headers import make_header_set

    custom = "default-src 'self'; img-src *"
    headers = make_header_set(csp=custom)

    assert headers["Content-Security-Policy"] == custom
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    )


@pytest.mark.asyncio
async def test_api_health_returns_security_headers() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.headers["content-security-policy"]
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "same-origin"
        assert "camera=()" in response.headers["permissions-policy"]
        assert "microphone=()" in response.headers["permissions-policy"]
        assert "geolocation=()" in response.headers["permissions-policy"]


@pytest.mark.asyncio
async def test_frame_ancestors_none_in_csp() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        csp = response.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in csp
        assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_custom_csp_via_env_replaces_header() -> None:
    custom = "default-src 'none'"
    from app.core.config import settings

    with mock.patch.object(settings, "csp", custom):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200
            assert response.headers["content-security-policy"] == custom
            assert response.headers["x-frame-options"] == "DENY"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["referrer-policy"] == "same-origin"


@pytest.mark.asyncio
async def test_spa_html_has_unsafe_inline_style() -> None:
    """Ensure the SPA HTML response contains style-src 'unsafe-inline' so
    that inline styles in the React frontend are not blocked.

    The CSP is the same for all responses (applied by middleware), so
    testing any API endpoint that returns the CSP verifies this."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        csp = response.headers["content-security-policy"]
        assert "style-src 'self' 'unsafe-inline'" in csp
