from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import database
from app import app
from models import (
    AuthToken,
    FileUpload,
    User,
    UserLogin,
    UserTier,
    VerificationCode,
    require_id,
    utcnow,
)
from security import create_access_token, hash_token
from tests.utils import get_error_message


async def _create_user(
    *,
    email: str,
    tier: UserTier = UserTier.free,
    is_admin: bool = False,
    is_banned: bool = False,
) -> tuple[int, dict[str, str]]:
    session_factory = database.async_session
    async with session_factory() as session:
        user = User(email=email, tier=tier, is_admin=is_admin, is_banned=is_banned)
        session.add(user)
        await session.flush()
        user_id = require_id(user.id, "User")
        raw_token, expires_at = create_access_token(user.id)
        auth_token = AuthToken(
            user_id=user_id,
            token=hash_token(raw_token),
            expires_at=expires_at,
        )
        session.add(auth_token)
        await session.commit()
    return user_id, {"Authorization": f"Bearer {raw_token}"}


async def _create_upload(
    *,
    user_id: int,
    upload_group: str,
    download_token: str,
    name: str,
    download_count: int = 0,
    expires_at: datetime | None = None,
    file_size_bytes: int = 123,
) -> None:
    session_factory = database.async_session
    async with session_factory() as session:
        session.add(
            FileUpload(
                user_id=user_id,
                original_filename=name,
                stored_filename=f"{download_token}.bin",
                file_size_bytes=file_size_bytes,
                download_token=download_token,
                download_count=download_count,
                upload_group=upload_group,
                expires_at=expires_at or (utcnow() + timedelta(days=2)),
            )
        )
        await session.commit()


