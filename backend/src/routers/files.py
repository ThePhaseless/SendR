import io
import json
import logging
import re
import secrets
import unicodedata
import uuid
import zipfile
from datetime import timedelta
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from passlib.hash import pbkdf2_sha256
from sqlmodel import func, or_, select

from config import settings
from database import get_session
from email_utils import send_file_invite_email
from models import (
    DownloadLog,
    FileUpload,
    UploadEmailRecipient,
    UploadGroupSettings,
    UploadPassword,
    User,
    UserTier,
    _utcnow,
)
from routers.altcha import verify_altcha_payload
from schemas import (
    AccessInfoResponse,
    DownloadStatEntry,
    DownloadStatsResponse,
    EmailRecipientInfo,
    FileEditRequest,
    FileListResponse,
    FileUploadResponse,
    GroupEditRequest,
    GroupRefreshRequest,
    MultiFileUploadResponse,
    PasswordInfo,
    RecipientDownloadEntry,
    RecipientStatsResponse,
    UploadGroupInfoResponse,
)
from security import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/files", tags=["files"])
logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from filename."""
    filename = filename.replace("/", "_").replace("\\", "_").replace("\0", "")
    filename = "".join(c for c in filename if unicodedata.category(c)[0] != "C")
    return filename[:255] or "unnamed"


def _get_limits(tier: UserTier) -> tuple[int, int]:
    if tier == UserTier.premium:
        return (
            settings.PREMIUM_MAX_FILE_SIZE_MB,
            settings.PREMIUM_MAX_FILES_PER_UPLOAD,
        )
    if tier == UserTier.free:
        return settings.FREE_MAX_FILE_SIZE_MB, settings.FREE_MAX_FILES_PER_UPLOAD
    return settings.TEMPORARY_MAX_FILE_SIZE_MB, settings.TEMPORARY_MAX_FILES_PER_UPLOAD


def _resolve_expiry(expiry_hours: int | None, tier: UserTier) -> timedelta:
    """Resolve the expiry duration, clamping to tier limits."""
    if expiry_hours is None:
        return timedelta(days=settings.FILE_EXPIRY_DAYS)
    if tier == UserTier.premium:
        clamped = max(settings.PREMIUM_MIN_EXPIRY_HOURS, min(expiry_hours, settings.PREMIUM_MAX_EXPIRY_HOURS))
    elif tier == UserTier.free:
        clamped = max(settings.FREE_MIN_EXPIRY_HOURS, min(expiry_hours, settings.FREE_MAX_EXPIRY_HOURS))
    else:
        # Temporary tier: pick closest allowed option
        allowed = settings.TEMPORARY_EXPIRY_OPTIONS_HOURS
        clamped = min(allowed, key=lambda h: abs(h - expiry_hours)) if allowed else 72
    return timedelta(hours=clamped)


def _resolve_max_downloads(max_downloads: int | None, tier: UserTier) -> int | None:
    """Resolve max_downloads, applying tier limits. 0 or None means unlimited."""
    if max_downloads is None or max_downloads <= 0:
        return None
    if tier == UserTier.premium:
        limit = settings.PREMIUM_MAX_DOWNLOADS_LIMIT
    elif tier == UserTier.free:
        limit = settings.FREE_MAX_DOWNLOADS_LIMIT
    else:
        allowed = settings.TEMPORARY_MAX_DOWNLOADS_OPTIONS
        if 0 in allowed and max_downloads not in allowed:
            return None
        return min(allowed, key=lambda h: abs(h - max_downloads)) if allowed else max_downloads
    return min(max_downloads, limit) if limit > 0 else max_downloads


def _build_download_url(download_token: str) -> str:
    return f"/api/files/{download_token}"


def _to_response(
    f: FileUpload,
    group_settings: UploadGroupSettings | None = None,
    password_count: int = 0,
    email_count: int = 0,
) -> FileUploadResponse:
    return FileUploadResponse(
        id=f.id,
        original_filename=f.original_filename,
        file_size_bytes=f.file_size_bytes,
        download_url=_build_download_url(f.download_token),
        expires_at=f.expires_at,
        download_count=f.download_count,
        max_downloads=f.max_downloads,
        is_active=f.is_active,
        upload_group=f.upload_group,
        is_public=group_settings.is_public if group_settings else True,
        has_passwords=password_count > 0,
        has_email_recipients=email_count > 0,
    )


def _get_password_limit(tier: UserTier) -> int:
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_PASSWORDS_PER_UPLOAD
    if tier == UserTier.free:
        return settings.FREE_MAX_PASSWORDS_PER_UPLOAD
    return settings.TEMPORARY_MAX_PASSWORDS_PER_UPLOAD


def _get_email_limit(tier: UserTier) -> int:
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_EMAILS_PER_UPLOAD
    if tier == UserTier.free:
        return settings.FREE_MAX_EMAILS_PER_UPLOAD
    return settings.TEMPORARY_MAX_EMAILS_PER_UPLOAD


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def _load_group_access(
    session,
    upload_group: str,
) -> tuple[UploadGroupSettings | None, list[UploadPassword], list[UploadEmailRecipient]]:
    """Load group settings, passwords, and email recipients."""
    gs_result = await session.execute(
        select(UploadGroupSettings).where(UploadGroupSettings.upload_group == upload_group)
    )
    group_settings = gs_result.scalars().first()

    pw_result = await session.execute(select(UploadPassword).where(UploadPassword.upload_group == upload_group))
    passwords = list(pw_result.scalars().all())

    er_result = await session.execute(
        select(UploadEmailRecipient).where(UploadEmailRecipient.upload_group == upload_group)
    )
    email_recipients = list(er_result.scalars().all())

    return group_settings, passwords, email_recipients


async def _verify_access(
    session,
    upload_group: str,
    password: str | None,
    owner_user_id: int | None,
    current_user: User | None,
) -> tuple[str, int | None, int | None]:
    """Verify download access. Returns (access_type, password_id, email_recipient_id)."""
    # Owner always has access
    if current_user and owner_user_id and current_user.id == owner_user_id:
        return "owner", None, None

    group_settings, passwords, email_recipients = await _load_group_access(session, upload_group)

    # If password provided, check against passwords and email tokens
    if password:
        for pw in passwords:
            if pbkdf2_sha256.verify(password, pw.password_hash):
                return "password", pw.id, None

        # Check email recipient tokens (SHA256-based, constant-time)
        pw_hash = sha256(password.encode()).hexdigest()
        for er in email_recipients:
            if compare_digest(pw_hash, er.token_hash):
                return "email", None, er.id

    # If public and no password required
    if group_settings and group_settings.is_public:
        return "public", None, None

    # Not public, no valid password
    if passwords or email_recipients:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password")

    # No access control configured (legacy public files) — allow
    return "public", None, None


async def _create_group_access(
    session,
    upload_group: str,
    is_public: bool,
    passwords_json: str | None,
    emails_json: str | None,
    show_email_stats: bool,
    user: User,
    title: str | None = None,
    description: str | None = None,
) -> tuple[UploadGroupSettings, int, int, list[tuple[str, str]]]:
    """Create group settings, passwords, and email recipients.

    Returns (settings, pw_count, email_count, email_tokens).
    """
    # Create group settings
    group_settings = UploadGroupSettings(
        upload_group=upload_group,
        is_public=is_public,
        show_email_stats=show_email_stats,
        title=title[:200] if title else None,
        description=description[:2000] if description else None,
    )
    session.add(group_settings)

    # Process passwords
    pw_count = 0
    if passwords_json:
        pw_list = json.loads(passwords_json)
        pw_limit = _get_password_limit(user.tier)
        if pw_limit > 0 and len(pw_list) > pw_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many passwords. Max {pw_limit} for {user.tier.value} tier.",
            )
        for pw_entry in pw_list:
            label = str(pw_entry.get("label", "Password")).strip()[:100] or "Password"
            raw_pw = pw_entry.get("password", "")
            if not raw_pw:
                continue
            session.add(
                UploadPassword(
                    upload_group=upload_group,
                    label=label,
                    password_hash=pbkdf2_sha256.hash(raw_pw),
                )
            )
            pw_count += 1

    # Process email invites
    email_count = 0
    email_tokens: list[tuple[str, str]] = []  # (email, raw_token)
    if emails_json:
        email_list = json.loads(emails_json)
        email_limit = _get_email_limit(user.tier)
        # temp users can't use email invites
        if user.tier == UserTier.temporary:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Create a free account to use email invites.",
            )
        if email_limit > 0 and len(email_list) > email_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many email invites. Max {email_limit} for {user.tier.value} tier.",
            )
        for email_addr in email_list:
            email_str = str(email_addr).strip().lower()
            if not _EMAIL_RE.match(email_str):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email address: {email_str}",
                )
            raw_token = secrets.token_urlsafe(32)
            token_hash = sha256(raw_token.encode()).hexdigest()
            session.add(
                UploadEmailRecipient(
                    upload_group=upload_group,
                    email=email_str,
                    token_hash=token_hash,
                )
            )
            email_tokens.append((email_str, raw_token))
            email_count += 1

    return group_settings, pw_count, email_count, email_tokens


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _altcha: None = Depends(verify_altcha_payload),
    expiry_hours: int | None = Form(None),
    max_downloads: int | None = Form(None),
    is_public: bool = Form(True),
    passwords: str | None = Form(None),
    emails: str | None = Form(None),
    show_email_stats: bool = Form(False),
    title: str | None = Form(None),
    description: str | None = Form(None),
) -> FileUploadResponse:
    # Get tier limits
    max_size_mb, _ = _get_limits(user.tier)

    # Read file content and check size
    content = await file.read()
    file_size = len(content)
    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {max_size_mb}MB for {user.tier.value} tier.",
        )

    # Save to disk
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = str(uuid.uuid4())
    file_path = upload_dir / stored_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create DB record
    download_token = secrets.token_urlsafe(32)
    upload_group = secrets.token_urlsafe(32)
    expires_at = _utcnow() + _resolve_expiry(expiry_hours, user.tier)
    resolved_max_downloads = _resolve_max_downloads(max_downloads, user.tier)

    file_upload = FileUpload(
        user_id=user.id,
        original_filename=_sanitize_filename(file.filename or "unnamed"),
        stored_filename=stored_filename,
        file_size_bytes=file_size,
        download_token=download_token,
        upload_group=upload_group,
        expires_at=expires_at,
        max_downloads=resolved_max_downloads,
    )
    session.add(file_upload)

    # Create access control
    group_settings, pw_count, email_count, email_tokens = await _create_group_access(
        session,
        upload_group,
        is_public,
        passwords,
        emails,
        show_email_stats,
        user,
        title=title,
        description=description,
    )

    await session.commit()
    await session.refresh(file_upload)

    # Send invite emails in background
    if email_tokens:
        group_url = f"/download/group/{upload_group}"
        file_names = [file_upload.original_filename]
        for email_addr, raw_token in email_tokens:
            try:
                await send_file_invite_email(
                    recipient_email=email_addr,
                    sender_email=user.email,
                    download_url=f"{group_url}?password={raw_token}",
                    file_names=file_names,
                )
                # Mark as notified
                stmt = select(UploadEmailRecipient).where(
                    UploadEmailRecipient.upload_group == upload_group,
                    UploadEmailRecipient.email == email_addr,
                )
                er_result = await session.execute(stmt)
                er = er_result.scalars().first()
                if er:
                    er.notified = True
                    session.add(er)
            except Exception:
                logger.warning("Failed to send invite email", exc_info=True)
        await session.commit()

    return _to_response(file_upload, group_settings, pw_count, email_count)


@router.post("/upload-multiple", status_code=status.HTTP_201_CREATED)
async def upload_multiple_files(
    files: list[UploadFile],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _altcha: None = Depends(verify_altcha_payload),
    expiry_hours: int | None = Form(None),
    max_downloads: int | None = Form(None),
    is_public: bool = Form(True),
    passwords: str | None = Form(None),
    emails: str | None = Form(None),
    show_email_stats: bool = Form(False),
    title: str | None = Form(None),
    description: str | None = Form(None),
) -> MultiFileUploadResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    # Get tier limits
    max_size_mb, max_per_upload = _get_limits(user.tier)

    # Validate number of files against per-upload limit
    if max_per_upload > 0 and len(files) > max_per_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Max {max_per_upload} files per upload for {user.tier.value} tier.",
        )

    # Read all files and validate cumulative size
    max_bytes = max_size_mb * 1024 * 1024
    file_contents: list[tuple[str, bytes]] = []
    total_size = 0
    for f in files:
        content = await f.read()
        total_size += len(content)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{f.filename}' too large. Max {max_size_mb}MB for {user.tier.value} tier.",
            )
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total file size exceeds limit. Max {max_size_mb}MB cumulative for {user.tier.value} tier.",
            )
        file_contents.append((_sanitize_filename(f.filename or "unnamed"), content))

    # Save all files
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_group = secrets.token_urlsafe(32)
    expires_at = _utcnow() + _resolve_expiry(expiry_hours, user.tier)
    resolved_max_downloads = _resolve_max_downloads(max_downloads, user.tier)
    saved_uploads: list[FileUpload] = []

    for original_name, content in file_contents:
        stored_filename = str(uuid.uuid4())
        file_path = upload_dir / stored_filename
        async with aiofiles.open(file_path, "wb") as out:
            await out.write(content)

        file_upload = FileUpload(
            user_id=user.id,
            original_filename=original_name,
            stored_filename=stored_filename,
            file_size_bytes=len(content),
            download_token=secrets.token_urlsafe(32),
            upload_group=upload_group,
            expires_at=expires_at,
            max_downloads=resolved_max_downloads,
        )
        session.add(file_upload)
        saved_uploads.append(file_upload)

    # Create access control
    group_settings, pw_count, email_count, email_tokens = await _create_group_access(
        session,
        upload_group,
        is_public,
        passwords,
        emails,
        show_email_stats,
        user,
        title=title,
        description=description,
    )

    await session.commit()
    for fu in saved_uploads:
        await session.refresh(fu)

    # Send invite emails in background
    if email_tokens:
        group_url = f"/download/group/{upload_group}"
        file_names = [fu.original_filename for fu in saved_uploads]
        for email_addr, raw_token in email_tokens:
            try:
                await send_file_invite_email(
                    recipient_email=email_addr,
                    sender_email=user.email,
                    download_url=f"{group_url}?password={raw_token}",
                    file_names=file_names,
                )
                stmt = select(UploadEmailRecipient).where(
                    UploadEmailRecipient.upload_group == upload_group,
                    UploadEmailRecipient.email == email_addr,
                )
                er_result = await session.execute(stmt)
                er = er_result.scalars().first()
                if er:
                    er.notified = True
                    session.add(er)
            except Exception:
                logger.warning("Failed to send invite email", exc_info=True)
        await session.commit()

    return MultiFileUploadResponse(
        files=[_to_response(fu, group_settings, pw_count, email_count) for fu in saved_uploads],
        upload_group=upload_group,
        total_size_bytes=total_size,
        title=group_settings.title,
        description=group_settings.description,
    )


@router.get("/group/{upload_group}")
async def get_group_info(
    upload_group: str,
    session: AsyncSession = Depends(get_session),
) -> UploadGroupInfoResponse:
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    files = list(result.scalars().all())

    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    group_settings, passwords, email_recipients = await _load_group_access(session, upload_group)
    pw_count = len(passwords)
    email_count = len(email_recipients)

    total_size = sum(f.file_size_bytes for f in files)
    return UploadGroupInfoResponse(
        files=[_to_response(f, group_settings, pw_count, email_count) for f in files],
        upload_group=upload_group,
        total_size_bytes=total_size,
        file_count=len(files),
        will_zip=len(files) > settings.GROUP_ZIP_THRESHOLD,
        is_public=group_settings.is_public if group_settings else True,
        has_passwords=pw_count > 0,
        has_email_recipients=email_count > 0,
        title=group_settings.title if group_settings else None,
        description=group_settings.description if group_settings else None,
    )


@router.get("/group/{upload_group}/download")
async def download_group(
    upload_group: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
):
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    files = list(result.scalars().all())

    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    # Access verification
    owner_user_id = files[0].user_id
    access_type, pw_id, er_id = await _verify_access(session, upload_group, password, owner_user_id, None)

    # Check expiration for all files
    now = _utcnow()
    for f in files:
        if now > f.expires_at:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Files have expired")

    if len(files) == 1:
        # Single file - serve directly
        file_path = Path(settings.UPLOAD_DIR) / files[0].stored_filename
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        files[0].download_count += 1
        session.add(files[0])
        # Log download
        session.add(
            DownloadLog(
                upload_group=upload_group,
                file_upload_id=files[0].id,
                access_type=access_type,
                upload_password_id=pw_id,
                email_recipient_id=er_id,
            )
        )
        await session.commit()
        return FileResponse(
            path=str(file_path), filename=files[0].original_filename, media_type="application/octet-stream"
        )

    # Multiple files - create zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            file_path = Path(settings.UPLOAD_DIR) / f.stored_filename
            if not file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File '{f.original_filename}' not found on disk",
                )
            zf.write(file_path, f.original_filename)
            f.download_count += 1
            session.add(f)
            session.add(
                DownloadLog(
                    upload_group=upload_group,
                    file_upload_id=f.id,
                    access_type=access_type,
                    upload_password_id=pw_id,
                    email_recipient_id=er_id,
                )
            )

    await session.commit()
    zip_buffer.seek(0)

    zip_name = f"sendr-{upload_group[:8]}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_name}"},
    )


@router.get("/", response_model=FileListResponse)
async def list_files(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileListResponse:
    now = _utcnow()
    grace_cutoff = now - timedelta(days=settings.FILE_GRACE_PERIOD_DAYS)
    stmt = (
        select(FileUpload)
        .where(
            FileUpload.user_id == user.id,
            FileUpload.is_active == True,  # noqa: E712
            # Include active files and expired files within grace period
            or_(
                FileUpload.expires_at > now,
                FileUpload.expires_at > grace_cutoff,
            ),
        )
        .order_by(FileUpload.created_at.desc())
    )
    result = await session.execute(stmt)
    files = list(result.scalars().all())

    # Load access info for each unique upload_group
    group_access_cache: dict[str, tuple[UploadGroupSettings | None, int, int]] = {}
    for f in files:
        if f.upload_group not in group_access_cache:
            gs, pws, ers = await _load_group_access(session, f.upload_group)
            group_access_cache[f.upload_group] = (gs, len(pws), len(ers))

    return FileListResponse(
        files=[_to_response(f, *group_access_cache.get(f.upload_group, (None, 0, 0))) for f in files],
    )


@router.get("/{download_token}")
async def download_file(
    download_token: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
):
    stmt = select(FileUpload).where(
        FileUpload.download_token == download_token,
    )
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Access verification
    access_type, pw_id, er_id = await _verify_access(
        session, file_upload.upload_group, password, file_upload.user_id, None
    )

    now = _utcnow()
    grace_end = file_upload.expires_at + timedelta(days=settings.FILE_GRACE_PERIOD_DAYS)

    if not file_upload.is_active:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="File has been deactivated")

    if now > file_upload.expires_at:
        if now > grace_end:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="File has expired and been removed")
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="File has expired")

    if file_upload.max_downloads and file_upload.download_count >= file_upload.max_downloads:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Download limit reached")

    # Increment download count
    file_upload.download_count += 1
    session.add(file_upload)

    # Log download
    session.add(
        DownloadLog(
            upload_group=file_upload.upload_group,
            file_upload_id=file_upload.id,
            access_type=access_type,
            upload_password_id=pw_id,
            email_recipient_id=er_id,
        )
    )
    await session.commit()

    file_path = Path(settings.UPLOAD_DIR) / file_upload.stored_filename
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=file_upload.original_filename,
        media_type="application/octet-stream",
    )


@router.get("/{download_token}/info")
async def get_file_info(
    download_token: str,
    session: AsyncSession = Depends(get_session),
) -> FileUploadResponse:
    stmt = select(FileUpload).where(FileUpload.download_token == download_token)
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    gs, pws, ers = await _load_group_access(session, file_upload.upload_group)
    return _to_response(file_upload, gs, len(pws), len(ers))


@router.post("/{file_id}/refresh")
async def refresh_download_link(
    file_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    expiry_hours: int | None = None,
) -> FileUploadResponse:
    stmt = select(FileUpload).where(
        FileUpload.id == file_id,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    now = _utcnow()

    # Free users can only refresh before expiry
    if user.tier == UserTier.free and now > file_upload.expires_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free users can only refresh uploads before they expire.",
        )

    # Premium users can refresh up to 14 days after expiry
    if user.tier == UserTier.premium and now > file_upload.expires_at + timedelta(days=14):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload expired more than 2 weeks ago and can no longer be refreshed.",
        )

    # Temporary users cannot refresh
    if user.tier == UserTier.temporary:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create a free account to refresh your uploads.",
        )

    # Generate new download token
    file_upload.download_token = secrets.token_urlsafe(32)
    file_upload.download_count = 0
    file_upload.expires_at = now + _resolve_expiry(expiry_hours, user.tier)
    file_upload.is_active = True

    session.add(file_upload)
    await session.commit()
    await session.refresh(file_upload)

    gs, pws, ers = await _load_group_access(session, file_upload.upload_group)
    return _to_response(file_upload, gs, len(pws), len(ers))


@router.patch("/{file_id}")
async def edit_file(
    file_id: int,
    body: FileEditRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileUploadResponse:
    """Edit file metadata without changing the download link. Premium only."""
    if user.tier != UserTier.premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only premium users can edit uploads.",
        )

    stmt = select(FileUpload).where(
        FileUpload.id == file_id,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if body.original_filename is not None:
        file_upload.original_filename = _sanitize_filename(body.original_filename)
    if body.expires_in_hours is not None:
        file_upload.expires_at = _utcnow() + _resolve_expiry(body.expires_in_hours, user.tier)
    if body.max_downloads is not None:
        file_upload.max_downloads = _resolve_max_downloads(body.max_downloads, user.tier)

    session.add(file_upload)
    await session.commit()
    await session.refresh(file_upload)

    gs, pws, ers = await _load_group_access(session, file_upload.upload_group)
    return _to_response(file_upload, gs, len(pws), len(ers))


@router.delete("/{file_id}", status_code=status.HTTP_200_OK)
async def deactivate_file(
    file_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    stmt = select(FileUpload).where(
        FileUpload.id == file_id,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_upload.is_active = False
    session.add(file_upload)
    await session.commit()

    return {"message": "File deactivated"}


@router.post("/group/{upload_group}/add", status_code=status.HTTP_201_CREATED)
async def add_files_to_group(
    upload_group: str,
    files: list[UploadFile],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MultiFileUploadResponse:
    """Add new files to an existing upload group. Requires ownership of the group."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    # Verify the group exists and belongs to this user
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    existing_files = list(result.scalars().all())

    if not existing_files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    # Get tier limits
    max_size_mb, max_per_upload = _get_limits(user.tier)
    max_bytes = max_size_mb * 1024 * 1024

    # Count active files in the group
    active_count = sum(1 for f in existing_files if f.is_active)
    if max_per_upload > 0 and active_count + len(files) > max_per_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Max {max_per_upload} files per upload for {user.tier.value} tier.",
        )

    # Use the same expiry/max_downloads as the first active file in the group
    reference = next((f for f in existing_files if f.is_active), existing_files[0])
    expires_at = reference.expires_at
    resolved_max_downloads = reference.max_downloads

    # Read and validate files
    file_contents: list[tuple[str, bytes]] = []
    total_size = sum(f.file_size_bytes for f in existing_files if f.is_active)
    for f in files:
        content = await f.read()
        total_size += len(content)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total file size exceeds limit. Max {max_size_mb}MB for {user.tier.value} tier.",
            )
        file_contents.append((_sanitize_filename(f.filename or "unnamed"), content))

    # Save new files
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_uploads: list[FileUpload] = []

    for original_name, content in file_contents:
        stored_filename = str(uuid.uuid4())
        file_path = upload_dir / stored_filename
        async with aiofiles.open(file_path, "wb") as out:
            await out.write(content)

        file_upload = FileUpload(
            user_id=user.id,
            original_filename=original_name,
            stored_filename=stored_filename,
            file_size_bytes=len(content),
            download_token=secrets.token_urlsafe(32),
            upload_group=upload_group,
            expires_at=expires_at,
            max_downloads=resolved_max_downloads,
        )
        session.add(file_upload)
        saved_uploads.append(file_upload)

    await session.commit()
    for fu in saved_uploads:
        await session.refresh(fu)

    gs, pws, ers = await _load_group_access(session, upload_group)
    new_total = sum(len(c) for _, c in file_contents)
    return MultiFileUploadResponse(
        files=[_to_response(fu, gs, len(pws), len(ers)) for fu in saved_uploads],
        upload_group=upload_group,
        total_size_bytes=new_total,
        title=gs.title if gs else None,
        description=gs.description if gs else None,
    )


