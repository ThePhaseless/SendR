import pytest
from httpx import ASGITransport, AsyncClient
from app import app


@pytest.mark.asyncio
async def test_limits_includes_max_files_per_upload():
    """GET /api/auth/limits should include max_files_per_upload."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/auth/limits")
    assert response.status_code == 200
    data = response.json()
    assert "max_files_per_upload" in data
    assert isinstance(data["max_files_per_upload"], int)
    assert data["max_files_per_upload"] > 0
