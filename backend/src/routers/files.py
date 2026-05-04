import io
import json
import logging
import re
import secrets
import shutil
import threading
import unicodedata
import uuid
import zipfile
from collections.abc import Mapping
from datetime import datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from queue import Full, Queue
from typing import TYPE_CHECKING, Annotated, cast
from urllib.parse import quote

import aiofiles
from fastapi import (
    APIRouter,
    Depends,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import update
from sqlmodel import col, func, or_, select

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
    require_id,
    utcnow,
)
from routers.altcha import verify_altcha_payload
from schemas import (
    AccessEditRequest,
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
from security import get_current_user, get_optional_user, hash_secret, verify_secret
from virus_scanner import scan_upload_content

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/api/files", tags=["files"])
logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from filename."""
    filename = filename.replace("/", "_").replace("\\", "_").replace("\0", "")
    filename = "".join(c for c in filename if unicodedata.category(c)[0] != "C")
    return filename[:255] or "unnamed"


def _sanitize_archive_path(filename: str) -> str:
    parts = [
        _sanitize_filename(part).strip().strip(". ")
        for part in filename.replace("\\", "/").split("/")
        if part.strip() and part not in (".", "..")
    ]
    return "/".join(parts)[:255] or "unnamed"


def _build_group_archive_name(upload_group: str, title: str | None) -> str:
    raw_name = title.strip() if title else ""
    fallback_name = f"sendr-{upload_group[:8]}"
    base_name = (
        _sanitize_filename(raw_name or fallback_name).strip().strip(". ")
        or fallback_name
    )
    if base_name.lower().endswith(".zip"):
        return base_name
    return f"{base_name}.zip"


def _build_attachment_header(filename: str) -> str:
    ascii_fallback = (
        filename.encode("ascii", "ignore").decode("ascii") or "download.zip"
    )
    ascii_fallback = ascii_fallback.replace('"', "")
    return (
        f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"
    )


def _group_downloads_as_archive(files: list[FileUpload]) -> bool:
    return len(files) > 1 or any("/" in f.original_filename for f in files)


class _QueuedZipWriter(io.RawIOBase):
    def __init__(
        self, output_queue: Queue[bytes | Exception | None], stop_event: threading.Event
    ):
        self._output_queue = output_queue
        self._stop_event = stop_event
        self._position = 0

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._position

    def flush(self) -> None:
        return None

    def write(self, data: ReadableBuffer) -> int:
        chunk = bytes(data)
        self._position += len(chunk)
        if not chunk:
            return 0

        while True:
            if self._stop_event.is_set():
                raise BrokenPipeError("Archive stream closed")
            try:
                self._output_queue.put(chunk, timeout=0.1)
                return len(chunk)
            except Full:
                continue


def _stream_group_archive(files: list[tuple[Path, str]]):
    output_queue: Queue[bytes | Exception | None] = Queue(maxsize=8)
    stop_event = threading.Event()

    def _write_archive() -> None:
        writer = _QueuedZipWriter(output_queue, stop_event)
        try:
            with zipfile.ZipFile(
                writer, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for file_path, archive_name in files:
                    with (
                        file_path.open("rb") as source,
                        archive.open(archive_name, "w") as target,
                    ):
                        shutil.copyfileobj(source, target, length=64 * 1024)
        except BrokenPipeError:
            return
        except Exception as exc:
            while True:
                if stop_event.is_set():
                    return
                try:
                    output_queue.put(exc, timeout=0.1)
                    break
                except Full:
                    continue
        finally:
            while True:
                if stop_event.is_set():
                    break
                try:
                    output_queue.put(None, timeout=0.1)
                    break
                except Full:
                    continue

    worker = threading.Thread(
        target=_write_archive, name="sendr-group-archive", daemon=True
    )
    worker.start()

    try:
        while True:
            item = output_queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        stop_event.set()
        worker.join(timeout=1)


def _get_limits(tier: UserTier) -> tuple[int, int]:
    if tier == UserTier.premium:
        return (
            settings.PREMIUM_MAX_FILE_SIZE_MB,
            settings.PREMIUM_MAX_FILES_PER_UPLOAD,
        )
    if tier == UserTier.free:
        return settings.FREE_MAX_FILE_SIZE_MB, settings.FREE_MAX_FILES_PER_UPLOAD
    return settings.TEMPORARY_MAX_FILE_SIZE_MB, settings.TEMPORARY_MAX_FILES_PER_UPLOAD


def _weekly_limit_for_tier(tier: UserTier) -> int:
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_WEEKLY_UPLOADS
    if tier == UserTier.free:
        return settings.FREE_MAX_WEEKLY_UPLOADS
    return settings.TEMPORARY_MAX_WEEKLY_UPLOADS


def _weekly_size_limit_for_tier(tier: UserTier) -> int:
    """Return weekly upload size limit in bytes (0 = unlimited)."""
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_WEEKLY_UPLOAD_SIZE_MB * 1024 * 1024
    if tier == UserTier.free:
        return settings.FREE_MAX_WEEKLY_UPLOAD_SIZE_MB * 1024 * 1024
    return settings.TEMPORARY_MAX_WEEKLY_UPLOAD_SIZE_MB * 1024 * 1024


async def _count_weekly_uploads(
    session: AsyncSession, user_id: int, one_week_ago: datetime
) -> int:
    result = await session.exec(
        select(func.count(func.distinct(col(FileUpload.upload_group)))).where(
            FileUpload.user_id == user_id,
            FileUpload.created_at >= one_week_ago,
        )
    )
    return result.one()


async def _check_weekly_quota(
    user: User,
    session: AsyncSession,
    *,
    incoming_uploads: int = 0,
    incoming_bytes: int = 0,
) -> None:
    """Raise HTTP 429 if the user has exceeded their weekly upload quota."""
    weekly_limit = _weekly_limit_for_tier(user.tier)
    user_id = require_id(user.id, "User")
    one_week_ago = utcnow() - timedelta(days=7)

    if weekly_limit > 0:
        weekly_used = await _count_weekly_uploads(session, user_id, one_week_ago)
        if weekly_used + incoming_uploads > weekly_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Weekly upload limit reached. You have used "
                    f"{weekly_used}/{weekly_limit} uploads this week."
                ),
            )

    size_limit = _weekly_size_limit_for_tier(user.tier)
    if size_limit > 0:
        result = await session.exec(
            select(func.coalesce(func.sum(col(FileUpload.file_size_bytes)), 0)).where(
                FileUpload.user_id == user_id,
                FileUpload.created_at >= one_week_ago,
            )
        )
        size_used = result.one()
        if size_used + incoming_bytes > size_limit:
            used_gb = size_used / (1024 * 1024 * 1024)
            limit_gb = size_limit / (1024 * 1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Weekly upload size limit reached. You have used "
                    f"{used_gb:.1f} GB / {limit_gb:.0f} GB this week."
                ),
            )


def _resolve_expiry(expiry_hours: int | None, tier: UserTier) -> timedelta:
    """Resolve the expiry duration, clamping to tier limits."""
    if expiry_hours is None:
        return timedelta(days=settings.FILE_EXPIRY_DAYS)
    if tier == UserTier.premium:
        clamped = max(
            settings.PREMIUM_MIN_EXPIRY_HOURS,
            min(expiry_hours, settings.PREMIUM_MAX_EXPIRY_HOURS),
        )
    elif tier == UserTier.free:
        clamped = max(
            settings.FREE_MIN_EXPIRY_HOURS,
            min(expiry_hours, settings.FREE_MAX_EXPIRY_HOURS),
        )
    else:
        # Temporary tier: pick closest allowed option
        allowed = settings.TEMPORARY_EXPIRY_OPTIONS_HOURS
        clamped = min(allowed, key=lambda h: abs(h - expiry_hours)) if allowed else 72
    return timedelta(hours=clamped)


def _resolve_max_downloads(max_downloads: int | None, tier: UserTier) -> int | None:
    """Resolve max_downloads, applying tier limits. 0 or None means unlimited."""
    if max_downloads is None:
        return None
    if max_downloads < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_downloads cannot be negative",
        )
    if max_downloads == 0:
        return None
    if tier == UserTier.premium:
        limit = settings.PREMIUM_MAX_DOWNLOADS_LIMIT
    elif tier == UserTier.free:
        limit = settings.FREE_MAX_DOWNLOADS_LIMIT
    else:
        allowed = settings.TEMPORARY_MAX_DOWNLOADS_OPTIONS
        # Clamp to closest allowed option (never grant unlimited)
        return (
            min(allowed, key=lambda h: abs(h - max_downloads))
            if allowed
            else max_downloads
        )
    return min(max_downloads, limit) if limit > 0 else max_downloads


def _build_download_url(download_token: str) -> str:
    return f"/api/files/{download_token}"


def _resolve_access_credential(
    password: str | None, access_token: str | None
) -> str | None:
    return access_token or password


def _build_invite_download_url(upload_group: str, raw_token: str) -> str:
    return f"/download/group/{upload_group}#password={raw_token}"


def _download_limit_message(access_type: str, separate_download_counts: bool) -> str:
    if separate_download_counts:
        if access_type == "public":
            return "Public download limit reached"
        if access_type in ("password", "email"):
            return "Restricted download limit reached"
    return "Download limit reached"


async def _consume_download_slot(
    session: AsyncSession,
    file_upload: FileUpload,
    access_type: str,
    separate_download_counts: bool,
) -> None:
    values: dict[str, object] = {"download_count": FileUpload.download_count + 1}
    file_upload_id = require_id(file_upload.id, "FileUpload")
    stmt = update(FileUpload).where(col(FileUpload.id) == file_upload_id)

    if access_type == "public":
        values["public_download_count"] = FileUpload.public_download_count + 1
    elif access_type in ("password", "email"):
        values["restricted_download_count"] = FileUpload.restricted_download_count + 1

    if file_upload.max_downloads and access_type != "owner":
        if separate_download_counts:
            if access_type == "public":
                stmt = stmt.where(
                    col(FileUpload.public_download_count) < file_upload.max_downloads
                )
            elif access_type in ("password", "email"):
                stmt = stmt.where(
                    col(FileUpload.restricted_download_count)
                    < file_upload.max_downloads
                )
        else:
            stmt = stmt.where(
                col(FileUpload.download_count) < file_upload.max_downloads
            )

    result = await session.exec(
        stmt.values(**values).execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=_download_limit_message(access_type, separate_download_counts),
        )

    file_upload.download_count += 1
    if access_type == "public":
        file_upload.public_download_count += 1
    elif access_type in ("password", "email"):
        file_upload.restricted_download_count += 1


def to_file_response(
    f: FileUpload,
    group_settings: UploadGroupSettings | None = None,
    password_count: int = 0,
    email_count: int = 0,
    viewer_is_owner: bool = False,
    group_download_only: bool = False,
) -> FileUploadResponse:
    return FileUploadResponse(
        id=require_id(f.id, "FileUpload"),
        original_filename=f.original_filename,
        file_size_bytes=f.file_size_bytes,
        download_url=_build_download_url(f.download_token),
        expires_at=f.expires_at,
        download_count=f.download_count,
        public_download_count=f.public_download_count,
        restricted_download_count=f.restricted_download_count,
        max_downloads=f.max_downloads,
        separate_download_counts=group_settings.separate_download_counts
        if group_settings
        else False,
        is_active=f.is_active,
        upload_group=f.upload_group,
        is_public=group_settings.is_public if group_settings else True,
        has_passwords=password_count > 0,
        has_email_recipients=email_count > 0,
        viewer_is_owner=viewer_is_owner,
        group_download_only=group_download_only,
    )


def _requires_group_archive_download(files: list[FileUpload]) -> bool:
    return _group_downloads_as_archive(files)


async def _is_single_file_download_restricted(
    session: AsyncSession,
    file_upload: FileUpload,
) -> bool:
    """Return whether a file can only be downloaded via the group ZIP flow."""
    result = await session.exec(
        select(FileUpload).where(
            FileUpload.upload_group == file_upload.upload_group,
            col(FileUpload.is_active).is_(True),
        )
    )
    return _requires_group_archive_download(list(result.all()))


async def _store_upload_content(
    session: AsyncSession, content: bytes
) -> tuple[str, str]:
    """Scan an upload and reuse an existing stored file when the checksum matches."""
    await run_in_threadpool(scan_upload_content, content)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    content_hash = sha256(content).hexdigest()
    result = await session.exec(
        select(FileUpload.stored_filename)
        .where(FileUpload.content_hash == content_hash)
        .order_by(col(FileUpload.created_at).desc())
    )

    for stored_filename in result.all():
        if stored_filename and (upload_dir / stored_filename).exists():
            return stored_filename, content_hash

    stored_filename = str(uuid.uuid4())
    async with aiofiles.open(upload_dir / stored_filename, "wb") as output_file:
        await output_file.write(content)

    return stored_filename, content_hash


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


def _normalize_password_entry(
    label_value: object, password_value: object
) -> tuple[str, str] | None:
    label = str(label_value or "").strip()
    password = str(password_value or "").strip()
    if label and not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password label requires a password.",
        )
    if not password:
        return None
    return label[:100] or "Password", password


def _parse_password_entries(passwords_json: str) -> list[tuple[str, str]]:
    try:
        payload = json.loads(passwords_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid passwords payload.",
        ) from None

    if not isinstance(payload, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid passwords payload.",
        )

    password_entries: list[tuple[str, str]] = []
    for entry in cast("list[object]", payload):
        if not isinstance(entry, Mapping):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid passwords payload.",
            )
        password_entry = cast("Mapping[str, object]", entry)
        normalized = _normalize_password_entry(
            password_entry.get("label", ""), password_entry.get("password", "")
        )
        if normalized:
            password_entries.append(normalized)
    return password_entries


async def load_group_access(
    session: AsyncSession,
    upload_group: str,
) -> tuple[
    UploadGroupSettings | None, list[UploadPassword], list[UploadEmailRecipient]
]:
    """Load group settings, passwords, and email recipients."""
    gs_result = await session.exec(
        select(UploadGroupSettings).where(
            UploadGroupSettings.upload_group == upload_group
        )
    )
    group_settings = gs_result.first()

    pw_result = await session.exec(
        select(UploadPassword).where(UploadPassword.upload_group == upload_group)
    )
    passwords = list(pw_result.all())

    er_result = await session.exec(
        select(UploadEmailRecipient).where(
            UploadEmailRecipient.upload_group == upload_group
        )
    )
    email_recipients = list(er_result.all())

    return group_settings, passwords, email_recipients


async def _load_group_access_summaries(
    session: AsyncSession,
    upload_groups: set[str],
) -> dict[str, tuple[UploadGroupSettings | None, int, int]]:
    if not upload_groups:
        return {}

    settings_result = await session.exec(
        select(UploadGroupSettings).where(
            col(UploadGroupSettings.upload_group).in_(upload_groups)
        )
    )
    summaries: dict[str, tuple[UploadGroupSettings | None, int, int]] = dict.fromkeys(
        upload_groups, (None, 0, 0)
    )
    for group_settings in settings_result.all():
        summaries[group_settings.upload_group] = (group_settings, 0, 0)

    password_result = await session.exec(
        select(col(UploadPassword.upload_group), func.count(col(UploadPassword.id)))
        .where(col(UploadPassword.upload_group).in_(upload_groups))
        .group_by(col(UploadPassword.upload_group))
    )
    for upload_group, password_count in password_result.all():
        group_settings, _, email_count = summaries[upload_group]
        summaries[upload_group] = (group_settings, int(password_count), email_count)

    email_result = await session.exec(
        select(
            col(UploadEmailRecipient.upload_group),
            func.count(col(UploadEmailRecipient.id)),
        )
        .where(col(UploadEmailRecipient.upload_group).in_(upload_groups))
        .group_by(col(UploadEmailRecipient.upload_group))
    )
    for upload_group, email_count in email_result.all():
        group_settings, password_count, _ = summaries[upload_group]
        summaries[upload_group] = (group_settings, password_count, int(email_count))

    return summaries


def _has_valid_credential(
    password: str | None,
    passwords: list[UploadPassword],
    email_recipients: list[UploadEmailRecipient],
) -> bool:
    """Check whether the provided password matches a password or email token."""
    if not password:
        return False
    for pw in passwords:
        if verify_secret(password, pw.password_hash):
            return True
    pw_hash = sha256(password.encode()).hexdigest()
    return any(compare_digest(pw_hash, er.token_hash) for er in email_recipients)


async def _verify_access(
    session: AsyncSession,
    upload_group: str,
    password: str | None,
    owner_user_id: int | None,
    current_user: User | None,
) -> tuple[str, int | None, int | None]:
    """Verify download access and return access metadata."""
    # Owner always has access
    if current_user and owner_user_id and current_user.id == owner_user_id:
        return "owner", None, None

    _, passwords, email_recipients = await load_group_access(session, upload_group)

    # If password provided, check against passwords and email tokens
    if password:
        for pw in passwords:
            if verify_secret(password, pw.password_hash):
                return "password", pw.id, None

        # Check email recipient tokens (SHA256-based, constant-time)
        pw_hash = sha256(password.encode()).hexdigest()
        for er in email_recipients:
            if compare_digest(pw_hash, er.token_hash):
                return "email", None, er.id

    # If passwords or email recipients exist, a valid credential is required
    if passwords or email_recipients:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password"
        )

    # No access control configured — allow public access
    return "public", None, None


async def _create_group_access(
    session: AsyncSession,
    upload_group: str,
    is_public: bool,
    passwords_json: str | None,
    emails_json: str | None,
    show_email_stats: bool,
    user: User,
    title: str | None = None,
    description: str | None = None,
    separate_download_counts: bool = False,
) -> tuple[UploadGroupSettings, int, int, list[tuple[str, str]]]:
    """Create group settings, passwords, and email recipients.

    Returns (settings, pw_count, email_count, email_tokens).
    """
    # Temporary users cannot use these features
    if user.tier == UserTier.temporary:
        separate_download_counts = False
        show_email_stats = False

    # Create group settings
    group_settings = UploadGroupSettings(
        upload_group=upload_group,
        is_public=is_public,
        show_email_stats=show_email_stats,
        separate_download_counts=separate_download_counts,
        title=title[:200] if title else None,
        description=description[:2000] if description else None,
    )
    session.add(group_settings)

    # Process passwords
    pw_count = 0
    if passwords_json:
        password_entries = _parse_password_entries(passwords_json)
        pw_limit = _get_password_limit(user.tier)
        if pw_limit > 0 and len(password_entries) > pw_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Too many passwords. Max {pw_limit} for {user.tier.value} tier."
                ),
            )
        for label, password in password_entries:
            session.add(
                UploadPassword(
                    upload_group=upload_group,
                    label=label,
                    password_hash=hash_secret(password),
                )
            )
            pw_count += 1

    # Process email invites
    email_count = 0
    email_tokens: list[tuple[str, str]] = []  # (email, raw_token)
    if emails_json:
        try:
            email_list = json.loads(emails_json)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid emails payload.",
            ) from None
        if not isinstance(email_list, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid emails payload.",
            )
        email_list = cast("list[object]", email_list)
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
                detail=(
                    f"Too many email invites. Max {email_limit} "
                    f"for {user.tier.value} tier."
                ),
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
    separate_download_counts: bool = Form(False),
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

    await _check_weekly_quota(
        user,
        session,
        incoming_uploads=1,
        incoming_bytes=file_size,
    )

    stored_filename, content_hash = await _store_upload_content(session, content)

    # Create DB record
    download_token = secrets.token_urlsafe(32)
    upload_group = secrets.token_urlsafe(32)
    expires_at = utcnow() + _resolve_expiry(expiry_hours, user.tier)
    resolved_max_downloads = _resolve_max_downloads(max_downloads, user.tier)

    file_upload = FileUpload(
        user_id=user.id,
        original_filename=_sanitize_filename(file.filename or "unnamed"),
        stored_filename=stored_filename,
        content_hash=content_hash,
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
        separate_download_counts=separate_download_counts,
    )

    await session.commit()
    await session.refresh(file_upload)

    # Send invite emails in background
    if email_tokens:
        file_names = [file_upload.original_filename]
        for email_addr, raw_token in email_tokens:
            try:
                await send_file_invite_email(
                    recipient_email=email_addr,
                    sender_email=user.email,
                    download_url=_build_invite_download_url(upload_group, raw_token),
                    file_names=file_names,
                )
                # Mark as notified
                stmt = select(UploadEmailRecipient).where(
                    UploadEmailRecipient.upload_group == upload_group,
                    UploadEmailRecipient.email == email_addr,
                )
                er_result = await session.exec(stmt)
                er = er_result.first()
                if er:
                    er.notified = True
                    session.add(er)
            except Exception:
                logger.warning("Failed to send invite email", exc_info=True)
        await session.commit()

    return to_file_response(file_upload, group_settings, pw_count, email_count)


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
    separate_download_counts: bool = Form(False),
    title: str | None = Form(None),
    description: str | None = Form(None),
) -> MultiFileUploadResponse:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided"
        )

    # Get tier limits
    max_size_mb, max_per_upload = _get_limits(user.tier)

    # Validate number of files against per-upload limit
    if max_per_upload > 0 and len(files) > max_per_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Too many files. Max {max_per_upload} files per upload "
                f"for {user.tier.value} tier."
            ),
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
                detail=(
                    f"File '{f.filename}' too large. Max {max_size_mb}MB "
                    f"for {user.tier.value} tier."
                ),
            )
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Total file size exceeds limit. Max "
                    f"{max_size_mb}MB cumulative for {user.tier.value} tier."
                ),
            )
        file_contents.append((_sanitize_archive_path(f.filename or "unnamed"), content))

    await _check_weekly_quota(
        user,
        session,
        incoming_uploads=1,
        incoming_bytes=total_size,
    )

    upload_group = secrets.token_urlsafe(32)
    expires_at = utcnow() + _resolve_expiry(expiry_hours, user.tier)
    resolved_max_downloads = _resolve_max_downloads(max_downloads, user.tier)
    saved_uploads: list[FileUpload] = []

    for original_name, content in file_contents:
        stored_filename, content_hash = await _store_upload_content(session, content)

        file_upload = FileUpload(
            user_id=user.id,
            original_filename=original_name,
            stored_filename=stored_filename,
            content_hash=content_hash,
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
        separate_download_counts=separate_download_counts,
    )

    await session.commit()
    for fu in saved_uploads:
        await session.refresh(fu)

    # Send invite emails in background
    if email_tokens:
        file_names = [fu.original_filename for fu in saved_uploads]
        for email_addr, raw_token in email_tokens:
            try:
                await send_file_invite_email(
                    recipient_email=email_addr,
                    sender_email=user.email,
                    download_url=_build_invite_download_url(upload_group, raw_token),
                    file_names=file_names,
                )
                stmt = select(UploadEmailRecipient).where(
                    UploadEmailRecipient.upload_group == upload_group,
                    UploadEmailRecipient.email == email_addr,
                )
                er_result = await session.exec(stmt)
                er = er_result.first()
                if er:
                    er.notified = True
                    session.add(er)
            except Exception:
                logger.warning("Failed to send invite email", exc_info=True)
        await session.commit()

    return MultiFileUploadResponse(
        files=[
            to_file_response(
                fu,
                group_settings,
                pw_count,
                email_count,
                group_download_only=_requires_group_archive_download(saved_uploads),
            )
            for fu in saved_uploads
        ],
        upload_group=upload_group,
        total_size_bytes=total_size,
        title=group_settings.title,
        description=group_settings.description,
    )


@router.get("/group/{upload_group}")
async def get_group_info(
    upload_group: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
    access_token: Annotated[str | None, Header(alias="X-Access-Token")] = None,
    current_user: User | None = Depends(get_optional_user),
) -> UploadGroupInfoResponse:
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        col(FileUpload.is_active).is_(True),
    )
    result = await session.exec(stmt)
    files = list(result.all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    group_settings, passwords, email_recipients = await load_group_access(
        session, upload_group
    )
    pw_count = len(passwords)
    email_count = len(email_recipients)
    is_public = group_settings.is_public if group_settings else True
    viewer_is_owner = current_user is not None and files[0].user_id == current_user.id

    # Hide details for non-public groups until the viewer proves access.
    hide_details = (
        not viewer_is_owner
        and not is_public
        and (pw_count > 0 or email_count > 0)
        and not _has_valid_credential(
            _resolve_access_credential(password, access_token),
            passwords,
            email_recipients,
        )
    )

    total_size = sum(f.file_size_bytes for f in files)
    requires_archive_download = _requires_group_archive_download(files)
    return UploadGroupInfoResponse(
        files=(
            []
            if hide_details
            else [
                to_file_response(
                    f,
                    group_settings,
                    pw_count,
                    email_count,
                    viewer_is_owner=viewer_is_owner,
                    group_download_only=requires_archive_download,
                )
                for f in files
            ]
        ),
        upload_group=upload_group,
        total_size_bytes=0 if hide_details else total_size,
        file_count=0 if hide_details else len(files),
        will_zip=False if hide_details else _group_downloads_as_archive(files),
        is_public=is_public,
        has_passwords=pw_count > 0,
        has_email_recipients=email_count > 0,
        separate_download_counts=group_settings.separate_download_counts
        if group_settings
        else False,
        title=None
        if hide_details
        else (group_settings.title if group_settings else None),
        description=None
        if hide_details
        else (group_settings.description if group_settings else None),
        viewer_is_owner=viewer_is_owner,
    )


@router.get("/group/{upload_group}/download")
async def download_group(
    upload_group: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
    access_token: Annotated[str | None, Header(alias="X-Access-Token")] = None,
    current_user: User | None = Depends(get_optional_user),
):
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        col(FileUpload.is_active).is_(True),
    )
    result = await session.exec(stmt)
    files = list(result.all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    # Access verification
    owner_user_id = files[0].user_id
    access_type, pw_id, er_id = await _verify_access(
        session,
        upload_group,
        _resolve_access_credential(password, access_token),
        owner_user_id,
        current_user,
    )

    # Check expiration and download limits for all files
    now = utcnow()
    gs_result = await session.exec(
        select(UploadGroupSettings).where(
            UploadGroupSettings.upload_group == upload_group
        )
    )
    group_settings = gs_result.first()

    for f in files:
        if now > f.expires_at:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Files have expired"
            )
        if f.max_downloads and access_type != "owner":
            if group_settings and group_settings.separate_download_counts:
                if access_type == "public":
                    if f.public_download_count >= f.max_downloads:
                        raise HTTPException(
                            status_code=status.HTTP_410_GONE,
                            detail="Public download limit reached",
                        )
                else:
                    if f.restricted_download_count >= f.max_downloads:
                        raise HTTPException(
                            status_code=status.HTTP_410_GONE,
                            detail="Restricted download limit reached",
                        )
            elif f.download_count >= f.max_downloads:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE, detail="Download limit reached"
                )

    if not _group_downloads_as_archive(files):
        # Single file - serve directly
        file_path = Path(settings.UPLOAD_DIR) / files[0].stored_filename
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
            )
        await _consume_download_slot(
            session,
            files[0],
            access_type,
            bool(group_settings and group_settings.separate_download_counts),
        )
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
            path=str(file_path),
            filename=files[0].original_filename,
            media_type="application/octet-stream",
        )

    archive_files: list[tuple[Path, str]] = []
    for f in files:
        file_path = Path(settings.UPLOAD_DIR) / f.stored_filename
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{f.original_filename}' not found on disk",
            )
        archive_files.append((file_path, f.original_filename))
        await _consume_download_slot(
            session,
            f,
            access_type,
            bool(group_settings and group_settings.separate_download_counts),
        )

    # Archive downloads are one transfer event even though each file consumes its
    # own download slot for per-file limit enforcement.
    session.add(
        DownloadLog(
            upload_group=upload_group,
            access_type=access_type,
            upload_password_id=pw_id,
            email_recipient_id=er_id,
        )
    )

    await session.commit()

    zip_name = _build_group_archive_name(
        upload_group, group_settings.title if group_settings else None
    )
    return StreamingResponse(
        _stream_group_archive(archive_files),
        media_type="application/zip",
        headers={"Content-Disposition": _build_attachment_header(zip_name)},
    )


@router.get("/", response_model=FileListResponse)
async def list_files(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileListResponse:
    now = utcnow()
    grace_days = settings.FILE_GRACE_PERIOD_DAYS
    if user.tier == UserTier.premium:
        grace_days = max(grace_days, settings.PREMIUM_REFRESH_GRACE_DAYS)
    grace_cutoff = now - timedelta(days=grace_days)
    stmt = (
        select(FileUpload)
        .where(
            FileUpload.user_id == user.id,
            col(FileUpload.is_active).is_(True),
            # Include active files and expired files within grace period
            or_(
                FileUpload.expires_at > now,
                FileUpload.expires_at > grace_cutoff,
            ),
        )
        .order_by(col(FileUpload.created_at).desc())
    )
    result = await session.exec(stmt)
    files = list(result.all())

    group_access_cache = await _load_group_access_summaries(
        session, {f.upload_group for f in files}
    )

    return FileListResponse(
        files=[
            to_file_response(f, *group_access_cache.get(f.upload_group, (None, 0, 0)))
            for f in files
        ],
    )


@router.get("/{download_token}")
async def download_file(
    download_token: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
    access_token: Annotated[str | None, Header(alias="X-Access-Token")] = None,
    current_user: User | None = Depends(get_optional_user),
):
    stmt = select(FileUpload).where(
        FileUpload.download_token == download_token,
    )
    result = await session.exec(stmt)
    file_upload = result.first()

    if not file_upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    # Access verification
    access_type, pw_id, er_id = await _verify_access(
        session,
        file_upload.upload_group,
        _resolve_access_credential(password, access_token),
        file_upload.user_id,
        current_user,
    )

    if await _is_single_file_download_restricted(session, file_upload):
        detail = (
            "Single-file downloads are disabled for grouped transfers. "
            "Download the full transfer instead."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    now = utcnow()
    grace_end = file_upload.expires_at + timedelta(days=settings.FILE_GRACE_PERIOD_DAYS)

    if not file_upload.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="File has been deactivated"
        )

    if now > file_upload.expires_at:
        if now > grace_end:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="File has expired and been removed",
            )
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="File has expired")

    if file_upload.max_downloads and access_type != "owner":
        # Load group settings for separate counting check
        gs_result = await session.exec(
            select(UploadGroupSettings).where(
                UploadGroupSettings.upload_group == file_upload.upload_group
            )
        )
        gs = gs_result.first()
        if gs and gs.separate_download_counts:
            if access_type == "public":
                if file_upload.public_download_count >= file_upload.max_downloads:
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Public download limit reached",
                    )
            else:
                if file_upload.restricted_download_count >= file_upload.max_downloads:
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Restricted download limit reached",
                    )
        elif file_upload.download_count >= file_upload.max_downloads:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Download limit reached"
            )

    file_path = Path(settings.UPLOAD_DIR) / file_upload.stored_filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
        )

    gs_result = await session.exec(
        select(UploadGroupSettings).where(
            UploadGroupSettings.upload_group == file_upload.upload_group
        )
    )
    group_settings = gs_result.first()
    await _consume_download_slot(
        session,
        file_upload,
        access_type,
        bool(group_settings and group_settings.separate_download_counts),
    )

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

    return FileResponse(
        path=str(file_path),
        filename=file_upload.original_filename,
        media_type="application/octet-stream",
    )


@router.get("/{download_token}/info")
async def get_file_info(
    download_token: str,
    session: AsyncSession = Depends(get_session),
    password: str | None = Query(None),
    access_token: Annotated[str | None, Header(alias="X-Access-Token")] = None,
    current_user: User | None = Depends(get_optional_user),
) -> FileUploadResponse:
    stmt = select(FileUpload).where(FileUpload.download_token == download_token)
    result = await session.exec(stmt)
    file_upload = result.first()

    if not file_upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    gs, pws, ers = await load_group_access(session, file_upload.upload_group)
    is_public = gs.is_public if gs else True
    pw_count = len(pws)
    viewer_is_owner = (
        current_user is not None and file_upload.user_id == current_user.id
    )
    group_download_only = await _is_single_file_download_restricted(
        session, file_upload
    )

    # Hide details when is_public=false and no valid credential provided
    hide_details = (
        not viewer_is_owner
        and not is_public
        and (pw_count > 0 or len(ers) > 0)
        and not _has_valid_credential(
            _resolve_access_credential(password, access_token), pws, ers
        )
    )

    if hide_details:
        return FileUploadResponse(
            id=require_id(file_upload.id, "FileUpload"),
            original_filename="Protected file",
            file_size_bytes=0,
            download_url=_build_download_url(file_upload.download_token),
            expires_at=file_upload.expires_at,
            download_count=0,
            is_active=file_upload.is_active,
            upload_group=file_upload.upload_group,
            is_public=False,
            has_passwords=True,
            has_email_recipients=len(ers) > 0,
            viewer_is_owner=False,
            group_download_only=group_download_only,
        )

    return to_file_response(
        file_upload,
        gs,
        pw_count,
        len(ers),
        viewer_is_owner=viewer_is_owner,
        group_download_only=group_download_only,
    )


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
    result = await session.exec(stmt)
    file_upload = result.first()

    if not file_upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    now = utcnow()

    # Free users can only refresh before expiry
    if user.tier == UserTier.free and now > file_upload.expires_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free users can only refresh uploads before they expire.",
        )

    # Premium users can refresh within the premium grace window after expiry.
    if user.tier == UserTier.premium and now > file_upload.expires_at + timedelta(
        days=settings.PREMIUM_REFRESH_GRACE_DAYS
    ):
        grace_message = (
            "Upload expired more than "
            f"{settings.PREMIUM_REFRESH_GRACE_DAYS} days ago and can no longer "
            "be refreshed."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=grace_message,
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

    gs, pws, ers = await load_group_access(session, file_upload.upload_group)
    return to_file_response(
        file_upload,
        gs,
        len(pws),
        len(ers),
        group_download_only=await _is_single_file_download_restricted(
            session, file_upload
        ),
    )


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
    result = await session.exec(stmt)
    file_upload = result.first()

    if not file_upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    if body.original_filename is not None:
        file_upload.original_filename = _sanitize_filename(body.original_filename)
    if body.expires_in_hours is not None:
        file_upload.expires_at = utcnow() + _resolve_expiry(
            body.expires_in_hours, user.tier
        )
    if body.max_downloads is not None:
        file_upload.max_downloads = _resolve_max_downloads(
            body.max_downloads, user.tier
        )

    session.add(file_upload)
    await session.commit()
    await session.refresh(file_upload)

    gs, pws, ers = await load_group_access(session, file_upload.upload_group)
    return to_file_response(
        file_upload,
        gs,
        len(pws),
        len(ers),
        group_download_only=await _is_single_file_download_restricted(
            session, file_upload
        ),
    )


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
    result = await session.exec(stmt)
    file_upload = result.first()

    if not file_upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

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
    """Add new files to an existing upload group. Premium only."""
    if user.tier != UserTier.premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only premium users can edit uploads.",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided"
        )

    # Verify the group exists and belongs to this user
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.exec(stmt)
    existing_files = list(result.all())

    if not existing_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    # Get tier limits
    max_size_mb, max_per_upload = _get_limits(user.tier)
    max_bytes = max_size_mb * 1024 * 1024

    # Count active files in the group
    active_count = sum(1 for f in existing_files if f.is_active)
    if max_per_upload > 0 and active_count + len(files) > max_per_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Too many files. Max {max_per_upload} files per upload "
                f"for {user.tier.value} tier."
            ),
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
                detail=(
                    "Total file size exceeds limit. Max "
                    f"{max_size_mb}MB for {user.tier.value} tier."
                ),
            )
        file_contents.append((_sanitize_archive_path(f.filename or "unnamed"), content))

    await _check_weekly_quota(
        user,
        session,
        incoming_uploads=0,
        incoming_bytes=sum(len(content) for _, content in file_contents),
    )

    saved_uploads: list[FileUpload] = []

    for original_name, content in file_contents:
        stored_filename, content_hash = await _store_upload_content(session, content)

        file_upload = FileUpload(
            user_id=user.id,
            original_filename=original_name,
            stored_filename=stored_filename,
            content_hash=content_hash,
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

    gs, pws, ers = await load_group_access(session, upload_group)
    new_total = sum(len(c) for _, c in file_contents)
    requires_archive_download = _requires_group_archive_download(
        [f for f in existing_files if f.is_active] + saved_uploads
    )
    return MultiFileUploadResponse(
        files=[
            to_file_response(
                fu,
                gs,
                len(pws),
                len(ers),
                group_download_only=requires_archive_download,
            )
            for fu in saved_uploads
        ],
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
    """Refresh all active files in a group."""
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.exec(stmt)
    files = list(result.all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    now = utcnow()
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

    # Premium users can refresh within the premium grace window after expiry.
    if user.tier == UserTier.premium and now > reference.expires_at + timedelta(
        days=settings.PREMIUM_REFRESH_GRACE_DAYS
    ):
        grace_message = (
            "Upload expired more than "
            f"{settings.PREMIUM_REFRESH_GRACE_DAYS} days ago and can no longer "
            "be refreshed."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=grace_message,
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
        gs_stmt = select(UploadGroupSettings).where(
            UploadGroupSettings.upload_group == upload_group
        )
        gs_result = await session.exec(gs_stmt)
        gs_obj = gs_result.first()
        if gs_obj:
            if body.title is not None:
                gs_obj.title = body.title[:200] if body.title else None
            if body.description is not None:
                gs_obj.description = (
                    body.description[:2000] if body.description else None
                )
            session.add(gs_obj)

    await session.commit()
    for f in files:
        await session.refresh(f)

    gs, pws, ers = await load_group_access(session, upload_group)
    active_files = [f for f in files if f.is_active]
    requires_archive_download = _requires_group_archive_download(active_files)
    return MultiFileUploadResponse(
        files=[
            to_file_response(
                f,
                gs,
                len(pws),
                len(ers),
                group_download_only=requires_archive_download,
            )
            for f in active_files
        ],
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
        col(FileUpload.is_active).is_(True),
    )
    result = await session.exec(stmt)
    files = list(result.all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    for f in files:
        if body.expiry_hours is not None:
            f.expires_at = utcnow() + _resolve_expiry(body.expiry_hours, user.tier)
        if body.max_downloads is not None:
            f.max_downloads = _resolve_max_downloads(body.max_downloads, user.tier)
        session.add(f)

    # Update group settings (title/description)
    if body.title is not None or body.description is not None:
        gs_stmt = select(UploadGroupSettings).where(
            UploadGroupSettings.upload_group == upload_group
        )
        gs_result = await session.exec(gs_stmt)
        gs = gs_result.first()
        if gs:
            if body.title is not None:
                gs.title = body.title[:200] if body.title else None
            if body.description is not None:
                gs.description = body.description[:2000] if body.description else None
            session.add(gs)

    await session.commit()
    for f in files:
        await session.refresh(f)

    gs, pws, ers = await load_group_access(session, upload_group)
    requires_archive_download = _requires_group_archive_download(files)
    return MultiFileUploadResponse(
        files=[
            to_file_response(
                f,
                gs,
                len(pws),
                len(ers),
                group_download_only=requires_archive_download,
            )
            for f in files
        ],
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
    result = await session.exec(stmt)
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    group_settings, passwords, email_recipients = await load_group_access(
        session, upload_group
    )

    return AccessInfoResponse(
        is_public=group_settings.is_public if group_settings else True,
        passwords=[
            PasswordInfo(id=require_id(pw.id, "UploadPassword"), label=pw.label)
            for pw in passwords
        ],
        emails=[
            EmailRecipientInfo(
                id=require_id(er.id, "UploadEmailRecipient"),
                email=er.email,
                notified=er.notified,
            )
            for er in email_recipients
        ],
        show_email_stats=group_settings.show_email_stats if group_settings else False,
        separate_download_counts=group_settings.separate_download_counts
        if group_settings
        else False,
    )


@router.patch("/group/{upload_group}/access")
async def edit_access(
    upload_group: str,
    body: AccessEditRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessInfoResponse:
    """Edit access control for an upload group. Owner only."""
    # Verify ownership
    stmt = select(FileUpload).where(
        FileUpload.upload_group == upload_group,
        FileUpload.user_id == user.id,
    )
    result = await session.exec(stmt)
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    group_settings, passwords, email_recipients = await load_group_access(
        session, upload_group
    )
    if not group_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group settings not found"
        )

    # Update is_public
    if body.is_public is not None:
        group_settings.is_public = body.is_public

    # Update show_email_stats
    if body.show_email_stats is not None:
        # Temporary users cannot use this feature
        if user.tier == UserTier.temporary:
            group_settings.show_email_stats = False
        else:
            group_settings.show_email_stats = body.show_email_stats

    # Update separate_download_counts
    if body.separate_download_counts is not None:
        # Temporary users cannot use this feature
        if user.tier == UserTier.temporary:
            group_settings.separate_download_counts = False
        else:
            group_settings.separate_download_counts = body.separate_download_counts

    session.add(group_settings)

    # Remove passwords by ID
    if body.password_ids_to_remove:
        existing_ids = {pw.id for pw in passwords}
        for pw_id in body.password_ids_to_remove:
            if pw_id not in existing_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password with id {pw_id} not found in this group",
                )
            pw_stmt = select(UploadPassword).where(UploadPassword.id == pw_id)
            pw_result = await session.exec(pw_stmt)
            pw_obj = pw_result.first()
            if pw_obj:
                await session.delete(pw_obj)

    # Add new passwords
    if body.passwords_to_add:
        password_entries: list[tuple[str, str]] = []
        for pw_entry in body.passwords_to_add:
            normalized = _normalize_password_entry(pw_entry.label, pw_entry.password)
            if normalized:
                password_entries.append(normalized)

        current_count = len(passwords) - len(body.password_ids_to_remove or [])
        pw_limit = _get_password_limit(user.tier)
        new_total = current_count + len(password_entries)
        if pw_limit > 0 and new_total > pw_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Too many passwords. Max {pw_limit} for {user.tier.value} tier."
                ),
            )
        for label, password in password_entries:
            session.add(
                UploadPassword(
                    upload_group=upload_group,
                    label=label,
                    password_hash=hash_secret(password),
                )
            )

    # Remove emails by ID
    if body.email_ids_to_remove:
        existing_ids = {er.id for er in email_recipients}
        for er_id in body.email_ids_to_remove:
            if er_id not in existing_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email recipient with id {er_id} not found in this group",
                )
            er_stmt = select(UploadEmailRecipient).where(
                UploadEmailRecipient.id == er_id
            )
            er_result = await session.exec(er_stmt)
            er_obj = er_result.first()
            if er_obj:
                await session.delete(er_obj)

    # Add new emails
    email_tokens: list[tuple[str, str]] = []
    if body.emails_to_add:
        if user.tier == UserTier.temporary:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Create a free account to use email invites.",
            )
        current_count = len(email_recipients) - len(body.email_ids_to_remove or [])
        email_limit = _get_email_limit(user.tier)
        new_total = current_count + len(body.emails_to_add)
        if email_limit > 0 and new_total > email_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Too many email invites. Max {email_limit} "
                    f"for {user.tier.value} tier."
                ),
            )
        for email_addr in body.emails_to_add:
            email_str = email_addr.strip().lower()
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

    await session.commit()

    # Send email invites for newly added emails
    if email_tokens:
        any_file_stmt = select(FileUpload).where(
            FileUpload.upload_group == upload_group,
            col(FileUpload.is_active).is_(True),
        )
        any_file_result = await session.exec(any_file_stmt)
        active_files = list(any_file_result.all())
        if active_files:
            file_names = [file_upload.original_filename for file_upload in active_files]
            for email_str, raw_token in email_tokens:
                try:
                    await send_file_invite_email(
                        recipient_email=email_str,
                        sender_email=user.email,
                        download_url=_build_invite_download_url(
                            upload_group, raw_token
                        ),
                        file_names=file_names,
                    )
                    er_stmt = select(UploadEmailRecipient).where(
                        UploadEmailRecipient.upload_group == upload_group,
                        UploadEmailRecipient.email == email_str,
                    )
                    er_result = await session.exec(er_stmt)
                    er_obj = er_result.first()
                    if er_obj:
                        er_obj.notified = True
                        session.add(er_obj)
                except Exception:
                    logger.exception("Failed to send invite to %s", email_str)
            await session.commit()

    # Reload for response
    _, updated_passwords, updated_emails = await load_group_access(
        session, upload_group
    )

    return AccessInfoResponse(
        is_public=group_settings.is_public,
        passwords=[
            PasswordInfo(id=require_id(pw.id, "UploadPassword"), label=pw.label)
            for pw in updated_passwords
        ],
        emails=[
            EmailRecipientInfo(
                id=require_id(er.id, "UploadEmailRecipient"),
                email=er.email,
                notified=er.notified,
            )
            for er in updated_emails
        ],
        show_email_stats=group_settings.show_email_stats,
        separate_download_counts=group_settings.separate_download_counts,
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
    result = await session.exec(stmt)
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload group not found"
        )

    # Get all download logs for this group
    log_stmt = select(DownloadLog).where(DownloadLog.upload_group == upload_group)
    log_result = await session.exec(log_stmt)
    logs = list(log_result.all())

    if not logs:
        return DownloadStatsResponse(stats=[], total_downloads=0)

    # Load passwords and email recipients for label/email lookup
    _, passwords, email_recipients = await load_group_access(session, upload_group)
    pw_map = {pw.id: pw.label for pw in passwords}
    er_map = {er.id: er.email for er in email_recipients}

    # Aggregate by (access_type, identifier)
    aggregated: dict[tuple[str, str | None], list[datetime]] = {}
    for log in logs:
        identifier = None
        if log.access_type == "password" and log.upload_password_id:
            identifier = pw_map.get(
                log.upload_password_id, f"Password #{log.upload_password_id}"
            )
        elif log.access_type == "email" and log.email_recipient_id:
            identifier = er_map.get(
                log.email_recipient_id, f"Recipient #{log.email_recipient_id}"
            )

        key = (log.access_type, identifier)
        if key not in aggregated:
            aggregated[key] = []
        aggregated[key].append(log.downloaded_at)

    stats: list[DownloadStatEntry] = []
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
    access_token: Annotated[str | None, Header(alias="X-Access-Token")] = None,
) -> RecipientStatsResponse:
    """Get download stats visible to email recipients. Requires valid email token."""
    credential = _resolve_access_credential(password, access_token)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access token required"
        )

    # Verify the token belongs to an email recipient
    token_hash = sha256(credential.encode()).hexdigest()
    er_stmt = select(UploadEmailRecipient).where(
        UploadEmailRecipient.upload_group == upload_group,
    )
    er_result = await session.exec(er_stmt)
    recipients = list(er_result.all())

    matched_recipient = None
    for er in recipients:
        if compare_digest(token_hash, er.token_hash):
            matched_recipient = er
            break

    if not matched_recipient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid access token"
        )

    # Check if stats are enabled
    gs_stmt = select(UploadGroupSettings).where(
        UploadGroupSettings.upload_group == upload_group
    )
    gs_result = await session.exec(gs_stmt)
    group_settings = gs_result.first()

    if not group_settings or not group_settings.show_email_stats:
        return RecipientStatsResponse(downloads=[], total_downloads=0)

    # Stats enabled: return per-email breakdown (only email downloads)
    log_stmt = select(DownloadLog).where(
        DownloadLog.upload_group == upload_group,
        DownloadLog.access_type == "email",
    )
    log_result = await session.exec(log_stmt)
    email_logs = list(log_result.all())

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
        RecipientDownloadEntry(email=email, download_count=count)
        for email, count in sorted(email_counts.items())
    ]

    # Total across all access types
    total_stmt = select(func.count(col(DownloadLog.id))).where(
        DownloadLog.upload_group == upload_group,
    )
    total_result = await session.exec(total_stmt)
    total = total_result.first() or 0

    return RecipientStatsResponse(downloads=downloads, total_downloads=total)