@router.post("/group/{upload_group}/refresh")
async def refresh_group(
    upload_group: str,
    body: GroupRefreshRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MultiFileUploadResponse:
    """Refresh all files in a group: new download tokens, new expiry, reset download counts."""
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    files = list(result.scalars().all())

    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    now = _utcnow()
    reference = files[0]

    # Temporary users cannot refresh
    if user.tier == UserTier.temporary:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create a free account to refresh your uploads.",
        )

    # Free users can only refresh before expiry
    if user.tier == UserTier.free and now > reference.expires_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free users can only refresh uploads before they expire.",
        )

    # Premium users can refresh up to 14 days after expiry
    if user.tier == UserTier.premium and now > reference.expires_at + timedelta(days=14):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload expired more than 2 weeks ago and can no longer be refreshed.",
        )

    new_expiry = now + _resolve_expiry(body.expiry_hours, user.tier)
    resolved_max_downloads = (
        _resolve_max_downloads(body.max_downloads, user.tier)
        if body.max_downloads is not None
        else reference.max_downloads
    )

    for f in files:
        if not f.is_active:
            continue
        f.download_token = secrets.token_urlsafe(32)
        f.download_count = 0
        f.expires_at = new_expiry
        f.max_downloads = resolved_max_downloads
        f.is_active = True
        session.add(f)

    # Update group settings (title/description) on refresh
    if body.title is not None or body.description is not None:
        gs_stmt = select(UploadGroupSettings).where(UploadGroupSettings.upload_group == upload_group)
        gs_result = await session.execute(gs_stmt)
        gs_obj = gs_result.scalars().first()
        if gs_obj:
            if body.title is not None:
                gs_obj.title = body.title[:200] if body.title else None
            if body.description is not None:
                gs_obj.description = body.description[:2000] if body.description else None
            session.add(gs_obj)

    await session.commit()
    for f in files:
        await session.refresh(f)

    gs, pws, ers = await _load_group_access(session, upload_group)
    active_files = [f for f in files if f.is_active]
    return MultiFileUploadResponse(
        files=[_to_response(f, gs, len(pws), len(ers)) for f in active_files],
        upload_group=upload_group,
        total_size_bytes=sum(f.file_size_bytes for f in active_files),
        title=gs.title if gs else None,
        description=gs.description if gs else None,
    )


