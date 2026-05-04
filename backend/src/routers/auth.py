from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import func, select

from config import settings
from database import get_session
from email_utils import send_verification_email
from models import (
    AuthToken,
    FileUpload,
    User,
    UserLogin,
    UserTier,
    VerificationCode,
    _utcnow,
)
from rate_limit import auth_rate_limiter, get_client_ip
from schemas import (
    ChangePasswordRequest,
    CodeVerificationRequest,
    EmailVerificationRequest,
    LimitsResponse,
    PasswordLoginRequest,
    QuotaResponse,
    SessionResponse,
    SetPasswordRequest,
    UserResponse,
)
from security import (
    api_key_header,
    clear_session_cookie,
    create_access_token,
    generate_verification_code,
    get_current_user,
    hash_token,
    hash_user_password,
    resolve_request_token,
    set_session_cookie,
    verify_user_password,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await session.exec(stmt)
    return result.first()


def _validate_account_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if len(password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 128 characters or fewer.",
        )
    return password


async def _issue_auth_token(
    session: AsyncSession,
    user: User,
    auth_method: str,
    request: Request,
    response: Response,
) -> SessionResponse:
    raw_token, expires_at = create_access_token(user.id)
    session.add(
        AuthToken(
            user_id=user.id,
            token=hash_token(raw_token),
            expires_at=expires_at,
        )
    )
    session.add(
        UserLogin(
            user_id=user.id,
            auth_method=auth_method,
            ip_address=get_client_ip(request),
        )
    )
    await session.commit()
    set_session_cookie(response, raw_token, expires_at)
    return SessionResponse(expires_at=expires_at)


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        tier=user.tier.value,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
        has_password=bool(user.password_hash),
    )


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
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    auth_rate_limiter.check(get_client_ip(request))

    user = await _get_user_by_email(session, body.email)
    if user and user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned"
        )

    code = generate_verification_code()
    expires_at = _utcnow() + timedelta(
        minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
    )

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
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SessionResponse:
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned"
        )
    elif body.create_account and user.tier == UserTier.temporary:
        # Upgrade temporary user to free on registration
        user.tier = UserTier.free
        session.add(user)

    return await _issue_auth_token(
        session, user, "verification_code", request, response
    )


@router.post("/login-password")
async def login_password(
    body: PasswordLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SessionResponse:
    auth_rate_limiter.check(get_client_ip(request))

    user = await _get_user_by_email(session, body.email)
    if not user or not verify_user_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned"
        )

    return await _issue_auth_token(session, user, "password", request, response)


@router.get("/me")
async def get_me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return _to_user_response(user)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Depends(api_key_header)] = None,
) -> dict[str, str]:
    token = resolve_request_token(request, authorization)
    if token:
        stmt = select(AuthToken).where(AuthToken.token == hash_token(token))
        result = await session.exec(stmt)
        auth_token = result.first()
        if auth_token:
            await session.delete(auth_token)
            await session.commit()

    clear_session_cookie(response)
    return {"message": "Logged out"}


@router.post("/set-password")
async def set_password(
    body: SetPasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    if user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password already set"
        )

    user.password_hash = hash_user_password(_validate_account_password(body.password))
    user.updated_at = _utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _to_user_response(user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password set for this account",
        )
    if not verify_user_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_user_password(
        _validate_account_password(body.new_password)
    )
    user.updated_at = _utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _to_user_response(user)


@router.get("/limits")
async def get_limits(response: Response) -> LimitsResponse:
    """Return upload limits for temporary tier (public, no auth required)."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return LimitsResponse(
        max_file_size_mb=settings.TEMPORARY_MAX_FILE_SIZE_MB,
        max_files_per_upload=settings.TEMPORARY_MAX_FILES_PER_UPLOAD,
        weekly_uploads_limit=settings.TEMPORARY_MAX_WEEKLY_UPLOADS,
        expiry_options_hours=settings.TEMPORARY_EXPIRY_OPTIONS_HOURS,
        max_downloads_options=settings.TEMPORARY_MAX_DOWNLOADS_OPTIONS,
    )


@router.get("/quota")
async def get_quota(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
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
    weekly_remaining = (
        max(0, weekly_limit - weekly_used) if weekly_limit > 0 else weekly_limit
    )

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
