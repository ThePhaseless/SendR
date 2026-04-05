from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import func, select

from config import settings
from database import get_session
from email_utils import send_verification_email
from models import AuthToken, FileUpload, User, UserTier, VerificationCode, _utcnow
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


@router.post("/request-code", status_code=status.HTTP_200_OK)
async def request_code(
    body: EmailVerificationRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    auth_rate_limiter.check(get_client_ip(request))

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
    result = await session.execute(stmt)
    vc = result.scalars().first()
    if not vc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    vc.used = True
    session.add(vc)

    # Find or create user
    stmt = select(User).where(User.email == body.email)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        tier = UserTier.free if body.create_account else UserTier.temporary
        user = User(email=body.email, tier=tier)
        session.add(user)
        await session.flush()
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
    await session.commit()

    return TokenResponse(token=raw_token, expires_at=expires_at)


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, tier=user.tier.value, is_admin=user.is_admin)


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

    quota = QuotaResponse(
        max_file_size_mb=max_file_size_mb,
        max_files_per_upload=max_files_per_upload,
        weekly_uploads_limit=weekly_limit,
        weekly_uploads_used=weekly_used,
        weekly_uploads_remaining=weekly_remaining,
    )

    # Populate tier-specific expiry/download options
    if user.tier == UserTier.temporary:
        quota.expiry_options_hours = settings.TEMPORARY_EXPIRY_OPTIONS_HOURS
        quota.max_downloads_options = settings.TEMPORARY_MAX_DOWNLOADS_OPTIONS
    elif user.tier == UserTier.free:
        quota.min_expiry_hours = settings.FREE_MIN_EXPIRY_HOURS
        quota.max_expiry_hours = settings.FREE_MAX_EXPIRY_HOURS
        quota.max_downloads_limit = settings.FREE_MAX_DOWNLOADS_LIMIT
    elif user.tier == UserTier.premium:
        quota.min_expiry_hours = settings.PREMIUM_MIN_EXPIRY_HOURS
        quota.max_expiry_hours = settings.PREMIUM_MAX_EXPIRY_HOURS
        quota.max_downloads_limit = settings.PREMIUM_MAX_DOWNLOADS_LIMIT

    return quota
