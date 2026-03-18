from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from config import settings
from database import get_session
from models import AuthToken, User, UserTier
from schemas import TokenResponse
from security import create_access_token, hash_token

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/login/{role}")
async def dev_login(role: str, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    if not settings.DEV_MODE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if role not in ("admin", "user"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role. Must be 'admin' or 'user'")

    email = f"dev-{role}@sendr.local"

    # Find or create the dev user
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        user = User(
            email=email,
            tier=UserTier.premium if role == "admin" else UserTier.free,
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
    await session.commit()

    return TokenResponse(token=raw_token, expires_at=expires_at)
