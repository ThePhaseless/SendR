import secrets
import unicodedata
import uuid
from datetime import timedelta
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.config import settings
from backend.database import get_session
from backend.models import FileUpload, User, UserTier, _utcnow
from backend.routers.altcha import verify_altcha_payload
from backend.schemas import FileListResponse, FileUploadResponse
from backend.security import get_current_user, get_optional_user

router = APIRouter(prefix="/api/files", tags=["files"])


def _sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from filename."""
    filename = filename.replace("/", "_").replace("\\", "_").replace("\0", "")
    filename = "".join(c for c in filename if unicodedata.category(c)[0] != "C")
    return filename[:255] or "unnamed"


def _get_limits(tier: UserTier) -> tuple[int, int]:
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_FILES_PER_WEEK, settings.PREMIUM_MAX_FILE_SIZE_MB
    if tier == UserTier.free:
        return settings.FREE_MAX_FILES_PER_WEEK, settings.FREE_MAX_FILE_SIZE_MB
    return settings.ANON_MAX_FILES_PER_WEEK, settings.ANON_MAX_FILE_SIZE_MB


async def _count_recent_uploads(session: AsyncSession, user_id: int) -> int:
    one_week_ago = _utcnow() - timedelta(days=7)
    stmt = (
        select(func.count())
        .select_from(FileUpload)
        .where(
            FileUpload.user_id == user_id,
            FileUpload.created_at >= one_week_ago,
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one()


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
        is_active=f.is_active,
    )


async def _get_or_create_anon_user(session: AsyncSession) -> User:
    anon_email = f"anon-{secrets.token_hex(8)}@sendr.local"
    user = User(email=anon_email, tier=UserTier.anonymous)
    session.add(user)
    await session.flush()
    return user


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
    _altcha: None = Depends(verify_altcha_payload),
) -> FileUploadResponse:
    # Create anon user if not authenticated
    if user is None:
        user = await _get_or_create_anon_user(session)

    # Get tier limits
    max_files, max_size_mb = _get_limits(user.tier)

    # Check quota
    files_used = await _count_recent_uploads(session, user.id)
    if files_used >= max_files:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload quota exceeded. Max {max_files} files per week for {user.tier.value} tier.",
        )

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
    expires_at = _utcnow() + timedelta(days=settings.FILE_EXPIRY_DAYS)

    file_upload = FileUpload(
        user_id=user.id,
        original_filename=_sanitize_filename(file.filename or "unnamed"),
        stored_filename=stored_filename,
        file_size_bytes=file_size,
        download_token=download_token,
        expires_at=expires_at,
    )
    session.add(file_upload)
    await session.commit()
    await session.refresh(file_upload)

    return _to_response(file_upload)


@router.get("/", response_model=FileListResponse)
async def list_files(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileListResponse:
    stmt = (
        select(FileUpload)
        .where(
            FileUpload.user_id == user.id,
            FileUpload.is_active == True,  # noqa: E712
        )
        .order_by(FileUpload.created_at.desc())
    )
    result = await session.execute(stmt)
    files = result.scalars().all()

    files_used = await _count_recent_uploads(session, user.id)
    max_files, _ = _get_limits(user.tier)

    return FileListResponse(
        files=[_to_response(f) for f in files],
        quota_used=files_used,
        quota_limit=max_files,
    )


@router.get("/{download_token}")
async def download_file(
    download_token: str,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(FileUpload).where(
        FileUpload.download_token == download_token,
    )
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

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
) -> FileUploadResponse:
    stmt = select(FileUpload).where(
        FileUpload.id == file_id,
        FileUpload.user_id == user.id,
    )
    result = await session.execute(stmt)
    file_upload = result.scalars().first()

    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Check quota (refresh counts toward quota)
    max_files, _ = _get_limits(user.tier)
    files_used = await _count_recent_uploads(session, user.id)
    if files_used >= max_files:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload quota exceeded. Max {max_files} files per week for {user.tier.value} tier.",
        )

    # Generate new download token
    file_upload.download_token = secrets.token_urlsafe(32)
    file_upload.download_count = 0
    file_upload.expires_at = _utcnow() + timedelta(days=settings.FILE_EXPIRY_DAYS)
    file_upload.is_active = True

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
