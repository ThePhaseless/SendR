import pytest
from httpx import ASGITransport, AsyncClient

from app import app


@pytest.mark.asyncio
async def test_get_limits_returns_basic_tier():
    """GET /api/auth/limits should return basic tier upload limits."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/auth/limits")

    assert response.status_code == 200
    data = response.json()
    assert "max_file_size_mb" in data
    assert "max_files_per_upload" in data
    assert isinstance(data["max_file_size_mb"], int)
    assert isinstance(data["max_files_per_upload"], int)
