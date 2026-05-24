"""End-to-end integration tests covering complete user journeys."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import database
from app import app
from config import settings
from models import (
    AuthToken,
    User,
    UserTier,
    VerificationCode,
    require_id,
)
from rate_limit import auth_rate_limiter
from routers.altcha import verify_altcha_payload
from security import create_access_token, hash_token, hash_user_password
from tests.utils import get_error_message


def _noop_altcha():
    return


def _extract_csrf_value(response) -> str | None:
    """Parse the CSRF cookie value from a response's Set-Cookie headers."""
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{settings.CSRF_COOKIE_NAME}="):
            return header.split(";")[0].split("=", 1)[1]
    return None


@pytest.fixture(autouse=True)
def override_altcha():
    app.dependency_overrides[verify_altcha_payload] = _noop_altcha
    yield
    app.dependency_overrides.pop(verify_altcha_payload, None)


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter():
    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


async def _create_user_in_db(
    *,
    email: str,
    tier: UserTier = UserTier.free,
    is_admin: bool = False,
    password: str | None = None,
) -> tuple[int, dict[str, str]]:
    async with database.async_session() as session:
        user = User(
            email=email,
            tier=tier,
            is_admin=is_admin,
            password_hash=hash_user_password(password) if password else None,
        )
        session.add(user)
        await session.flush()
        user_id = require_id(user.id, "User")
        raw_token, expires_at = create_access_token(user_id)
        auth_token = AuthToken(
            user_id=user_id,
            token=hash_token(raw_token),
            expires_at=expires_at,
        )
        session.add(auth_token)
        await session.commit()
    return user_id, {"Authorization": f"Bearer {raw_token}"}


# ── Full account lifecycle ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_account_creation_and_password_login_flow():
    """Full journey: request code -> verify -> set password -> login -> me -> logout."""
    email = "new-user@sendr.local"
    original_env = settings.ENVIRONMENT
    original_smtp = settings.SMTP_HOST
    settings.ENVIRONMENT = "test"
    settings.SMTP_HOST = ""

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Step 1: Request verification code
            request_resp = await client.post(
                "/api/auth/request-code", json={"email": email}
            )
            assert request_resp.status_code == 200
            assert request_resp.json() == {"message": "Verification code sent"}

            # Retrieve the code from DB
            async with database.async_session() as session:
                result = await session.exec(
                    select(VerificationCode).where(VerificationCode.email == email)
                )
                vc = result.first()
                assert vc is not None
                code = vc.code

            # Step 2: Verify code and create account
            verify_resp = await client.post(
                "/api/auth/verify-code",
                json={"email": email, "code": code, "create_account": True},
            )
            assert verify_resp.status_code == 200
            assert verify_resp.json()["expires_at"].endswith("Z")
            assert settings.SESSION_COOKIE_NAME in verify_resp.headers.get(
                "set-cookie", ""
            )
            csrf_value = _extract_csrf_value(verify_resp)
            assert csrf_value is not None

            # Step 3: /me should work and show no password yet
            me_resp = await client.get("/api/auth/me")
            assert me_resp.status_code == 200
            me_data = me_resp.json()
            assert me_data["email"] == email
            assert me_data["tier"] == "free"
            assert me_data["has_password"] is False
            csrf_value = _extract_csrf_value(me_resp) or csrf_value

            # Step 4: Set password (needs CSRF when session cookie is present)
            set_pw_resp = await client.post(
                "/api/auth/set-password",
                json={"password": "SecurePass123"},
                headers={settings.CSRF_HEADER_NAME: csrf_value},
            )
            assert set_pw_resp.status_code == 200
            assert set_pw_resp.json()["has_password"] is True
            csrf_value = _extract_csrf_value(set_pw_resp) or csrf_value

            # Step 5: Logout clears session
            logout_resp = await client.post(
                "/api/auth/logout",
                headers={settings.CSRF_HEADER_NAME: csrf_value},
            )
            assert logout_resp.status_code == 200
            logout_cookie = logout_resp.headers.get("set-cookie", "")
            assert settings.SESSION_COOKIE_NAME in logout_cookie
            assert "Max-Age=0" in logout_cookie

            # Step 6: /me should now fail
            me_after_logout = await client.get("/api/auth/me")
            assert me_after_logout.status_code == 401

            # Step 7: Login with password
            login_resp = await client.post(
                "/api/auth/login-password",
                json={"email": email, "password": "SecurePass123"},
            )
            assert login_resp.status_code == 200
            assert settings.SESSION_COOKIE_NAME in login_resp.headers.get(
                "set-cookie", ""
            )

            # Step 8: /me works again
            me_after_login = await client.get("/api/auth/me")
            assert me_after_login.status_code == 200
            assert me_after_login.json()["has_password"] is True
    finally:
        settings.ENVIRONMENT = original_env
        settings.SMTP_HOST = original_smtp


