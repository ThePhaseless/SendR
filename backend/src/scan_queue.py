from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import update
from sqlmodel import col, select

from config import settings
from database import get_session_context
from email_utils import send_malware_detected_email
from errors import normalize_http_exception_detail
from models import FileUpload, ScanStatus, User, UserTier, require_id, utcnow
from storage import storage
from virus_scanner import scan_upload_result

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from fastapi import UploadFile
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

_UPLOAD_CHUNK_SIZE = 1024 * 1024


@dataclass(slots=True)
class StagedUpload:
    temp_path: Path
    file_size: int
    content_hash: str


@dataclass(slots=True)
class StoredUpload:
    stored_filename: str
    content_hash: str
    file_size: int
    scan_status: ScanStatus
    storage_path: Path | None
    cleanup_from_storage: bool = False


def get_clean_upload_dir() -> Path:
    return Path(settings.UPLOAD_DIR)


def get_quarantine_upload_dir() -> Path:
    return Path(settings.UPLOAD_QUARANTINE_DIR)


def ensure_upload_directories() -> None:
    get_clean_upload_dir().mkdir(parents=True, exist_ok=True)
    get_quarantine_upload_dir().mkdir(parents=True, exist_ok=True)


def clean_upload_path(stored_filename: str) -> Path:
    return get_clean_upload_dir() / stored_filename


def quarantine_upload_path(stored_filename: str) -> Path:
    return get_quarantine_upload_dir() / stored_filename


def resolve_existing_upload_path(stored_filename: str) -> Path | None:
    clean_path = clean_upload_path(stored_filename)
    if clean_path.exists():
        return clean_path

    quarantine_path = quarantine_upload_path(stored_filename)
    if quarantine_path.exists():
        return quarantine_path

    return None


def resolve_storage_path(file_upload: FileUpload) -> Path:
    if file_upload.scan_status == ScanStatus.clean:
        return clean_upload_path(file_upload.stored_filename)
    return quarantine_upload_path(file_upload.stored_filename)


def aggregate_scan_status(files: list[FileUpload]) -> ScanStatus | None:
    if not files:
        return None

    statuses = {file_upload.scan_status for file_upload in files}
    for candidate in (
        ScanStatus.infected,
        ScanStatus.failed,
        ScanStatus.scanning,
        ScanStatus.queued,
    ):
        if candidate in statuses:
            return candidate

    return ScanStatus.clean


async def _find_reusable_clean_file(
    session: AsyncSession,
    content_hash: str,
    *,
    exclude_file_id: int | None = None,
) -> str | None:
    stmt = (
        select(FileUpload.stored_filename)
        .where(
            FileUpload.content_hash == content_hash,
            FileUpload.scan_status == ScanStatus.clean,
            col(FileUpload.is_active).is_(True),
        )
        .order_by(col(FileUpload.created_at).desc())
    )
    if exclude_file_id is not None:
        stmt = stmt.where(col(FileUpload.id) != exclude_file_id)

    result = await session.exec(stmt)
    for stored_filename in result.all():
        if not stored_filename:
            continue
        if settings.is_s3_configured:
            if await storage.file_exists(stored_filename):
                return stored_filename
            continue
        if clean_upload_path(stored_filename).exists():
            return stored_filename
    return None


async def stage_upload_file(
    upload_file: UploadFile,
    *,
    max_bytes: int | None = None,
    size_limit_detail: str | None = None,
) -> StagedUpload:
    ensure_upload_directories()

    target_dir = (
        get_quarantine_upload_dir()
        if settings.VIRUS_SCANNING_ENABLED
        else get_clean_upload_dir()
    )
    temp_path = target_dir / f"{uuid.uuid4()}.part"
    file_size = 0
    content_hash = sha256()

    try:
        async with aiofiles.open(temp_path, "wb") as output_file:
            while True:
                chunk = await upload_file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break

                file_size += len(chunk)
                if max_bytes is not None and file_size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=size_limit_detail or "File too large.",
                    )

                content_hash.update(chunk)
                await output_file.write(chunk)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    return StagedUpload(
        temp_path=temp_path,
        file_size=file_size,
        content_hash=content_hash.hexdigest(),
    )


async def discard_staged_uploads(staged_uploads: Sequence[StagedUpload]) -> None:
    for staged_upload in staged_uploads:
        if staged_upload.temp_path.exists():
            staged_upload.temp_path.unlink()