async def _create_login(
    *,
    user_id: int,
    auth_method: str,
    ip_address: str,
    logged_in_at: datetime | None = None,
) -> None:
    session_factory = database.async_session
    async with session_factory() as session:
        session.add(
            UserLogin(
                user_id=user_id,
                auth_method=auth_method,
                ip_address=ip_address,
                logged_in_at=logged_in_at or utcnow(),
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_ban_user_and_block_existing_session():
    admin_id, admin_headers = await _create_user(
        email="admin@sendr.local",
        tier=UserTier.premium,
        is_admin=True,
    )
    user_id, user_headers = await _create_user(email="user@sendr.local")

    assert admin_id != user_id

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/admin/users/{user_id}",
            json={"is_banned": True},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_banned"] is True

        me_response = await client.get("/api/auth/me", headers=user_headers)
        assert me_response.status_code == 403
        assert get_error_message(me_response) == "Account is banned"


@pytest.mark.asyncio
async def test_admin_cannot_ban_own_account():
    admin_id, admin_headers = await _create_user(
        email="self-admin@sendr.local",
        tier=UserTier.premium,
        is_admin=True,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/admin/users/{admin_id}",
            json={"is_banned": True},
            headers=admin_headers,
        )

    assert response.status_code == 400
    assert get_error_message(response) == "Cannot ban your own account"


@pytest.mark.asyncio
async def test_banned_user_cannot_request_or_verify_code():
    banned_email = "banned@sendr.local"
    await _create_user(email=banned_email, is_banned=True)

    session_factory = database.async_session
    async with session_factory() as session:
        session.add(
            VerificationCode(
                email=banned_email,
                code="123456",
                expires_at=utcnow() + timedelta(minutes=5),
            )
        )
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        request_code_response = await client.post(
            "/api/auth/request-code",
            json={"email": banned_email},
        )
        assert request_code_response.status_code == 403
        assert get_error_message(request_code_response) == "Account is banned"

        verify_code_response = await client.post(
            "/api/auth/verify-code",
            json={"email": banned_email, "code": "123456", "create_account": False},
        )

    assert verify_code_response.status_code == 403
    assert get_error_message(verify_code_response) == "Account is banned"


@pytest.mark.asyncio
async def test_verify_code_records_login_event():
    email = "login-record@sendr.local"
    session_factory = database.async_session
    async with session_factory() as session:
        session.add(
            VerificationCode(
                email=email,
                code="654321",
                expires_at=utcnow() + timedelta(minutes=5),
            )
        )
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/auth/verify-code",
            json={"email": email, "code": "654321", "create_account": True},
            headers={"x-forwarded-for": "203.0.113.10"},
        )

    assert response.status_code == 200

    async with session_factory() as session:
        user_result = await session.exec(select(User).where(User.email == email))
        user = user_result.first()
        assert user is not None
        user_id = require_id(user.id, "User")
        login_result = await session.exec(
            select(UserLogin).where(UserLogin.user_id == user_id)
        )
        login = login_result.first()

    assert login is not None
    assert login.auth_method == "verification_code"
    assert login.ip_address == "203.0.113.10"


@pytest.mark.asyncio
async def test_admin_can_list_and_delete_user_transfers():
    _, admin_headers = await _create_user(
        email="uploads-admin@sendr.local",
        tier=UserTier.premium,
        is_admin=True,
    )
    user_id, _ = await _create_user(email="uploads-user@sendr.local")
    upload_group = "admin-transfer-group"
    first_transfer_token = "admin-transfer-a-file"
    second_transfer_token = "admin-transfer-b-file"
    await _create_upload(
        user_id=user_id,
        upload_group=upload_group,
        download_token=first_transfer_token,
        name="first.txt",
    )
    await _create_upload(
        user_id=user_id,
        upload_group=upload_group,
        download_token=second_transfer_token,
        name="second.txt",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        list_response = await client.get(
            f"/api/admin/users/{user_id}/uploads", headers=admin_headers
        )
        assert list_response.status_code == 200
        assert len(list_response.json()["files"]) == 2

        delete_response = await client.delete(
            f"/api/admin/users/{user_id}/transfers/{upload_group}",
            headers=admin_headers,
        )
        assert delete_response.status_code == 200

        after_response = await client.get(
            f"/api/admin/users/{user_id}/uploads", headers=admin_headers
        )
        assert after_response.status_code == 200
        assert after_response.json()["files"] == []

    session_factory = database.async_session
    async with session_factory() as session:
        result = await session.exec(
            select(FileUpload).where(FileUpload.upload_group == upload_group)
        )
        uploads = result.all()

    assert uploads
    assert all(upload.is_active is False for upload in uploads)


@pytest.mark.asyncio
async def test_admin_can_list_user_logins_and_stats():
    _, admin_headers = await _create_user(
        email="stats-admin@sendr.local",
        tier=UserTier.premium,
        is_admin=True,
    )
    user_id, _ = await _create_user(email="stats-user@sendr.local")
    now = utcnow()
    active_upload_token = "stats-active-file"
    expired_upload_token = "stats-expired-file"

    await _create_upload(
        user_id=user_id,
        upload_group="stats-group-active",
        download_token=active_upload_token,
        name="active.txt",
        download_count=2,
        expires_at=now + timedelta(days=2),
        file_size_bytes=120,
    )
    await _create_upload(
        user_id=user_id,
        upload_group="stats-group-expired",
        download_token=expired_upload_token,
        name="expired.txt",
        download_count=5,
        expires_at=now - timedelta(days=1),
        file_size_bytes=180,
    )
    await _create_login(
        user_id=user_id,
        auth_method="verification_code",
        ip_address="198.51.100.10",
        logged_in_at=now - timedelta(days=1),
    )
    await _create_login(
        user_id=user_id,
        auth_method="dev_login",
        ip_address="198.51.100.11",
        logged_in_at=now,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        logins_response = await client.get(
            f"/api/admin/users/{user_id}/logins", headers=admin_headers
        )
        assert logins_response.status_code == 200
        logins = logins_response.json()["logins"]
        assert len(logins) == 2
        assert logins[0]["auth_method"] == "dev_login"
        assert logins[0]["ip_address"] == "198.51.100.11"

        stats_response = await client.get(
            f"/api/admin/users/{user_id}/stats", headers=admin_headers
        )
        assert stats_response.status_code == 200
        stats = stats_response.json()

    assert stats["total_transfers"] == 2
    assert stats["active_transfers"] == 1
    assert stats["total_files_uploaded"] == 2
    assert stats["total_uploaded_bytes"] == 300
    assert stats["total_downloads"] == 7
    assert stats["login_count"] == 2
    assert stats["last_login_at"] is not None
