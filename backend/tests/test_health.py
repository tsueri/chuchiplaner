from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette

from app.main import create_app


@pytest.fixture
def app() -> Starlette:
    return create_app()


@pytest.fixture
async def client(app: Starlette) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
