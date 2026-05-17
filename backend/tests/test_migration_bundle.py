from __future__ import annotations

import hashlib
import secrets
import shutil
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from sqlmodel import func, select

import database
from config import settings
from database import build_async_engine, create_session_factory
from db_migrations import run_migrations_for_url
from migration_bundle import (
    export_bundle,
    import_bundle,
    validate_source,
    verify_target,
)
from models import (
    AuthToken,
    DownloadLog,
    FileUpload,
    ScanStatus,
    Subscription,
    SubscriptionPlan,
    Transfer,
    UploadEmailRecipient,
    UploadGroupSettings,
    UploadPassword,
    User,
    UserLogin,
    UserTier,
    VerificationCode,
    require_id,
    utcnow,
)
from scan_queue import process_file_scan
from security import hash_secret, hash_token

if TYPE_CHECKING:
    from pathlib import Path


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


@pytest.mark.asyncio
async def test_export_import_bundle_roundtrip_preserves_business_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    source_upload_dir = tmp_path / "source-uploads"
    source_quarantine_dir = tmp_path / "source-quarantine"
    target_upload_dir = tmp_path / "target-uploads"
    target_quarantine_dir = tmp_path / "target-quarantine"
    bundle_dir = tmp_path / "bundle"
    source_upload_dir.mkdir(parents=True, exist_ok=True)
    source_quarantine_dir.mkdir(parents=True, exist_ok=True)

    shared_payload = b"shared upload payload"
    queued_payload = b"queued upload payload"
    failed_payload = b"failed upload payload"
    shared_stored_filename = "shared.bin"
    queued_stored_filename = "queued.bin"
    failed_stored_filename = "failed.bin"
    infected_stored_filename = "infected.bin"
    (source_upload_dir / shared_stored_filename).write_bytes(shared_payload)
    (source_quarantine_dir / queued_stored_filename).write_bytes(queued_payload)
    (source_quarantine_dir / failed_stored_filename).write_bytes(failed_payload)
    shared_payload_hash = hashlib.sha256(shared_payload).hexdigest()
    queued_payload_hash = hashlib.sha256(queued_payload).hexdigest()
    failed_payload_hash = hashlib.sha256(failed_payload).hexdigest()
    infected_payload_hash = hashlib.sha256(b"infected payload").hexdigest()
    first_download_token = "download-token-1"
    second_download_token = "download-token-2"
    queued_download_token = "download-token-queued"
    failed_download_token = "download-token-failed"
    infected_download_token = "download-token-infected"
    source_url = _sqlite_url(source_db)
    target_url = _sqlite_url(target_db)

    run_migrations_for_url(source_url)

    source_engine = build_async_engine(source_url)
    source_session_factory = create_session_factory(source_engine)
    try:
        async with source_session_factory() as session:
            user = User(email="migrate@sendr.local", tier=UserTier.free, is_admin=True)
            session.add(user)
            await session.flush()

            user_id = require_id(user.id, "User")
            session.add(
                Subscription(
                    user_id=user_id,
                    plan=SubscriptionPlan.premium,
                    expires_at=utcnow() + timedelta(days=30),
                )
            )
            session.add(
                UserLogin(
                    user_id=user_id,
                    auth_method="email_code",
                    ip_address="127.0.0.1",
                )
            )
            session.add(
                VerificationCode(
                    email=user.email,
                    code="123456",
                    expires_at=utcnow() + timedelta(minutes=5),
                )
            )

            raw_token = secrets.token_urlsafe(16)
            session.add(
                AuthToken(
                    user_id=user_id,
                    token=hash_token(raw_token),
                    expires_at=utcnow() + timedelta(hours=2),
                )
            )

            upload_group = "group-migration"
            session.add(
                UploadGroupSettings(
                    upload_group=upload_group,
                    is_public=False,
                    title="Migrated transfer",
                    description="Roundtrip test",
                    show_email_stats=True,
                    separate_download_counts=True,
                )
            )
            password = UploadPassword(
                upload_group=upload_group,
                label="Main password",
                password_hash=hash_secret("Secret123!"),
            )
            session.add(password)
            await session.flush()

            recipient = UploadEmailRecipient(
                upload_group=upload_group,
                email="recipient@sendr.local",
                token_hash=hashlib.sha256(b"recipient-token").hexdigest(),
                notified=True,
            )
            session.add(recipient)
            await session.flush()

            first_upload = FileUpload(
                user_id=user_id,
                original_filename="first.txt",
                stored_filename=shared_stored_filename,
                content_hash=shared_payload_hash,
                file_size_bytes=len(shared_payload),
                download_token=first_download_token,
                upload_group=upload_group,
                expires_at=utcnow() + timedelta(days=1),
            )
            second_upload = FileUpload(
                user_id=user_id,
                original_filename="second.txt",
                stored_filename=shared_stored_filename,
                content_hash=shared_payload_hash,
                file_size_bytes=len(shared_payload),
                download_token=second_download_token,
                upload_group=upload_group,
                expires_at=utcnow() + timedelta(days=2),
            )
            queued_upload = FileUpload(
                user_id=user_id,
                original_filename="queued.txt",
                stored_filename=queued_stored_filename,
                content_hash=queued_payload_hash,
                file_size_bytes=len(queued_payload),
                download_token=queued_download_token,
                upload_group=upload_group,
                expires_at=utcnow() + timedelta(days=2),
                scan_status=ScanStatus.queued,
                scan_enqueued_at=utcnow(),
            )
            failed_upload = FileUpload(
                user_id=user_id,
                original_filename="failed.txt",
                stored_filename=failed_stored_filename,
                content_hash=failed_payload_hash,
                file_size_bytes=len(failed_payload),
                download_token=failed_download_token,
                upload_group=upload_group,
                expires_at=utcnow() + timedelta(days=2),
                scan_status=ScanStatus.failed,
                scan_enqueued_at=utcnow(),
                scan_started_at=utcnow(),
                scan_completed_at=utcnow(),
                scan_failure_code="FILE_SCAN_FAILED",
                scan_failure_message="Virus scanner unavailable. Try again later.",
            )
            infected_upload = FileUpload(
                user_id=user_id,
                original_filename="infected.txt",
                stored_filename=infected_stored_filename,
                content_hash=infected_payload_hash,
                file_size_bytes=len(b"infected payload"),
                download_token=infected_download_token,
                upload_group=upload_group,
                expires_at=utcnow() + timedelta(days=2),
                scan_status=ScanStatus.infected,
                scan_completed_at=utcnow(),
                scan_failure_code="FILE_BLOCKED_MALWARE",
                scan_failure_message=(
                    "This file was blocked because malware was detected."
                ),
                malware_signature="Test-Signature",
            )
            session.add(first_upload)
            session.add(second_upload)
            session.add(queued_upload)
            session.add(failed_upload)
            session.add(infected_upload)
            await session.flush()

            session.add(
                Transfer(
                    user_id=user_id,
                    upload_group=upload_group,
                    message="Bundle migration",
                    recipient_emails='["recipient@sendr.local"]',
                    password_hash=hash_secret("TransferSecret123!"),
                    notify_on_download=True,
                    expires_at=utcnow() + timedelta(days=7),
                )
            )
            session.add(
                DownloadLog(
                    upload_group=upload_group,
                    file_upload_id=require_id(first_upload.id, "FileUpload"),
                    access_type="email",
                    upload_password_id=require_id(password.id, "UploadPassword"),
                    email_recipient_id=require_id(recipient.id, "UploadEmailRecipient"),
                )
            )
            await session.commit()
    finally:
        await source_engine.dispose()

    export_result = await export_bundle(
        source_url,
        source_upload_dir,
        bundle_dir,
        quarantine_dir=source_quarantine_dir,
    )
    assert export_result.validation_report.has_errors is False
    assert export_result.validation_report.quarantine_dir == str(source_quarantine_dir)
    assert export_result.manifest["files"]["copied"] == 3

    import_result = await import_bundle(
        target_url,
        target_upload_dir,
        bundle_dir,
        quarantine_dir=target_quarantine_dir,
    )
    assert import_result.copied_files == 3
    assert import_result.skipped_files == 1
    assert (target_upload_dir / shared_stored_filename).read_bytes() == shared_payload
    assert (target_quarantine_dir / queued_stored_filename).read_bytes() == (
        queued_payload
    )
    assert (target_quarantine_dir / failed_stored_filename).read_bytes() == (
        failed_payload
    )
    assert not (target_upload_dir / infected_stored_filename).exists()
    assert not (target_quarantine_dir / infected_stored_filename).exists()

    verify_report = await verify_target(
        target_url,
        target_upload_dir,
        bundle_dir,
        quarantine_dir=target_quarantine_dir,
    )
    assert verify_report.has_errors is False

    target_engine = build_async_engine(target_url)
    target_session_factory = create_session_factory(target_engine)
    try:
        async with target_session_factory() as session:
            result = await session.exec(select(func.count()).select_from(User))
            assert int(result.one()) == 1
            result = await session.exec(select(func.count()).select_from(FileUpload))
            assert int(result.one()) == 5
            result = await session.exec(select(func.count()).select_from(DownloadLog))
            assert int(result.one()) == 1
            result = await session.exec(select(func.count()).select_from(AuthToken))
            assert int(result.one()) == 0
            result = await session.exec(
                select(func.count()).select_from(VerificationCode)
            )
            assert int(result.one()) == 0

            uploads = list(
                (await session.exec(select(FileUpload).order_by(FileUpload.id))).all()
            )
            assert [upload.download_token for upload in uploads] == [
                first_download_token,
                second_download_token,
                queued_download_token,
                failed_download_token,
                infected_download_token,
            ]
            assert uploads[0].stored_filename == shared_stored_filename
            assert uploads[1].stored_filename == shared_stored_filename
            assert uploads[2].scan_status == ScanStatus.queued
            assert uploads[3].scan_status == ScanStatus.failed
            assert uploads[4].scan_status == ScanStatus.infected

            queued_id = require_id(uploads[2].id, "FileUpload")

        monkeypatch.setattr(database, "engine", target_engine)
        monkeypatch.setattr(database, "async_session", target_session_factory)
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(target_upload_dir))
        monkeypatch.setattr(
            settings,
            "UPLOAD_QUARANTINE_DIR",
            str(target_quarantine_dir),
        )
        monkeypatch.setattr(
            "scan_queue.scan_upload_result",
            lambda _target: (ScanStatus.clean, None),
        )

        await process_file_scan(queued_id)

        async with target_session_factory() as session:
            refreshed = await session.get(FileUpload, queued_id)
            assert refreshed is not None
            assert refreshed.scan_status == ScanStatus.clean
            assert (target_upload_dir / queued_stored_filename).exists()
            assert not (target_quarantine_dir / queued_stored_filename).exists()
    finally:
        await target_engine.dispose()


