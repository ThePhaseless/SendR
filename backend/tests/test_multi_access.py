"""Tests for the multi-access upload system (passwords, emails, public access)."""

import json
from hashlib import sha256

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import database
from app import app
from models import (
    AuthToken,
    DownloadLog,
    UploadEmailRecipient,
    UploadGroupSettings,
    User,
    UserTier,
)
from routers.altcha import verify_altcha_payload
from security import create_access_token, hash_token
from tests.utils import get_error_message


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
async def test_upload_rejects_password_label_without_password(free_headers):
    """Upload password labels must include a password value."""
    passwords = [{"label": "Team A", "password": ""}]
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
    assert resp.status_code == 400
    assert get_error_message(resp) == "Password label requires a password."


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
    passwords = [{"label": f"pw{i}", "password": f"pass{i}"} for i in range(4)]
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
async def test_public_flag_hides_details_but_requires_password_to_download(
    free_headers,
):
    """Public password files show info but require a password to download."""
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

        # Download without password should be rejected
        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 403

        # Public metadata remains visible without a password.
        info_resp = await client.get(f"/api/files/{token}/info")
        assert info_resp.status_code == 200
        assert info_resp.json()["original_filename"] == "public.txt"

        # Download with correct password should work
        dl_resp = await client.get(f"/api/files/{token}?password=bonus")
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


@pytest.mark.asyncio
async def test_limited_multi_file_group_disables_single_file_downloads(free_headers):
    """Limited multi-file transfers can only be downloaded as the full group."""
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
                "is_public": "true",
                "max_downloads": "1",
            },
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        first_file = upload_data["files"][0]
        assert first_file["group_download_only"] is True

        info_resp = await client.get(
            f"/api/files/{first_file['download_url'].split('/')[-1]}/info"
        )
        assert info_resp.status_code == 200
        assert info_resp.json()["group_download_only"] is True

        single_file_resp = await client.get(first_file["download_url"])
        assert single_file_resp.status_code == 403
        assert "Download the full transfer instead" in get_error_message(
            single_file_resp
        )

        group_download_resp = await client.get(
            f"/api/files/group/{upload_data['upload_group']}/download"
        )
        assert group_download_resp.status_code == 200


@pytest.mark.asyncio
async def test_owner_can_download_password_protected_group_files_without_password(
    free_headers,
):
    """Owners can download password-protected group files without a password."""
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
                "is_public": "true",
                "passwords": json.dumps(passwords),
            },
            headers=free_headers,
        )
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        group = upload_data["upload_group"]
        file_id = upload_data["files"][0]["id"]
        download_url = upload_data["files"][0]["download_url"]

        info_resp = await client.get(f"/api/files/group/{group}", headers=free_headers)
        assert info_resp.status_code == 200
        info_data = info_resp.json()
        assert info_data["viewer_is_owner"] is True
        assert len(info_data["files"]) == 2

        file_info_resp = await client.get(f"{download_url}/info", headers=free_headers)
        assert file_info_resp.status_code == 200
        assert file_info_resp.json()["viewer_is_owner"] is True

        download_resp = await client.get(download_url, headers=free_headers)
        assert download_resp.status_code == 200

    session_factory = database.async_session
    async with session_factory() as session:
        result = await session.exec(
            select(DownloadLog).where(DownloadLog.file_upload_id == file_id)
        )
        log_entry = result.first()

    assert log_entry is not None
    assert log_entry.access_type == "owner"


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


# ── Access edit endpoint ─────────────────────────────────────────────


