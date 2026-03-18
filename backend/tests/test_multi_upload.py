import json
import pytest
from httpx import ASGITransport, AsyncClient
from app import app
from routers.altcha import verify_altcha_payload


def _noop_altcha():
    """No-op override for the altcha verification dependency."""
    return None


@pytest.fixture(autouse=True)
def _override_altcha():
    """Override altcha verification for all tests in this module."""
    app.dependency_overrides[verify_altcha_payload] = _noop_altcha
    yield
    app.dependency_overrides.pop(verify_altcha_payload, None)


@pytest.mark.asyncio
async def test_upload_multiple_no_files_returns_400():
    """POST /api/files/upload-multiple with no files should return 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/files/upload-multiple",
            data={"altcha": json.dumps({"mock": True})},
        )
    # 400 or 422 for missing files
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_multiple_success():
    """POST /api/files/upload-multiple should upload multiple files."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("test1.txt", b"hello world 1", "text/plain")),
            ("files", ("test2.txt", b"hello world 2", "text/plain")),
        ]
        response = await client.post(
            "/api/files/upload-multiple",
            files=files,
            data={"altcha": json.dumps({"mock": True})},
        )
    assert response.status_code == 201
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 2
    assert "upload_group" in data
    assert "total_size_bytes" in data
    assert data["total_size_bytes"] > 0
    # Each file should have upload_group set
    for f in data["files"]:
        assert f["upload_group"] == data["upload_group"]


@pytest.mark.asyncio
async def test_group_info():
    """GET /api/files/group/{group} should return group info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First upload files
        files = [
            ("files", ("a.txt", b"aaa", "text/plain")),
            ("files", ("b.txt", b"bbb", "text/plain")),
        ]
        upload_resp = await client.post(
            "/api/files/upload-multiple",
            files=files,
            data={"altcha": json.dumps({"mock": True})},
        )
        assert upload_resp.status_code == 201
        upload_group = upload_resp.json()["upload_group"]

        # Get group info
        info_resp = await client.get(f"/api/files/group/{upload_group}")
        assert info_resp.status_code == 200
        data = info_resp.json()
        assert data["file_count"] == 2
        assert data["upload_group"] == upload_group
        assert "will_zip" in data


@pytest.mark.asyncio
async def test_group_download():
    """GET /api/files/group/{group}/download should return file or zip."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = [
            ("files", ("x.txt", b"xxx", "text/plain")),
            ("files", ("y.txt", b"yyy", "text/plain")),
        ]
        upload_resp = await client.post(
            "/api/files/upload-multiple",
            files=files,
            data={"altcha": json.dumps({"mock": True})},
        )
        assert upload_resp.status_code == 201
        upload_group = upload_resp.json()["upload_group"]

        # Download group
        dl_resp = await client.get(f"/api/files/group/{upload_group}/download")
        assert dl_resp.status_code == 200
        # Multiple files should return a zip
        assert "application/zip" in dl_resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_group_not_found():
    """GET /api/files/group/nonexistent should return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/files/group/nonexistent")
    assert response.status_code == 404