@pytest.mark.asyncio
async def test_import_bundle_rolls_back_rows_and_copied_files_on_copy_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_db = tmp_path / "source-copy-failure.db"
    target_db = tmp_path / "target-copy-failure.db"
    source_upload_dir = tmp_path / "source-copy-failure-uploads"
    target_upload_dir = tmp_path / "target-copy-failure-uploads"
    target_quarantine_dir = tmp_path / "target-copy-failure-quarantine"
    bundle_dir = tmp_path / "bundle-copy-failure"
    source_upload_dir.mkdir(parents=True, exist_ok=True)

    payloads = {
        "first.bin": b"first payload",
        "second.bin": b"second payload",
    }
    for stored_filename, payload in payloads.items():
        (source_upload_dir / stored_filename).write_bytes(payload)

    source_url = _sqlite_url(source_db)
    target_url = _sqlite_url(target_db)
    run_migrations_for_url(source_url)

    source_engine = build_async_engine(source_url)
    source_session_factory = create_session_factory(source_engine)
    try:
        async with source_session_factory() as session:
            user = User(email="rollback@sendr.local", tier=UserTier.free)
            session.add(user)
            await session.flush()

            user_id = require_id(user.id, "User")
            for index, (stored_filename, payload) in enumerate(
                payloads.items(), start=1
            ):
                session.add(
                    FileUpload(
                        user_id=user_id,
                        original_filename=f"file-{index}.txt",
                        stored_filename=stored_filename,
                        content_hash=hashlib.sha256(payload).hexdigest(),
                        file_size_bytes=len(payload),
                        download_token=f"rollback-token-{index}",
                        upload_group="rollback-group",
                        expires_at=utcnow() + timedelta(days=1),
                    )
                )
            await session.commit()
    finally:
        await source_engine.dispose()

    await export_bundle(source_url, source_upload_dir, bundle_dir)

    original_copy2 = shutil.copy2
    copy_calls = 0

    def _failing_copy2(
        src: str | Path,
        dst: str | Path,
        *args: object,
        **kwargs: object,
    ):
        nonlocal copy_calls
        copy_calls += 1
        if copy_calls == 2:
            raise OSError("simulated copy failure")
        return original_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr("migration_bundle.shutil.copy2", _failing_copy2)

    with pytest.raises(OSError, match="simulated copy failure"):
        await import_bundle(
            target_url,
            target_upload_dir,
            bundle_dir,
            quarantine_dir=target_quarantine_dir,
        )

    assert list(target_upload_dir.iterdir()) == []
    assert list(target_quarantine_dir.iterdir()) == []

    target_engine = build_async_engine(target_url)
    target_session_factory = create_session_factory(target_engine)
    try:
        async with target_session_factory() as session:
            user_count = int(
                (await session.exec(select(func.count()).select_from(User))).one()
            )
            upload_count = int(
                (await session.exec(select(func.count()).select_from(FileUpload))).one()
            )
            assert user_count == 0
            assert upload_count == 0
    finally:
        await target_engine.dispose()


@pytest.mark.asyncio
async def test_validate_source_reports_missing_active_file_and_orphan_payload(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "validate.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "orphan.bin").write_bytes(b"orphan")
    database_url = _sqlite_url(database_path)
    missing_download_token = "missing-download-token"

    run_migrations_for_url(database_url)

    engine = build_async_engine(database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            file_upload = FileUpload(
                original_filename="missing.txt",
                stored_filename="missing.bin",
                content_hash=hashlib.sha256(b"missing").hexdigest(),
                file_size_bytes=7,
                download_token=missing_download_token,
                upload_group="missing-group",
                expires_at=utcnow() + timedelta(days=1),
            )
            session.add(file_upload)
            await session.commit()
    finally:
        await engine.dispose()

    report = await validate_source(database_url, upload_dir)
    issue_codes = {issue.code for issue in report.issues}

    assert report.has_errors is True
    assert "MISSING_ACTIVE_UPLOAD_FILE" in issue_codes
    assert "ORPHAN_UPLOAD_FILE" in issue_codes
