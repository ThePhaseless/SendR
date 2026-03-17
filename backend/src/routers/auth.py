from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from config import settings
from database import get_session
from email_utils import send_verification_email
from models import AuthToken, FileUpload, User, UserTier, VerificationCode, _utcnow
from rate_limit import auth_rate_limiter, get_client_ip
from schemas import (
    CodeVerificationRequest,
    EmailVerificationRequest,
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

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_quota_for_tier(tier: UserTier) -> tuple[int, int]:
    if tier == UserTier.premium:
        return settings.PREMIUM_MAX_FILES_PER_WEEK, settings.PREMIUM_MAX_FILE_SIZE_MB
    if tier == UserTier.free:
        return settings.FREE_MAX_FILES_PER_WEEK, settings.FREE_MAX_FILE_SIZE_MB
    return settings.ANON_MAX_FILES_PER_WEEK, settings.ANON_MAX_FILE_SIZE_MB


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
        user = User(email=body.email, tier=UserTier.free)
        session.add(user)
        await session.flush()

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


@router.get("/quota")
async def get_quota(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuotaResponse:
    one_week_ago = _utcnow() - timedelta(days=7)
    stmt = (
        select(func.count())
        .select_from(FileUpload)
        .where(FileUpload.user_id == user.id, FileUpload.created_at >= one_week_ago)
    )
    result = await session.execute(stmt)
    files_used = result.scalar_one()
    files_limit, max_file_size_mb = _get_quota_for_tier(user.tier)

    return QuotaResponse(
        files_used=files_used,
        files_limit=files_limit,
        max_file_size_mb=max_file_size_mb,
    )
