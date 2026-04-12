"""Tests for the multi-access upload system (passwords, emails, public access)."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app
import database
from models import AuthToken, User, UserTier
from routers.altcha import verify_altcha_payload
from security import create_access_token, hash_token


def _noop_altcha():
    return


@pytest.fixture(autouse=True)
def _override_altcha():
    app.dependency_overrides[verify_altcha_payload] = _noop_altcha
    yield
    app.dependency_overrides.pop(verify_altcha_payload, None)


async def _create_user(tier: UserTier = UserTier.free) -> dict[str, str]:
    """Create a user of the given tier and return auth headers."""
    session_factory = database.async_session
    async with session_factory() as session:
        user = User(email=f"test-{tier}@sendr.local", tier=tier)
        session.add(user)
        await session.flush()
        raw_token, expires_at = create_access_token(user.id)
        auth_token = AuthToken(
            user_id=user.id, token=hash_token(raw_token), expires_at=expires_at
        )
        session.add(auth_token)
        await session.commit()
    return {"Authorization": f"Bearer {raw_token}"}


@pytest.fixture
async def free_headers():
    return await _create_user(UserTier.free)


@pytest.fixture
async def premium_headers():
    return await _create_user(UserTier.premium)


@pytest.fixture
async def temp_headers():
    return await _create_user(UserTier.temporary)


# ── Upload with access options ────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_public(free_headers):
    """Upload a public file (default)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/files/upload",
            files=[("file", ("test.txt", b"hello", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=free_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_public"] is True
    assert data["has_passwords"] is False
    assert data["has_email_recipients"] is False


@pytest.mark.asyncio
async def test_upload_with_passwords(free_headers):
    """Upload a file with passwords."""
    passwords = [
        {"label": "Team A", "password": "secret1"},
        {"label": "Team B", "password": "secret2"},
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/files/upload",
            files=[("file", ("test.txt", b"hello", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_passwords"] is True
    assert data["upload_group"] is not None


@pytest.mark.asyncio
async def test_upload_with_emails(free_headers):
    """Upload a file with email recipients."""
    emails = ["alice@example.com", "bob@example.com"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/files/upload",
            files=[("file", ("test.txt", b"hello", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "emails": json.dumps(emails),
            },
            headers=free_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_email_recipients"] is True


@pytest.mark.asyncio
async def test_upload_exceeds_password_limit(free_headers):
    """Free tier: max 3 passwords. Uploading 4 should fail."""
    passwords = [
        {"label": f"pw{i}", "password": f"pass{i}"} for i in range(4)
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/files/upload",
            files=[("file", ("test.txt", b"hello", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_temporary_user_cannot_use_emails(temp_headers):
    """Temporary users have 0 email limit."""
    emails = ["alice@example.com"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/files/upload",
            files=[("file", ("test.txt", b"hello", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "emails": json.dumps(emails),
            },
            headers=temp_headers,
        )
    # Temporary users have no email access - should be rejected
    assert resp.status_code in (400, 403)


# ── Password-protected download ──────────────────────────────────────


@pytest.mark.asyncio
async def test_password_protected_download(free_headers):
    """Non-public file with password: must provide correct password to download."""
    passwords = [{"label": "Main", "password": "mypass"}]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Upload
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("secret.txt", b"secret content", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        token = upload_resp.json()["download_url"].split("/")[-1]

        # Download without password should fail
        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 403

        # Download with wrong password should fail
        dl_resp = await client.get(f"/api/files/{token}?password=wrong")
        assert dl_resp.status_code == 403

        # Download with correct password should succeed
        dl_resp = await client.get(f"/api/files/{token}?password=mypass")
        assert dl_resp.status_code == 200


@pytest.mark.asyncio
async def test_public_download_no_password_needed(free_headers):
    """Public file can be downloaded without password even if passwords exist."""
    passwords = [{"label": "Extra", "password": "bonus"}]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("public.txt", b"public data", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "true",
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        token = upload_resp.json()["download_url"].split("/")[-1]

        # Public files should be downloadable without password
        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 200


# ── Group download with password ─────────────────────────────────────


@pytest.mark.asyncio
async def test_group_password_protected_download(free_headers):
    """Group download with password protection."""
    passwords = [{"label": "Team", "password": "teampass"}]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload-multiple",
            files=[
                ("files", ("a.txt", b"aaa", "text/plain")),
                ("files", ("b.txt", b"bbb", "text/plain")),
            ],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        group = upload_resp.json()["upload_group"]

        # Without password
        dl_resp = await client.get(f"/api/files/group/{group}/download")
        assert dl_resp.status_code == 403

        # With correct password
        dl_resp = await client.get(
            f"/api/files/group/{group}/download?password=teampass"
        )
        assert dl_resp.status_code == 200


# ── Access info endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_access_info(free_headers):
    """Owner can view access info for their upload."""
    passwords = [{"label": "A", "password": "pw1"}]
    emails = ["viewer@example.com"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("info.txt", b"data", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "true",
                "passwords": json.dumps(passwords),
                "emails": json.dumps(emails),
                "show_email_stats": "true",
            },
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        group = upload_resp.json()["upload_group"]

        # Get access info
        info_resp = await client.get(
            f"/api/files/group/{group}/access-info", headers=free_headers
        )
        assert info_resp.status_code == 200
        data = info_resp.json()
        assert data["is_public"] is True
        assert len(data["passwords"]) == 1
        assert data["passwords"][0]["label"] == "A"
        assert len(data["emails"]) == 1
        assert data["emails"][0]["email"] == "viewer@example.com"
        assert data["show_email_stats"] is True


@pytest.mark.asyncio
async def test_access_info_unauthorized(free_headers, temp_headers):
    """Non-owner cannot view access info."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("x.txt", b"x", "text/plain"))],
            data={"altcha": json.dumps({"mock": True})},
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        group = upload_resp.json()["upload_group"]

        # Another user should get 404 (don't leak existence)
        info_resp = await client.get(
            f"/api/files/group/{group}/access-info", headers=temp_headers
        )
        assert info_resp.status_code == 404


# ── Download stats endpoint ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_stats(free_headers):
    """Owner can view download stats after downloads."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Upload public file
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("stats.txt", b"data", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        token = upload_resp.json()["download_url"].split("/")[-1]
        group = upload_resp.json()["upload_group"]

        # Download it once
        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 200

        # Check stats
        stats_resp = await client.get(
            f"/api/files/group/{group}/stats", headers=free_headers
        )
        assert stats_resp.status_code == 200
        data = stats_resp.json()
        assert data["total_downloads"] >= 1


@pytest.mark.asyncio
async def test_download_stats_unauthorized(free_headers, temp_headers):
    """Non-owner cannot view download stats."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("x.txt", b"x", "text/plain"))],
            data={"altcha": json.dumps({"mock": True})},
            headers=free_headers,
        )
        group = upload_resp.json()["upload_group"]

        stats_resp = await client.get(
            f"/api/files/group/{group}/stats", headers=temp_headers
        )
        assert stats_resp.status_code == 404


# ── Multi-file upload with access options ────────────────────────────


@pytest.mark.asyncio
async def test_multi_upload_with_passwords(free_headers):
    """Multi-file upload with password access."""
    passwords = [{"label": "Dev", "password": "devpass"}]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/files/upload-multiple",
            files=[
                ("files", ("a.txt", b"aaa", "text/plain")),
                ("files", ("b.txt", b"bbb", "text/plain")),
            ],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    for f in data["files"]:
        assert f["has_passwords"] is True
        assert f["is_public"] is False


# ── Quota includes password/email limits ─────────────────────────────


@pytest.mark.asyncio
async def test_quota_includes_access_limits(free_headers):
    """Quota endpoint should return password/email limits."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/auth/quota", headers=free_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "max_passwords_per_upload" in data
    assert "max_emails_per_upload" in data
    # Free tier should have limits > 0 for passwords
    assert data["max_passwords_per_upload"] == 3
    assert data["max_emails_per_upload"] == 5