@pytest.mark.asyncio
async def test_full_upload_download_and_manage_flow(auth_headers: dict[str, str]):
    """Upload a file, download it, view info, list files, then deactivate."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Upload
        upload_resp = await client.post(
            "/api/files/upload",
            files=[("file", ("flow.txt", b"flow content", "text/plain"))],
            data={"altcha": json.dumps({"mock": True}), "is_public": "true"},
            headers=auth_headers,
        )
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        token = upload_data["download_url"].split("/")[-1]
        file_id = upload_data["id"]
        upload_group = upload_data["upload_group"]

        # Download as guest (public file)
        dl_resp = await client.get(f"/api/files/{token}")
        assert dl_resp.status_code == 200
        assert dl_resp.content == b"flow content"

        # File info
        info_resp = await client.get(f"/api/files/{token}/info")
        assert info_resp.status_code == 200
        assert info_resp.json()["original_filename"] == "flow.txt"

        # Group info
        group_resp = await client.get(f"/api/files/group/{upload_group}")
        assert group_resp.status_code == 200
        assert group_resp.json()["file_count"] == 1

        # List files (authenticated)
        list_resp = await client.get("/api/files/", headers=auth_headers)
        assert list_resp.status_code == 200
        assert any(f["id"] == file_id for f in list_resp.json()["files"])

        # Deactivate file
        delete_resp = await client.delete(f"/api/files/{file_id}", headers=auth_headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json()["message"] == "File deactivated"

        # Download should now fail with 410
        dl_after_delete = await client.get(f"/api/files/{token}")
        assert dl_after_delete.status_code == 410


@pytest.mark.asyncio
async def test_full_admin_user_lifecycle():
    """Admin creates a user, promotes them, bans them, and deletes them."""
    admin_id, admin_headers = await _create_user_in_db(
        email="admin-lifecycle@sendr.local",
        tier=UserTier.premium,
        is_admin=True,
    )
    user_id, user_headers = await _create_user_in_db(
        email="target-user@sendr.local",
        tier=UserTier.free,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # List users should include both
        list_resp = await client.get("/api/admin/users", headers=admin_headers)
        assert list_resp.status_code == 200
        users = list_resp.json()["users"]
        emails = {u["email"] for u in users}
        assert "admin-lifecycle@sendr.local" in emails
        assert "target-user@sendr.local" in emails

        # Promote user to premium
        patch_resp = await client.patch(
            f"/api/admin/users/{user_id}",
            json={"tier": "premium"},
            headers=admin_headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["tier"] == "premium"

        # Ban the user
        ban_resp = await client.patch(
            f"/api/admin/users/{user_id}",
            json={"is_banned": True},
            headers=admin_headers,
        )
        assert ban_resp.status_code == 200
        assert ban_resp.json()["is_banned"] is True

        # Banned user cannot access /me
        me_resp = await client.get("/api/auth/me", headers=user_headers)
        assert me_resp.status_code == 403
        assert get_error_message(me_resp) == "Account is banned"

        # Admin can delete the user
        delete_resp = await client.delete(
            f"/api/admin/users/{user_id}", headers=admin_headers
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["message"] == "User deleted"

        # User is gone
        async with database.async_session() as session:
            result = await session.exec(select(User).where(User.id == user_id))
            assert result.first() is None


@pytest.mark.asyncio
async def test_full_group_upload_with_access_control_and_stats(
    auth_headers: dict[str, str],
):
    """Multi-file upload with passwords, download, and stats verification."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Upload with password
        upload_resp = await client.post(
            "/api/files/upload-multiple",
            files=[
                ("files", ("a.txt", b"aaa", "text/plain")),
                ("files", ("b.txt", b"bbb", "text/plain")),
            ],
            data={
                "altcha": json.dumps({"mock": True}),
                "is_public": "false",
                "passwords": json.dumps([{"label": "Team", "password": "secret"}]),
            },
            headers=auth_headers,
        )
        assert upload_resp.status_code == 201
        group = upload_resp.json()["upload_group"]

        # Guest without password gets 403 on download
        dl_no_pw = await client.get(f"/api/files/group/{group}/download")
        assert dl_no_pw.status_code == 403

        # Download with password succeeds
        dl_with_pw = await client.get(
            f"/api/files/group/{group}/download",
            headers={"X-Access-Token": "secret"},
        )
        assert dl_with_pw.status_code == 200

        # Stats should reflect one download
        stats_resp = await client.get(
            f"/api/files/group/{group}/stats", headers=auth_headers
        )
        assert stats_resp.status_code == 200
        stats_data = stats_resp.json()
        assert stats_data["total_downloads"] == 1


