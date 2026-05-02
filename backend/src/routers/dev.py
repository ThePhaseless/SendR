from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select

from config import settings
from database import get_session
from models import AuthToken, User, UserLogin, UserTier
from rate_limit import get_client_ip
from schemas import TokenResponse
from security import create_access_token, hash_token

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/login/{role}")
async def dev_login(
    role: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    if not settings.is_local:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if role not in ("admin", "user", "premium"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin', 'user', or 'premium'",
        )

    email = f"dev-{role}@sendr.local"

    # Find or create the dev user
    stmt = select(User).where(User.email == email)
    result = await session.exec(stmt)
    user = result.first()

    if user and user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")

    if not user:
        tier = UserTier.free
        if role in ("admin", "premium"):
            tier = UserTier.premium
        user = User(
            email=email,
            tier=tier,
            is_admin=(role == "admin"),
        )
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
    session.add(
        UserLogin(
            user_id=user.id,
            auth_method="dev_login",
            ip_address=get_client_ip(request),
        )
    )
    await session.commit()

    return TokenResponse(token=raw_token, expires_at=expires_at)
