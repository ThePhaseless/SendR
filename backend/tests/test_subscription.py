from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import database
from app import app
from config import settings
from models import AuthToken, FileUpload, User, UserTier, require_id, utcnow
from security import create_access_token, hash_token
from tasks import cleanup_expired_files


async def _create_user(tier: UserTier = UserTier.free) -> tuple[int, dict[str, str]]:
    session_factory = database.async_session
    async with session_factory() as session:
        user = User(email=f"test-{tier}-subscription@sendr.local", tier=tier)
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
    user_id: int | None,
    download_token: str,
    expires_at: datetime,
    created_at: datetime,
    is_active: bool = True,
) -> int:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{download_token}.txt"
    (upload_dir / stored_filename).write_text("subscription fixture", encoding="utf-8")

    session_factory = database.async_session
    async with session_factory() as session:
        file_upload = FileUpload(
            user_id=user_id,
            original_filename=f"{download_token}.txt",
            stored_filename=stored_filename,
            file_size_bytes=(upload_dir / stored_filename).stat().st_size,
            download_token=download_token,
            expires_at=expires_at,
            created_at=created_at,
            is_active=is_active,
            upload_group=f"group-{download_token}",
        )
        session.add(file_upload)
        await session.commit()
        await session.refresh(file_upload)
    return require_id(file_upload.id, "FileUpload")


@pytest.mark.asyncio
async def test_upgrade_to_premium_restores_recently_expired_upload():
    user_id, headers = await _create_user(UserTier.free)
    now = utcnow()
    download_token = "expired-upgrade-token"
    await _create_upload(
        user_id=user_id,
        download_token=download_token,
        expires_at=now - timedelta(days=1),
        created_at=now - timedelta(days=8),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        before_resp = await client.get(f"/api/files/{download_token}")
        assert before_resp.status_code == 410

        upgrade_resp = await client.post("/api/subscription/upgrade", headers=headers)
        assert upgrade_resp.status_code == 200

        after_resp = await client.get(f"/api/files/{download_token}")
        assert after_resp.status_code == 200

    session_factory = database.async_session
    async with session_factory() as session:
        result = await session.exec(
            select(FileUpload).where(FileUpload.download_token == download_token)
        )
        file_upload = result.first()

    assert file_upload is not None
    assert file_upload.is_active is True
    assert file_upload.expires_at > now + timedelta(days=29)


@pytest.mark.asyncio
async def test_list_files_includes_premium_uploads_within_refresh_grace():
    user_id, headers = await _create_user(UserTier.premium)
    now = utcnow()
    premium_grace_upload = "premium-grace-upload"
    upload_id = await _create_upload(
        user_id=user_id,
        download_token=premium_grace_upload,
        expires_at=now - timedelta(days=10),
        created_at=now - timedelta(days=17),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/files/", headers=headers)

    assert response.status_code == 200
    assert any(file["id"] == upload_id for file in response.json()["files"])


@pytest.mark.asyncio
async def test_cleanup_expired_files_keeps_owned_uploads_for_premium_recovery_window():
    user_id, _ = await _create_user(UserTier.free)
    now = utcnow()
    owned_token = "owned-recovery-token"
    anonymous_token = "anonymous-cleanup-token"
    owned_upload_id = await _create_upload(
        user_id=user_id,
        download_token=owned_token,
        expires_at=now - timedelta(days=10),
        created_at=now - timedelta(days=17),
    )
    anonymous_upload_id = await _create_upload(
        user_id=None,
        download_token=anonymous_token,
        expires_at=now - timedelta(days=8),
        created_at=now - timedelta(days=9),
    )

    session_factory = database.async_session
    async with session_factory() as session:
        cleaned = await cleanup_expired_files(session)

    assert cleaned == 1
    assert Path(settings.UPLOAD_DIR, f"{owned_token}.txt").exists()
    assert not Path(settings.UPLOAD_DIR, f"{anonymous_token}.txt").exists()

    async with session_factory() as session:
        result = await session.exec(
            select(FileUpload).where(FileUpload.id == owned_upload_id)
        )
        owned_upload = result.first()
        result = await session.exec(
            select(FileUpload).where(FileUpload.id == anonymous_upload_id)
        )
        anonymous_upload = result.first()

    assert owned_upload is not None
    assert owned_upload.is_active is True
    assert anonymous_upload is not None
    assert anonymous_upload.is_active is False


@pytest.mark.asyncio
async def test_get_subscription_returns_free_for_user_without_subscription():
    _, headers = await _create_user(UserTier.free)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/subscription", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["is_active"] is False
    assert data["started_at"] is None
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_get_subscription_returns_premium_after_upgrade():
    _, headers = await _create_user(UserTier.free)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upgrade_resp = await client.post("/api/subscription/upgrade", headers=headers)
        assert upgrade_resp.status_code == 200

        get_resp = await client.get("/api/subscription", headers=headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["plan"] == "premium"
        assert data["is_active"] is True
        assert data["started_at"] is not None
        assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_cancel_subscription_downgrades_to_free():
    _, headers = await _create_user(UserTier.premium)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        cancel_resp = await client.post("/api/subscription/cancel", headers=headers)
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["plan"] == "free"
        assert cancel_resp.json()["is_active"] is False

        me_resp = await client.get("/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["tier"] == "free"


@pytest.mark.asyncio
async def test_cancel_subscription_for_free_user_returns_free():
    _, headers = await _create_user(UserTier.free)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/subscription/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_upgrade_then_cancel_then_get_subscription():
    _, headers = await _create_user(UserTier.free)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upgrade_resp = await client.post("/api/subscription/upgrade", headers=headers)
        assert upgrade_resp.status_code == 200
        assert upgrade_resp.json()["plan"] == "premium"

        cancel_resp = await client.post("/api/subscription/cancel", headers=headers)
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["plan"] == "free"

        get_resp = await client.get("/api/subscription", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["plan"] == "free"
        assert get_resp.json()["is_active"] is False
