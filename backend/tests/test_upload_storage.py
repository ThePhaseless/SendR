import asyncio
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import col, select

import database
from app import app
from config import settings
from models import AuthToken, FileUpload, ScanStatus, User, UserTier, require_id, utcnow
from routers.altcha import verify_altcha_payload
from scan_queue import (
    claim_next_queued_upload,
    clean_upload_path,
    process_file_scan,
    quarantine_upload_path,
)
from security import create_access_token, hash_token
from storage import storage
from tasks import cleanup_expired_files
from tests.utils import get_error_message


def _noop_altcha():
    return


async def _create_user_headers(tier: UserTier) -> dict[str, str]:
    async with database.async_session() as session:
        user = User(email=f"test-{tier.value}@sendr.local", tier=tier)
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


@pytest.fixture(autouse=True)
def override_altcha():
    app.dependency_overrides[verify_altcha_payload] = _noop_altcha
    yield
    app.dependency_overrides.pop(verify_altcha_payload, None)


@pytest.mark.asyncio
async def test_upload_is_queued_and_download_blocks_until_scan_completes(
    auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "VIRUS_SCANNING_ENABLED", True)
    monkeypatch.setattr(
        "scan_queue.scan_upload_result",
        lambda _content: (ScanStatus.clean, None),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_response = await client.post(
            "/api/files/upload",
            files=[("file", ("queued.txt", b"safe", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )

        assert upload_response.status_code == 201
        upload_payload = upload_response.json()
        assert upload_payload["scan_status"] == "queued"

        download_token = upload_payload["download_url"].split("/")[-1]
        info_response = await client.get(f"/api/files/{download_token}/info")
        assert info_response.status_code == 200
        assert info_response.json()["scan_status"] == "queued"

        blocked_download = await client.get(f"/api/files/{download_token}")
        assert blocked_download.status_code == 409
        assert blocked_download.json()["detail"]["code"] == "FILE_SCAN_PENDING"

    async with database.async_session() as session:
        result = await session.exec(select(FileUpload))
        file_upload = result.one()
        file_id = require_id(file_upload.id, "FileUpload")
        queued_path = quarantine_upload_path(file_upload.stored_filename)
        clean_path = clean_upload_path(file_upload.stored_filename)
        assert queued_path.exists()
        assert not clean_path.exists()

    await process_file_scan(file_id)

    async with database.async_session() as session:
        refreshed = await session.get(FileUpload, file_id)
        assert refreshed is not None
        assert refreshed.scan_status == ScanStatus.clean
        assert refreshed.scan_completed_at is not None
        assert clean_upload_path(refreshed.stored_filename).exists()
        assert not quarantine_upload_path(refreshed.stored_filename).exists()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ready_info = await client.get(f"/api/files/{download_token}/info")
        assert ready_info.status_code == 200
        assert ready_info.json()["scan_status"] == "clean"

        download_response = await client.get(f"/api/files/{download_token}")
        assert download_response.status_code == 200
        assert download_response.content == b"safe"


@pytest.mark.asyncio
async def test_infected_scan_deletes_payload_and_notifies_registered_owner(
    monkeypatch: pytest.MonkeyPatch,
):
    headers = await _create_user_headers(UserTier.free)
    monkeypatch.setattr(settings, "VIRUS_SCANNING_ENABLED", True)
    monkeypatch.setattr(
        "scan_queue.scan_upload_result",
        lambda _content: (ScanStatus.infected, "Test-Signature"),
    )

    notifications: list[tuple[str, list[str]]] = []

    async def _capture_notification(
        recipient_email: str, file_names: list[str]
    ) -> None:
        notifications.append((recipient_email, file_names))

    monkeypatch.setattr(
        "scan_queue.send_malware_detected_email",
        _capture_notification,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_response = await client.post(
            "/api/files/upload",
            files=[("file", ("infected.txt", b"bad", "text/plain"))],
            data={"altcha": "{}"},
            headers=headers,
        )

        assert upload_response.status_code == 201
        upload_payload = upload_response.json()
        assert upload_payload["scan_status"] == "queued"
        download_token = upload_payload["download_url"].split("/")[-1]

    async with database.async_session() as session:
        result = await session.exec(select(FileUpload))
        file_upload = result.one()
        file_id = require_id(file_upload.id, "FileUpload")
        queued_path = quarantine_upload_path(file_upload.stored_filename)
        assert queued_path.exists()

    await process_file_scan(file_id)

    async with database.async_session() as session:
        refreshed = await session.get(FileUpload, file_id)
        assert refreshed is not None
        assert refreshed.scan_status == ScanStatus.infected
        assert refreshed.scan_failure_code == "FILE_BLOCKED_MALWARE"
        assert refreshed.malware_signature == "Test-Signature"
        assert refreshed.scan_completed_at is not None
        assert not quarantine_upload_path(refreshed.stored_filename).exists()
        assert not clean_upload_path(refreshed.stored_filename).exists()

    assert notifications == [
        (
            "test-free@sendr.local",
            ["infected.txt"],
        )
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        info_response = await client.get(f"/api/files/{download_token}/info")
        assert info_response.status_code == 200
        assert info_response.json()["scan_status"] == "infected"

        blocked_download = await client.get(f"/api/files/{download_token}")
        assert blocked_download.status_code == 410
        assert blocked_download.json()["detail"]["code"] == "FILE_BLOCKED_MALWARE"
        assert "malware" in get_error_message(blocked_download).lower()


@pytest.mark.asyncio
async def test_s3_backed_scan_upload_stays_in_object_storage(
    auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "VIRUS_SCANNING_ENABLED", True)
    monkeypatch.setattr(settings, "SPACES_ACCESS_KEY", "spaces-key")
    monkeypatch.setattr(settings, "SPACES_SECRET_KEY", "spaces-secret")
    monkeypatch.setattr(settings, "SPACES_BUCKET_NAME", "sendr-files")
    monkeypatch.setattr(
        "scan_queue.scan_upload_result",
        lambda _content: (ScanStatus.clean, None),
    )

    object_storage: dict[str, bytes] = {}

    async def _store_file(content: bytes, filename: str | None = None) -> str:
        key = filename or str(uuid.uuid4())
        object_storage[key] = content
        return key

    async def _file_exists(filename: str) -> bool:
        return filename in object_storage

    async def _download_to_path(filename: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(object_storage[filename])

    async def _delete_file(filename: str) -> None:
        object_storage.pop(filename, None)

    monkeypatch.setattr(storage, "store_file", _store_file)
    monkeypatch.setattr(storage, "file_exists", _file_exists)
    monkeypatch.setattr(storage, "download_to_path", _download_to_path)
    monkeypatch.setattr(storage, "delete_file", _delete_file)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        upload_response = await client.post(
            "/api/files/upload",
            files=[("file", ("queued-s3.txt", b"safe", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )

        assert upload_response.status_code == 201
        assert upload_response.json()["scan_status"] == "queued"

    async with database.async_session() as session:
        result = await session.exec(select(FileUpload))
        file_upload = result.one()
        file_id = require_id(file_upload.id, "FileUpload")
        assert file_upload.stored_filename in object_storage
        assert not quarantine_upload_path(file_upload.stored_filename).exists()
        assert not clean_upload_path(file_upload.stored_filename).exists()

    await process_file_scan(file_id)

    async with database.async_session() as session:
        refreshed = await session.get(FileUpload, file_id)
        assert refreshed is not None
        assert refreshed.scan_status == ScanStatus.clean
        assert refreshed.stored_filename in object_storage
        assert not quarantine_upload_path(refreshed.stored_filename).exists()
        assert not clean_upload_path(refreshed.stored_filename).exists()


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
async def test_claim_next_queued_upload_only_claims_once_under_concurrency() -> None:
    async with database.async_session() as session:
        file_upload = FileUpload(
            original_filename="queued-race.txt",
            stored_filename="queued-race.bin",
            content_hash="race-hash",
            file_size_bytes=4,
            download_token=secrets.token_urlsafe(8),
            upload_group="group-race",
            expires_at=utcnow() + timedelta(days=1),
            scan_status=ScanStatus.queued,
            scan_enqueued_at=utcnow(),
        )
        session.add(file_upload)
        await session.commit()
        file_id = require_id(file_upload.id, "FileUpload")

    async with (
        database.async_session() as first_session,
        database.async_session() as second_session,
    ):
        first_claim, second_claim = await asyncio.gather(
            claim_next_queued_upload(first_session),
            claim_next_queued_upload(second_session),
        )

    claims = [claim for claim in (first_claim, second_claim) if claim is not None]
    assert len(claims) == 1
    assert require_id(claims[0].id, "FileUpload") == file_id
    assert claims[0].scan_status == ScanStatus.scanning

    async with database.async_session() as session:
        refreshed = await session.get(FileUpload, file_id)
        assert refreshed is not None
        assert refreshed.scan_status == ScanStatus.scanning
        assert refreshed.scan_started_at is not None


@pytest.mark.asyncio
async def test_upload_leaves_no_staging_files_after_success(
    auth_headers: dict[str, str],
):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload",
            files=[("file", ("staged.txt", b"payload", "text/plain"))],
            data={"altcha": "{}"},
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert list(Path(database.settings.UPLOAD_DIR).glob("*.part")) == []
    assert list(Path(database.settings.UPLOAD_QUARANTINE_DIR).glob("*.part")) == []


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


@pytest.mark.asyncio
async def test_cleanup_removes_expired_quarantined_file() -> None:
    stored_filename = "queued-upload.bin"
    quarantined_path = Path(database.settings.UPLOAD_QUARANTINE_DIR) / stored_filename
    quarantined_path.write_bytes(b"queued")
    expired_at = utcnow() - timedelta(days=database.settings.FILE_GRACE_PERIOD_DAYS + 1)

    async with database.async_session() as session:
        file_upload = FileUpload(
            original_filename="queued.txt",
            stored_filename=stored_filename,
            content_hash="queued123",
            file_size_bytes=6,
            download_token=secrets.token_urlsafe(8),
            upload_group="group-queued",
            expires_at=expired_at,
            scan_status=ScanStatus.queued,
            scan_enqueued_at=utcnow(),
        )
        session.add(file_upload)
        await session.commit()

        cleaned = await cleanup_expired_files(session)

    assert cleaned == 1
    assert not quarantined_path.exists()