async def _upload_with_access(
    client, headers, *, is_public=True, passwords=None, emails=None
):
    """Helper: upload a file with access settings and return upload_group."""
    data = {"altcha": json.dumps({"mock": True}), "is_public": str(is_public).lower()}
    if passwords:
        data["passwords"] = json.dumps(passwords)
    if emails:
        data["emails"] = json.dumps(emails)
    resp = await client.post(
        "/api/files/upload",
        files=[("file", ("edit.txt", b"data", "text/plain"))],
        data=data,
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["upload_group"]


@pytest.mark.asyncio
async def test_owner_file_mutation_endpoints(premium_headers):
    """Owners can refresh, edit, and deactivate a file."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("original.txt", b"data", "text/plain"))],
            data={"altcha": json.dumps({"mock": True})},
            headers=premium_headers,
        )
        assert upload_resp.status_code == 201
        file_data = upload_resp.json()

        refresh_resp = await client.post(
            f"/api/files/{file_data['id']}/refresh", headers=premium_headers
        )
        edit_resp = await client.patch(
            f"/api/files/{file_data['id']}",
            json={"original_filename": "renamed.txt", "max_downloads": 2},
            headers=premium_headers,
        )
        delete_resp = await client.delete(
            f"/api/files/{file_data['id']}", headers=premium_headers
        )

    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["download_url"] != file_data["download_url"]
    assert edit_resp.status_code == 200
    assert edit_resp.json()["original_filename"] == "renamed.txt"
    assert edit_resp.json()["max_downloads"] == 2
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "File deactivated"


@pytest.mark.asyncio
async def test_owner_group_mutation_endpoints(premium_headers):
    """Owners can add files, refresh links, and edit group metadata."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_resp = await client.post(
            "/api/files/upload-multiple",
            files=[
                ("files", ("one.txt", b"one", "text/plain")),
                ("files", ("two.txt", b"two", "text/plain")),
            ],
            data={"altcha": json.dumps({"mock": True}), "title": "Original"},
            headers=premium_headers,
        )
        assert upload_resp.status_code == 201
        group_data = upload_resp.json()
        upload_group = group_data["upload_group"]
        original_urls = {
            file_data["id"]: file_data["download_url"]
            for file_data in group_data["files"]
        }

        add_resp = await client.post(
            f"/api/files/group/{upload_group}/add",
            files=[("files", ("three.txt", b"three", "text/plain"))],
            headers=premium_headers,
        )
        refresh_resp = await client.post(
            f"/api/files/group/{upload_group}/refresh",
            json={"expiry_hours": 24, "max_downloads": 1, "title": "Refreshed"},
            headers=premium_headers,
        )
        edit_resp = await client.patch(
            f"/api/files/group/{upload_group}",
            json={
                "title": "Edited",
                "description": "Updated description",
                "max_downloads": 2,
            },
            headers=premium_headers,
        )

    assert add_resp.status_code == 201
    assert add_resp.json()["files"][0]["original_filename"] == "three.txt"
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["title"] == "Refreshed"
    refreshed_urls = {
        file_data["id"]: file_data["download_url"]
        for file_data in refresh_resp.json()["files"]
    }
    assert any(refreshed_urls[file_id] != url for file_id, url in original_urls.items())
    assert all(
        file_data["max_downloads"] == 1 for file_data in refresh_resp.json()["files"]
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["title"] == "Edited"
    assert edit_resp.json()["description"] == "Updated description"
    assert all(
        file_data["max_downloads"] == 2 for file_data in edit_resp.json()["files"]
    )


@pytest.mark.asyncio
async def test_recipient_stats_returns_email_download_counts(free_headers):
    """Email recipients can view stats when the owner enables them."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_group = await _upload_with_access(client, free_headers, is_public=False)

    raw_token = "recipient-token"
    async with database.async_session() as session:
        settings_result = await session.exec(
            select(UploadGroupSettings).where(
                UploadGroupSettings.upload_group == upload_group
            )
        )
        group_settings = settings_result.one()
        group_settings.show_email_stats = True
        session.add(group_settings)

        recipient = UploadEmailRecipient(
            upload_group=upload_group,
            email="recipient@example.com",
            token_hash=sha256(raw_token.encode()).hexdigest(),
        )
        session.add(recipient)
        await session.flush()
        session.add(
            DownloadLog(
                upload_group=upload_group,
                access_type="email",
                email_recipient_id=recipient.id,
            )
        )
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/files/group/{upload_group}/recipient-stats?password={raw_token}"
        )

    assert response.status_code == 200
    assert response.json() == {
        "downloads": [{"email": "recipient@example.com", "download_count": 1}],
        "total_downloads": 1,
    }


@pytest.mark.asyncio
async def test_edit_access_toggle_public(free_headers):
    """Can toggle is_public on an existing group."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(
            client,
            free_headers,
            is_public=True,
            passwords=[{"label": "A", "password": "pw1"}],
        )

        # Set to not public
        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"is_public": False},
            headers=free_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_public"] is False

        # Verify via access-info
        info = await client.get(
            f"/api/files/group/{group}/access-info", headers=free_headers
        )
        assert info.json()["is_public"] is False


@pytest.mark.asyncio
async def test_edit_access_add_password(free_headers):
    """Can add a new password to an existing group."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(client, free_headers, is_public=False)

        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"passwords_to_add": [{"label": "New", "password": "newpass"}]},
            headers=free_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["passwords"]) == 1
        assert resp.json()["passwords"][0]["label"] == "New"


@pytest.mark.asyncio
async def test_edit_access_rejects_password_label_without_password(free_headers):
    """Access edits must not accept a password label without a password value."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(client, free_headers, is_public=False)

        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"passwords_to_add": [{"label": "New", "password": ""}]},
            headers=free_headers,
        )
        assert resp.status_code == 400
        assert get_error_message(resp) == "Password label requires a password."


@pytest.mark.asyncio
async def test_edit_access_remove_password(free_headers):
    """Can remove a password from an existing group."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(
            client, free_headers, passwords=[{"label": "X", "password": "xpw"}]
        )

        # Get the password ID
        info = await client.get(
            f"/api/files/group/{group}/access-info", headers=free_headers
        )
        pw_id = info.json()["passwords"][0]["id"]

        # Remove it
        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"password_ids_to_remove": [pw_id]},
            headers=free_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["passwords"]) == 0


@pytest.mark.asyncio
async def test_edit_access_add_email(free_headers):
    """Can add email recipients to an existing group."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(client, free_headers, is_public=False)

        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"emails_to_add": ["new@example.com"]},
            headers=free_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["emails"]) == 1
        assert resp.json()["emails"][0]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_edit_access_remove_email(free_headers):
    """Can remove email recipients from an existing group."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(
            client, free_headers, emails=["old@example.com"]
        )

        info = await client.get(
            f"/api/files/group/{group}/access-info", headers=free_headers
        )
        email_id = info.json()["emails"][0]["id"]

        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"email_ids_to_remove": [email_id]},
            headers=free_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["emails"]) == 0


@pytest.mark.asyncio
async def test_edit_access_exceeds_password_limit(free_headers):
    """Adding passwords beyond tier limit should fail."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(
            client,
            free_headers,
            passwords=[{"label": f"pw{i}", "password": f"p{i}"} for i in range(3)],
        )

        # Free tier limit is 3, already at 3, adding 1 more should fail
        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"passwords_to_add": [{"label": "Extra", "password": "extra"}]},
            headers=free_headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_edit_access_unauthorized(free_headers, temp_headers):
    """Non-owner cannot edit access control."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(client, free_headers)

        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"is_public": False},
            headers=temp_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_edit_access_toggle_show_email_stats(free_headers):
    """Can toggle show_email_stats."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        group = await _upload_with_access(client, free_headers)

        resp = await client.patch(
            f"/api/files/group/{group}/access",
            json={"show_email_stats": True},
            headers=free_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["show_email_stats"] is True