async def discard_stored_uploads(stored_uploads: Sequence[StoredUpload]) -> None:
    for stored_upload in stored_uploads:
        if stored_upload.storage_path and stored_upload.storage_path.exists():
            stored_upload.storage_path.unlink()
            continue
        if stored_upload.cleanup_from_storage:
            await storage.delete_file(stored_upload.stored_filename)


async def finalize_staged_upload(
    session: AsyncSession,
    staged_upload: StagedUpload,
) -> StoredUpload:
    ensure_upload_directories()

    reusable_filename = await _find_reusable_clean_file(
        session, staged_upload.content_hash
    )
    if reusable_filename:
        if staged_upload.temp_path.exists():
            staged_upload.temp_path.unlink()
        return StoredUpload(
            stored_filename=reusable_filename,
            content_hash=staged_upload.content_hash,
            file_size=staged_upload.file_size,
            scan_status=ScanStatus.clean,
            storage_path=None,
        )

    stored_filename = str(uuid.uuid4())
    if settings.VIRUS_SCANNING_ENABLED:
        if settings.is_s3_configured:
            content = await run_in_threadpool(staged_upload.temp_path.read_bytes)
            await storage.store_file(content, stored_filename)
            if staged_upload.temp_path.exists():
                staged_upload.temp_path.unlink()
            return StoredUpload(
                stored_filename=stored_filename,
                content_hash=staged_upload.content_hash,
                file_size=staged_upload.file_size,
                scan_status=ScanStatus.queued,
                storage_path=None,
                cleanup_from_storage=True,
            )

        destination = quarantine_upload_path(stored_filename)
        staged_upload.temp_path.replace(destination)
        return StoredUpload(
            stored_filename=stored_filename,
            content_hash=staged_upload.content_hash,
            file_size=staged_upload.file_size,
            scan_status=ScanStatus.queued,
            storage_path=destination,
        )

    destination = clean_upload_path(stored_filename)
    staged_upload.temp_path.replace(destination)
    return StoredUpload(
        stored_filename=stored_filename,
        content_hash=staged_upload.content_hash,
        file_size=staged_upload.file_size,
        scan_status=ScanStatus.clean,
        storage_path=destination,
    )


async def _try_claim_queued_upload(
    session: AsyncSession,
    file_id: int,
    *,
    started_at: datetime | None = None,
) -> bool:
    claim_started_at = utcnow() if started_at is None else started_at
    stmt = (
        update(FileUpload)
        .where(
            col(FileUpload.id) == file_id,
            FileUpload.scan_status == ScanStatus.queued,
            col(FileUpload.is_active).is_(True),
        )
        .values(
            scan_status=ScanStatus.scanning,
            scan_started_at=claim_started_at,
            scan_completed_at=None,
            scan_failure_code=None,
            scan_failure_message=None,
            malware_signature=None,
        )
        .execution_options(synchronize_session=False)
    )
    result = await session.exec(stmt)
    if result.rowcount != 1:
        await session.rollback()
        return False

    await session.commit()
    return True


async def claim_next_queued_upload(session: AsyncSession) -> FileUpload | None:
    while True:
        stmt = (
            select(FileUpload.id)
            .where(
                FileUpload.scan_status == ScanStatus.queued,
                col(FileUpload.is_active).is_(True),
            )
            .order_by(col(FileUpload.scan_enqueued_at), col(FileUpload.created_at))
            .limit(1)
        )
        result = await session.exec(stmt)
        file_id = result.first()
        if file_id is None:
            return None

        started_at = utcnow()
        claimed = await _try_claim_queued_upload(
            session,
            file_id,
            started_at=started_at,
        )
        if not claimed:
            continue

        return await session.get(FileUpload, file_id)


async def _mark_scan_failed(
    session: AsyncSession,
    file_upload: FileUpload,
    *,
    code: str,
    message: str,
) -> ScanStatus:
    file_upload.scan_status = ScanStatus.failed
    file_upload.scan_completed_at = utcnow()
    file_upload.scan_failure_code = code
    file_upload.scan_failure_message = message
    file_upload.malware_signature = None
    session.add(file_upload)
    await session.commit()
    return file_upload.scan_status