@router.patch("/group/{upload_group}")
async def edit_group(
    upload_group: str,
    body: GroupEditRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MultiFileUploadResponse:
    """Edit group settings without changing download links. Premium only."""
    if user.tier != UserTier.premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only premium users can edit uploads.",
        )

    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
        FileUpload.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    files = list(result.scalars().all())

    if not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    for f in files:
        if body.expiry_hours is not None:
            f.expires_at = _utcnow() + _resolve_expiry(body.expiry_hours, user.tier)
        if body.max_downloads is not None:
            f.max_downloads = _resolve_max_downloads(body.max_downloads, user.tier)
        session.add(f)

    # Update group settings (title/description)
    if body.title is not None or body.description is not None:
        gs_stmt = select(UploadGroupSettings).where(UploadGroupSettings.upload_group == upload_group)
        gs_result = await session.execute(gs_stmt)
        gs = gs_result.scalars().first()
        if gs:
            if body.title is not None:
                gs.title = body.title[:200] if body.title else None
            if body.description is not None:
                gs.description = body.description[:2000] if body.description else None
            session.add(gs)

    await session.commit()
    for f in files:
        await session.refresh(f)

    gs, pws, ers = await _load_group_access(session, upload_group)
    return MultiFileUploadResponse(
        files=[_to_response(f, gs, len(pws), len(ers)) for f in files],
        upload_group=upload_group,
        total_size_bytes=sum(f.file_size_bytes for f in files),
        title=gs.title if gs else None,
        description=gs.description if gs else None,
    )


