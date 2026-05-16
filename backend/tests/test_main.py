import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.unit
async def test_health_endpoint():
    with patch("app.main.lifespan", side_effect=lambda app: _null_lifespan(app)):
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def _null_lifespan(app: FastAPI):
    yield
