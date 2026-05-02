from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import func, select

from config import settings
from database import get_session
from email_utils import send_verification_email
from models import AuthToken, FileUpload, User, UserLogin, UserTier, VerificationCode, _utcnow
from rate_limit import auth_rate_limiter, get_client_ip
from schemas import (
    CodeVerificationRequest,
    EmailVerificationRequest,
    LimitsResponse,
    QuotaResponse,
    TokenResponse,
    UserResponse,
)
from security import (
    create_access_token,
    generate_verification_code,
    get_current_user,
    hash_token,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await session.exec(stmt)
    return result.first()


def _get_max_file_size_for_tier(tier: UserTier) -> tuple[int, int]:
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_FILE_SIZE_MB, settings.PREMIUM_MAX_FILES_PER_UPLOAD
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


@router.post("/request-code", status_code=status.HTTP_200_OK)
async def request_code(
    body: EmailVerificationRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    auth_rate_limiter.check(get_client_ip(request))

    user = await _get_user_by_email(session, body.email)
    if user and user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")

    code = generate_verification_code()
    expires_at = _utcnow() + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES)

    verification = VerificationCode(
        email=body.email,
        code=code,
        expires_at=expires_at,
    )
    session.add(verification)
    await session.commit()

    await send_verification_email(body.email, code)

    return {"message": "Verification code sent"}


@router.post("/verify-code")
async def verify_code(
    body: CodeVerificationRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    auth_rate_limiter.check(get_client_ip(request))

    stmt = select(VerificationCode).where(
        VerificationCode.email == body.email,
        VerificationCode.code == body.code,
        VerificationCode.used == False,  # noqa: E712
        VerificationCode.expires_at > _utcnow(),
    )
    result = await session.exec(stmt)
    vc = result.first()
    if not vc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    vc.used = True
    session.add(vc)

    # Find or create user
    user = await _get_user_by_email(session, body.email)
    if not user:
        tier = UserTier.free if body.create_account else UserTier.temporary
        user = User(email=body.email, tier=tier)
        session.add(user)
        await session.flush()
    elif user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")
    elif body.create_account and user.tier == UserTier.temporary:
        # Upgrade temporary user to free on registration
        user.tier = UserTier.free
        session.add(user)

    # Create access token
    raw_token, expires_at = create_access_token(user.id)
    auth_token = AuthToken(
        user_id=user.id,
        token=hash_token(raw_token),
        expires_at=expires_at,
    )
    session.add(auth_token)
    session.add(
        UserLogin(
            user_id=user.id,
            auth_method="verification_code",
            ip_address=get_client_ip(request),
        )
    )
    await session.commit()

    return TokenResponse(token=raw_token, expires_at=expires_at)


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        tier=user.tier.value,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
    )


@router.get("/limits")
async def get_limits() -> LimitsResponse:
    """Return upload limits for temporary tier (public, no auth required)."""
    return LimitsResponse(
        max_file_size_mb=settings.TEMPORARY_MAX_FILE_SIZE_MB,
        max_files_per_upload=settings.TEMPORARY_MAX_FILES_PER_UPLOAD,
        weekly_uploads_limit=settings.TEMPORARY_MAX_WEEKLY_UPLOADS,
        expiry_options_hours=settings.TEMPORARY_EXPIRY_OPTIONS_HOURS,
        max_downloads_options=settings.TEMPORARY_MAX_DOWNLOADS_OPTIONS,
    )


@router.get("/quota")
async def get_quota(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuotaResponse:
    max_file_size_mb, max_files_per_upload = _get_max_file_size_for_tier(user.tier)

    # Count uploads in the last 7 days
    one_week_ago = _utcnow() - timedelta(days=7)
    result = await session.exec(
        select(func.count(FileUpload.id)).where(
            FileUpload.user_id == user.id,
            FileUpload.created_at >= one_week_ago,
        )
    )
    weekly_used = result.one()

    weekly_limit = _weekly_limit_for_tier(user.tier)
    weekly_remaining = max(0, weekly_limit - weekly_used) if weekly_limit > 0 else weekly_limit

    # Compute weekly size usage
    size_limit = _weekly_size_limit_for_tier(user.tier)
    size_used = 0
    if size_limit > 0:
        result = await session.exec(
            select(func.coalesce(func.sum(FileUpload.file_size_bytes), 0)).where(
                FileUpload.user_id == user.id,
                FileUpload.created_at >= one_week_ago,
            )
        )
        size_used = result.one()

    size_remaining = max(0, size_limit - size_used) if size_limit > 0 else 0

    quota = QuotaResponse(
        max_file_size_mb=max_file_size_mb,
        max_files_per_upload=max_files_per_upload,
        weekly_uploads_limit=weekly_limit,
        weekly_uploads_used=weekly_used,
        weekly_uploads_remaining=weekly_remaining,
        weekly_upload_size_limit_bytes=size_limit,
        weekly_upload_size_used_bytes=size_used,
        weekly_upload_size_remaining_bytes=size_remaining,
    )

    # Populate tier-specific expiry/download options
    if user.tier == UserTier.temporary:
        quota.expiry_options_hours = settings.TEMPORARY_EXPIRY_OPTIONS_HOURS
        quota.max_downloads_options = settings.TEMPORARY_MAX_DOWNLOADS_OPTIONS
        quota.max_passwords_per_upload = settings.TEMPORARY_MAX_PASSWORDS_PER_UPLOAD
        quota.max_emails_per_upload = settings.TEMPORARY_MAX_EMAILS_PER_UPLOAD
    elif user.tier == UserTier.free:
        quota.min_expiry_hours = settings.FREE_MIN_EXPIRY_HOURS
        quota.max_expiry_hours = settings.FREE_MAX_EXPIRY_HOURS
        quota.max_downloads_limit = settings.FREE_MAX_DOWNLOADS_LIMIT
        quota.max_passwords_per_upload = settings.FREE_MAX_PASSWORDS_PER_UPLOAD
        quota.max_emails_per_upload = settings.FREE_MAX_EMAILS_PER_UPLOAD
        quota.can_use_separate_download_counts = True
        quota.can_use_email_stats = True
    elif user.tier == UserTier.premium:
        quota.min_expiry_hours = settings.PREMIUM_MIN_EXPIRY_HOURS
        quota.max_expiry_hours = settings.PREMIUM_MAX_EXPIRY_HOURS
        quota.max_downloads_limit = settings.PREMIUM_MAX_DOWNLOADS_LIMIT
        quota.max_passwords_per_upload = settings.PREMIUM_MAX_PASSWORDS_PER_UPLOAD
        quota.max_emails_per_upload = settings.PREMIUM_MAX_EMAILS_PER_UPLOAD
        quota.can_use_separate_download_counts = True
        quota.can_use_email_stats = True

    return quota