@router.get("/group/{upload_group}/access-info")
async def get_access_info(
    upload_group: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessInfoResponse:
    """Get access configuration for an upload group. Owner only."""
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    group_settings, passwords, email_recipients = await _load_group_access(session, upload_group)

    return AccessInfoResponse(
        is_public=group_settings.is_public if group_settings else True,
        passwords=[PasswordInfo(id=pw.id, label=pw.label) for pw in passwords],
        emails=[EmailRecipientInfo(id=er.id, email=er.email, notified=er.notified) for er in email_recipients],
        show_email_stats=group_settings.show_email_stats if group_settings else False,
    )


@router.get("/group/{upload_group}/stats")
async def get_group_stats(
    upload_group: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DownloadStatsResponse:
    """Get download statistics for an upload group. Owner only."""
    # Verify ownership
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found")

    # Get all download logs for this group
    log_stmt = select(DownloadLog).where(DownloadLog.upload_group == upload_group)
    log_result = await session.execute(log_stmt)
    logs = list(log_result.scalars().all())

    if not logs:
        return DownloadStatsResponse(stats=[], total_downloads=0)

    # Load passwords and email recipients for label/email lookup
    _, passwords, email_recipients = await _load_group_access(session, upload_group)
    pw_map = {pw.id: pw.label for pw in passwords}
    er_map = {er.id: er.email for er in email_recipients}

    # Aggregate by (access_type, identifier)
    aggregated: dict[tuple[str, str | None], list] = {}
    for log in logs:
        identifier = None
        if log.access_type == "password" and log.upload_password_id:
            identifier = pw_map.get(log.upload_password_id, f"Password #{log.upload_password_id}")
        elif log.access_type == "email" and log.email_recipient_id:
            identifier = er_map.get(log.email_recipient_id, f"Recipient #{log.email_recipient_id}")

        key = (log.access_type, identifier)
        if key not in aggregated:
            aggregated[key] = []
        aggregated[key].append(log.downloaded_at)

    stats = []
    for (access_type, identifier), timestamps in aggregated.items():
        stats.append(
            DownloadStatEntry(
                access_type=access_type,
                identifier=identifier,
                download_count=len(timestamps),
                last_download=max(timestamps) if timestamps else None,
            )
        )

    # Sort: public first, then password, email, owner
    type_order = {"public": 0, "password": 1, "email": 2, "owner": 3}
    stats.sort(key=lambda s: (type_order.get(s.access_type, 99), s.identifier or ""))

    return DownloadStatsResponse(stats=stats, total_downloads=len(logs))


@router.get("/group/{upload_group}/recipient-stats")
async def get_recipient_stats(
    upload_group: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
) -> RecipientStatsResponse:
    """Get download stats visible to email recipients. Requires valid email token."""
    if not password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access token required")

    # Verify the token belongs to an email recipient
    token_hash = sha256(password.encode()).hexdigest()
    er_stmt = select(UploadEmailRecipient).where(
        UploadEmailRecipient.upload_group == upload_group,
    )
    er_result = await session.execute(er_stmt)
    recipients = list(er_result.scalars().all())

    matched_recipient = None
    for er in recipients:
        if compare_digest(token_hash, er.token_hash):
            matched_recipient = er
            break

    if not matched_recipient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid access token")

    # Check if stats are enabled
    gs_stmt = select(UploadGroupSettings).where(UploadGroupSettings.upload_group == upload_group)
    gs_result = await session.execute(gs_stmt)
    group_settings = gs_result.scalars().first()

    if not group_settings or not group_settings.show_email_stats:
        # Return only total count
        log_count_stmt = select(func.count(DownloadLog.id)).where(
            DownloadLog.upload_group == upload_group,
        )
        count_result = await session.execute(log_count_stmt)
        total = count_result.scalar() or 0
        return RecipientStatsResponse(downloads=[], total_downloads=total)

    # Stats enabled: return per-email breakdown (only email downloads)
    log_stmt = select(DownloadLog).where(
        DownloadLog.upload_group == upload_group,
        DownloadLog.access_type == "email",
    )
    log_result = await session.execute(log_stmt)
    email_logs = list(log_result.scalars().all())

    # Map recipient IDs to emails
    er_map = {er.id: er.email for er in recipients}

    # Aggregate by email
    email_counts: dict[str, int] = {}
    for log in email_logs:
        if log.email_recipient_id:
            email = er_map.get(log.email_recipient_id, "unknown")
            email_counts[email] = email_counts.get(email, 0) + 1

    # Include all recipients even if they have 0 downloads
    for er in recipients:
        if er.email not in email_counts:
            email_counts[er.email] = 0

    downloads = [
        RecipientDownloadEntry(email=email, download_count=count) for email, count in sorted(email_counts.items())
    ]

    # Total across all access types
    total_stmt = select(func.count(DownloadLog.id)).where(
        DownloadLog.upload_group == upload_group,
    )
    total_result = await session.execute(total_stmt)
    total = total_result.scalar() or 0

    return RecipientStatsResponse(downloads=downloads, total_downloads=total)
