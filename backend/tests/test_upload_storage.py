import secrets
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient
from sqlmodel import col, select

import database
from app import app
from models import FileUpload, utcnow
from routers.altcha import verify_altcha_payload
from tasks import cleanup_expired_files
from tests.utils import get_error_message


def _noop_altcha():
    return


@pytest.fixture(autouse=True)
def override_altcha():
    app.dependency_overrides[verify_altcha_payload] = _noop_altcha
    yield
    app.dependency_overrides.pop(verify_altcha_payload, None)


@pytest.mark.asyncio
async def test_upload_rejects_detected_malware(
    auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    def _raise_detected(_content: bytes) -> None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload blocked: malware detected (Test-Signature).",
        )

    monkeypatch.setattr("routers.files.scan_upload_content", _raise_detected)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload",
            files=[("file", ("infected.txt", b"bad", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert "malware detected" in get_error_message(response)


@pytest.mark.asyncio
async def test_duplicate_uploads_reuse_stored_file(auth_headers: dict[str, str]):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first_response = await client.post(
            "/api/files/upload",
            files=[("file", ("first.txt", b"same-content", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )
        second_response = await client.post(
            "/api/files/upload",
            files=[("file", ("second.txt", b"same-content", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    async with database.async_session() as session:
        result = await session.exec(select(FileUpload).order_by(col(FileUpload.id)))
        uploads = list(result.all())

    assert len(uploads) == 2
    assert uploads[0].content_hash == uploads[1].content_hash
    assert uploads[0].stored_filename == uploads[1].stored_filename


@pytest.mark.asyncio
async def test_upload_response_serializes_expiry_as_utc(auth_headers: dict[str, str]):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload",
            files=[("file", ("timezone.txt", b"payload", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert response.json()["expires_at"].endswith("Z")


@pytest.mark.asyncio
async def test_cleanup_removes_shared_file_only_after_last_active_reference() -> None:
    stored_filename = "shared-upload.bin"
    shared_path = Path(database.settings.UPLOAD_DIR) / stored_filename
    shared_path.write_bytes(b"shared")
    expired_at = utcnow() - timedelta(days=database.settings.FILE_GRACE_PERIOD_DAYS + 1)
    active_until = utcnow() + timedelta(days=1)

    async with database.async_session() as session:
        first = FileUpload(
            original_filename="first.txt",
            stored_filename=stored_filename,
            content_hash="abc123",
            file_size_bytes=6,
            download_token=secrets.token_urlsafe(8),
            upload_group="group-1",
            expires_at=expired_at,
        )
        second = FileUpload(
            original_filename="second.txt",
            stored_filename=stored_filename,
            content_hash="abc123",
            file_size_bytes=6,
            download_token=secrets.token_urlsafe(8),
            upload_group="group-2",
            expires_at=active_until,
        )
        session.add(first)
        session.add(second)
        await session.commit()

        cleaned = await cleanup_expired_files(session)
        assert cleaned == 1
        assert shared_path.exists()

        result = await session.exec(select(FileUpload).order_by(col(FileUpload.id)))
        uploads = list(result.all())
        assert uploads[0].is_active is False
        assert uploads[1].is_active is True

        uploads[1].expires_at = expired_at
        session.add(uploads[1])
        await session.commit()

        cleaned = await cleanup_expired_files(session)
        assert cleaned == 1

    assert not shared_path.exists()
