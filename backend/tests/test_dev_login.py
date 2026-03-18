import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from config import settings


@pytest.mark.asyncio
async def test_dev_login_disabled_by_default():
    """POST /api/dev/login/user should return 404 when DEV_MODE is False."""
    original = settings.DEV_MODE
    settings.DEV_MODE = False
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/dev/login/user")
        # When DEV_MODE is False, the router is not even registered (returns 404)
        assert response.status_code == 404
    finally:
        settings.DEV_MODE = original


@pytest.mark.asyncio
async def test_dev_login_invalid_role():
    """POST /api/dev/login/invalid should return 400 or 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/dev/login/invalid")
    # Should be 404 (router not registered) or 400 (invalid role)
    assert response.status_code in (400, 404)
