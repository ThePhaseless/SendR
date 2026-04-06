import io
import secrets
import unicodedata
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from passlib.hash import pbkdf2_sha256
from sqlmodel import or_, select

from config import settings
from database import get_session
from models import FileUpload, User, UserTier, _utcnow
from routers.altcha import verify_altcha_payload
from schemas import (
    FileEditRequest,
    FileListResponse,
    FileUploadResponse,
    GroupEditRequest,
    GroupRefreshRequest,
    MultiFileUploadResponse,
    UploadGroupInfoResponse,
)
from security import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/files", tags=["files"])


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


def _to_response(f: FileUpload) -> FileUploadResponse:
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
        has_password=f.password_hash is not None,
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _altcha: None = Depends(verify_altcha_payload),
    expiry_hours: int | None = Form(None),
    max_downloads: int | None = Form(None),
    password: str | None = Form(None),
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
    expires_at = _utcnow() + _resolve_expiry(expiry_hours, user.tier)
    resolved_max_downloads = _resolve_max_downloads(max_downloads, user.tier)

    password_hash = pbkdf2_sha256.hash(password) if password else None

    file_upload = FileUpload(
        user_id=user.id,
        original_filename=_sanitize_filename(file.filename or "unnamed"),
        stored_filename=stored_filename,
        file_size_bytes=file_size,
        download_token=download_token,
        expires_at=expires_at,
        max_downloads=resolved_max_downloads,
        password_hash=password_hash,
    )
    session.add(file_upload)
    await session.commit()
    await session.refresh(file_upload)

    return _to_response(file_upload)


@router.post("/upload-multiple", status_code=status.HTTP_201_CREATED)
async def upload_multiple_files(
    files: list[UploadFile],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _altcha: None = Depends(verify_altcha_payload),
    expiry_hours: int | None = Form(None),
    max_downloads: int | None = Form(None),
    password: str | None = Form(None),
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
    password_hash = pbkdf2_sha256.hash(password) if password else None
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
            password_hash=password_hash,
        )
        session.add(file_upload)
        saved_uploads.append(file_upload)

    await session.commit()
    for fu in saved_uploads:
        await session.refresh(fu)

    return MultiFileUploadResponse(
        files=[_to_response(fu) for fu in saved_uploads],
        upload_group=upload_group,
        total_size_bytes=total_size,
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

    total_size = sum(f.file_size_bytes for f in files)
    return UploadGroupInfoResponse(
        files=[_to_response(f) for f in files],
        upload_group=upload_group,
        total_size_bytes=total_size,
        file_count=len(files),
        will_zip=len(files) > settings.GROUP_ZIP_THRESHOLD,
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

    # Password verification (check first file's hash — all files in group share the same password)
    if files[0].password_hash and (not password or not pbkdf2_sha256.verify(password, files[0].password_hash)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password")

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
    files = result.scalars().all()

    return FileListResponse(
        files=[_to_response(f) for f in files],
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

    # Password verification
    if file_upload.password_hash and (not password or not pbkdf2_sha256.verify(password, file_upload.password_hash)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password")

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

    return _to_response(file_upload)


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

    return _to_response(file_upload)


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
    if body.remove_password:
        file_upload.password_hash = None
    elif body.password is not None:
        file_upload.password_hash = pbkdf2_sha256.hash(body.password)

    session.add(file_upload)
    await session.commit()
    await session.refresh(file_upload)

    return _to_response(file_upload)


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

    new_total = sum(len(c) for _, c in file_contents)
    return MultiFileUploadResponse(
        files=[_to_response(fu) for fu in saved_uploads],
        upload_group=upload_group,
        total_size_bytes=new_total,
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

    # Resolve password
    new_password_hash = reference.password_hash
    if body.remove_password:
        new_password_hash = None
    elif body.password is not None:
        new_password_hash = pbkdf2_sha256.hash(body.password)

    for f in files:
        if not f.is_active:
            continue
        f.download_token = secrets.token_urlsafe(32)
        f.download_count = 0
        f.expires_at = new_expiry
        f.max_downloads = resolved_max_downloads
        f.password_hash = new_password_hash
        f.is_active = True
        session.add(f)

    await session.commit()
    for f in files:
        await session.refresh(f)

    active_files = [f for f in files if f.is_active]
    return MultiFileUploadResponse(
        files=[_to_response(f) for f in active_files],
        upload_group=upload_group,
        total_size_bytes=sum(f.file_size_bytes for f in active_files),
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
        if body.remove_password:
            f.password_hash = None
        elif body.password is not None:
            f.password_hash = pbkdf2_sha256.hash(body.password)
        session.add(f)

    await session.commit()
    for f in files:
        await session.refresh(f)

    return MultiFileUploadResponse(
        files=[_to_response(f) for f in files],
        upload_group=upload_group,
        total_size_bytes=sum(f.file_size_bytes for f in files),
    )