async def _notify_registered_owner_if_needed(
    session: AsyncSession,
    file_upload: FileUpload,
) -> None:
    if file_upload.user_id is None:
        return

    user = await session.get(User, file_upload.user_id)
    if not user or user.tier == UserTier.temporary:
        return

    try:
        await send_malware_detected_email(user.email, [file_upload.original_filename])
    except Exception:
        logger.warning("Failed to send malware notification", exc_info=True)


async def process_file_scan(file_id: int) -> ScanStatus | None:
    ensure_upload_directories()

    async with get_session_context() as session:
        file_upload = await session.get(FileUpload, file_id)
        if not file_upload:
            return None

        if file_upload.scan_status == ScanStatus.clean:
            return file_upload.scan_status

        if file_upload.scan_status == ScanStatus.queued:
            file_upload.scan_status = ScanStatus.scanning
            file_upload.scan_started_at = utcnow()
            file_upload.scan_failure_code = None
            file_upload.scan_failure_message = None
            file_upload.malware_signature = None
            session.add(file_upload)
            await session.commit()
            await session.refresh(file_upload)

        if file_upload.scan_status != ScanStatus.scanning:
            return file_upload.scan_status

        file_path = quarantine_upload_path(file_upload.stored_filename)
        downloaded_from_storage = False
        if not file_path.exists() and settings.is_s3_configured:
            try:
                await storage.download_to_path(file_upload.stored_filename, file_path)
                downloaded_from_storage = True
            except FileNotFoundError:
                return await _mark_scan_failed(
                    session,
                    file_upload,
                    code="FILE_SCAN_PAYLOAD_MISSING",
                    message="Queued file payload is missing.",
                )
        elif not file_path.exists():
            return await _mark_scan_failed(
                session,
                file_upload,
                code="FILE_SCAN_PAYLOAD_MISSING",
                message="Queued file payload is missing.",
            )

        try:
            scan_status, signature = await run_in_threadpool(
                scan_upload_result, file_path
            )
        except HTTPException as exc:
            detail = normalize_http_exception_detail(exc.detail)
            return await _mark_scan_failed(
                session,
                file_upload,
                code=detail["code"],
                message=detail["message"],
            )
        except Exception:
            logger.warning("Unexpected malware scan failure", exc_info=True)
            return await _mark_scan_failed(
                session,
                file_upload,
                code="FILE_SCAN_FAILED",
                message="Virus scanning failed. Try again later.",
            )

        if scan_status == ScanStatus.infected:
            if file_path.exists():
                file_path.unlink()
            if settings.is_s3_configured:
                await storage.delete_file(file_upload.stored_filename)
            file_upload.scan_status = ScanStatus.infected
            file_upload.scan_completed_at = utcnow()
            file_upload.scan_failure_code = "FILE_BLOCKED_MALWARE"
            file_upload.scan_failure_message = (
                "This file was blocked because malware was detected."
            )
            file_upload.malware_signature = signature
            session.add(file_upload)
            await session.commit()
            await _notify_registered_owner_if_needed(session, file_upload)
            return file_upload.scan_status

        reusable_filename = None
        if file_upload.content_hash:
            reusable_filename = await _find_reusable_clean_file(
                session,
                file_upload.content_hash,
                exclude_file_id=require_id(file_upload.id, "FileUpload"),
            )

        if reusable_filename:
            if file_path.exists():
                file_path.unlink()
            if settings.is_s3_configured:
                await storage.delete_file(file_upload.stored_filename)
            file_upload.stored_filename = reusable_filename
        elif settings.is_s3_configured:
            if downloaded_from_storage and file_path.exists():
                file_path.unlink()
        else:
            destination = clean_upload_path(file_upload.stored_filename)
            if file_path.exists():
                file_path.replace(destination)

        file_upload.scan_status = ScanStatus.clean
        file_upload.scan_completed_at = utcnow()
        file_upload.scan_failure_code = None
        file_upload.scan_failure_message = None
        file_upload.malware_signature = None
        session.add(file_upload)
        await session.commit()
        return file_upload.scan_status


async def process_next_queued_upload() -> bool:
    async with get_session_context() as session:
        file_upload = await claim_next_queued_upload(session)

    if not file_upload:
        return False

    await process_file_scan(require_id(file_upload.id, "FileUpload"))
    return True