@pytest.mark.asyncio
async def test_full_password_change_flow():
    """Create user with password, change password, old password fails, new works."""
    email = "password-change@sendr.local"
    _, headers = await _create_user_in_db(email=email, password="OriginalPass123")  # noqa: S106

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Change password using Bearer auth (no session cookie = no CSRF needed)
        change_resp = await client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OriginalPass123",
                "new_password": "UpdatedPass456",
            },
            headers=headers,
        )
        assert change_resp.status_code == 200
        assert change_resp.json()["has_password"] is True

        # Old password should fail
        old_login = await client.post(
            "/api/auth/login-password",
            json={"email": email, "password": "OriginalPass123"},
        )
        assert old_login.status_code == 401

        # New password should succeed
        new_login = await client.post(
            "/api/auth/login-password",
            json={"email": email, "password": "UpdatedPass456"},
        )
        assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_full_subscription_upgrade_and_cancel():
    """User upgrades to premium, verifies tier change, then cancels."""
    _, headers = await _create_user_in_db(
        email="sub-user@sendr.local", tier=UserTier.free
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Get subscription (should be free)
        get_resp = await client.get("/api/subscription", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["plan"] == "free"
        assert get_resp.json()["is_active"] is False

        # Upgrade to premium
        upgrade_resp = await client.post("/api/subscription/upgrade", headers=headers)
        assert upgrade_resp.status_code == 200
        assert upgrade_resp.json()["plan"] == "premium"
        assert upgrade_resp.json()["is_active"] is True

        # /me reflects premium
        me_resp = await client.get("/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["tier"] == "premium"

        # Cancel subscription
        cancel_resp = await client.post("/api/subscription/cancel", headers=headers)
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["plan"] == "free"
        assert cancel_resp.json()["is_active"] is False

        # /me reflects free again
        me_after = await client.get("/api/auth/me", headers=headers)
        assert me_after.status_code == 200
        assert me_after.json()["tier"] == "free"


@pytest.mark.asyncio
async def test_full_temporary_to_free_upgrade():
    """Temporary user verifies code with create_account=True upgrades to free."""
    email = "temp-upgrade@sendr.local"
    original_env = settings.ENVIRONMENT
    original_smtp = settings.SMTP_HOST
    settings.ENVIRONMENT = "test"
    settings.SMTP_HOST = ""

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Request code
            await client.post("/api/auth/request-code", json={"email": email})

            async with database.async_session() as session:
                result = await session.exec(
                    select(VerificationCode).where(VerificationCode.email == email)
                )
                code = result.first().code

            # Verify without create_account -> temporary
            verify_temp = await client.post(
                "/api/auth/verify-code",
                json={"email": email, "code": code, "create_account": False},
            )
            assert verify_temp.status_code == 200
            me_temp = await client.get("/api/auth/me")
            assert me_temp.json()["tier"] == "temporary"
            # get_me refreshes the CSRF cookie; use the latest value
            csrf_value = _extract_csrf_value(me_temp) or _extract_csrf_value(
                verify_temp
            )
            assert csrf_value is not None

            # Request another code (needs CSRF because session cookie exists)
            await client.post(
                "/api/auth/request-code",
                json={"email": email},
                headers={settings.CSRF_HEADER_NAME: csrf_value},
            )

            async with database.async_session() as session:
                result = await session.exec(
                    select(VerificationCode)
                    .where(VerificationCode.email == email)
                    .order_by(VerificationCode.id.desc())
                )
                vc = result.first()
                code = vc.code

            # Verify with create_account -> free (needs CSRF)
            verify_free = await client.post(
                "/api/auth/verify-code",
                json={"email": email, "code": code, "create_account": True},
                headers={settings.CSRF_HEADER_NAME: csrf_value},
            )
            assert verify_free.status_code == 200
            me_free = await client.get("/api/auth/me")
            assert me_free.json()["tier"] == "free"
    finally:
        settings.ENVIRONMENT = original_env
        settings.SMTP_HOST = original_smtp
