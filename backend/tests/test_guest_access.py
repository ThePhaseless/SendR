"""Tests for unauthenticated (guest) access patterns."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import database
from app import app
from models import AuthToken, FileUpload, User, UserTier, require_id, utcnow
from routers.altcha import verify_altcha_payload
from security import create_access_token, hash_token
from tests.utils import get_error_message


def _noop_altcha():
    return


@pytest.fixture(autouse=True)
def override_altcha():
    app.dependency_overrides[verify_altcha_payload] = _noop_altcha
    yield
    app.dependency_overrides.pop(verify_altcha_payload, None)


async def _create_user_headers(tier: UserTier = UserTier.free) -> dict[str, str]:
    async with database.async_session() as session:
        user = User(email=f"guest-test-{tier.value}@sendr.local", tier=tier)
        session.add(user)
        await session.flush()
        raw_token, expires_at = create_access_token(user.id)
        auth_token = AuthToken(
            user_id=require_id(user.id, "User"),
            token=hash_token(raw_token),
            expires_at=expires_at,
        )
        session.add(auth_token)
        await session.commit()
    return {"Authorization": f"Bearer {raw_token}"}


# ── Guest upload restrictions ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_guest_cannot_upload_single_file():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload",
            files=[("file", ("test.txt", b"hello", "text/plain"))],
            data={"altcha": json.dumps({"mock": True})},
        )
    assert response.status_code == 401
    assert get_error_message(response) == "Not authenticated"


@pytest.mark.asyncio
async def test_guest_cannot_upload_multiple_files():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload-multiple",
            files=[("files", ("a.txt", b"aaa", "text/plain"))],
            data={"altcha": json.dumps({"mock": True})},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_guest_cannot_list_files():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/files/")
    assert response.status_code == 401


# ── Guest public file access ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_guest_can_download_public_file():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("public.txt", b"public data", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=headers,
        )
        assert upload_resp.status_code == 201
        token = upload_resp.json()["download_url"].split("/")[-1]

        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 200
        assert dl_resp.content == b"public data"


@pytest.mark.asyncio
async def test_guest_can_view_public_file_info():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("info.txt", b"info data", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=headers,
        )
        token = upload_resp.json()["download_url"].split("/")[-1]

        info_resp = await client.get(f"/api/files/{token}/info")
        assert info_resp.status_code == 200
        assert info_resp.json()["original_filename"] == "info.txt"
        assert info_resp.json()["is_public"] is True


@pytest.mark.asyncio
async def test_guest_can_download_public_group():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload-multiple",
            files=[
                ("files", ("x.txt", b"xxx", "text/plain")),
                ("files", ("y.txt", b"yyy", "text/plain")),
            ],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=headers,
        )
        assert upload_resp.status_code == 201
        group = upload_resp.json()["upload_group"]

        group_resp = await client.get(f"/api/files/group/{group}/download")
        assert group_resp.status_code == 200
        assert "application/zip" in group_resp.headers.get("content-type", "")


# ── Guest private file restrictions ──────────────────────────────────


@pytest.mark.asyncio
async def test_guest_cannot_download_password_protected_file():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("secret.txt", b"secret", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "passwords": json.dumps([{"label": "Main", "password": "pw"}]),
            },
            headers=headers,
        )
        token = upload_resp.json()["download_url"].split("/")[-1]

        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 403


@pytest.mark.asyncio
async def test_guest_can_access_public_file_info_but_not_restricted_download():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("mixed.txt", b"mixed", "text/plain"))],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "true",
                "passwords": json.dumps([{"label": "X", "password": "x"}]),
            },
            headers=headers,
        )
        token = upload_resp.json()["download_url"].split("/")[-1]

        # Info is public
        info_resp = await client.get(f"/api/files/{token}/info")
        assert info_resp.status_code == 200
        assert info_resp.json()["original_filename"] == "mixed.txt"

        # Download requires password
        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 403


# ── Guest non-existent resources ─────────────────────────────────────


@pytest.mark.asyncio
async def test_guest_gets_404_for_nonexistent_file():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/files/nonexistent-token")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_guest_gets_404_for_nonexistent_group():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/files/group/nonexistent-group")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_guest_gets_404_for_nonexistent_group_download():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/files/group/nonexistent-group/download")
    assert response.status_code == 404


# ── Guest quota and limits (public, no auth) ────────────────────────


@pytest.mark.asyncio
async def test_guest_can_view_public_limits():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/auth/limits")
    assert response.status_code == 200
    data = response.json()
    assert "max_file_size_mb" in data
    assert "max_files_per_upload" in data


@pytest.mark.asyncio
async def test_guest_cannot_view_authenticated_quota():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/auth/quota")
    assert response.status_code == 401


# ── Guest access to expired/deactivated files ───────────────────────


@pytest.mark.asyncio
async def test_guest_gets_410_for_expired_file():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("expired.txt", b"expired", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=headers,
        )
        token = upload_resp.json()["download_url"].split("/")[-1]

    # Manually expire the file in DB
    async with database.async_session() as session:
        result = await session.exec(
            select(FileUpload).where(FileUpload.download_token == token)
        )
        fu = result.first()
        assert fu is not None
        fu.expires_at = utcnow() - timedelta(days=1)
        session.add(fu)
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        dl_resp = await client.get(f"/api/files/{token}")
    assert dl_resp.status_code == 410
    assert "expired" in get_error_message(dl_resp).lower()


@pytest.mark.asyncio
async def test_guest_gets_410_for_deactivated_file():
    headers = await _create_user_headers()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("deactivated.txt", b"deactivated", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=headers,
        )
        file_id = upload_resp.json()["id"]
        token = upload_resp.json()["download_url"].split("/")[-1]

        # Deactivate
        await client.delete(f"/api/files/{file_id}", headers=headers)

        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 410
        assert "deactivated" in get_error_message(dl_resp).lower()
