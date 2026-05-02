import hashlib
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlmodel import select

from config import settings
from database import get_session
from models import AuthToken, User, _utcnow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def generate_verification_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(_user_id: int) -> tuple[str, datetime]:
    raw_token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES)
    return raw_token, expires_at


async def verify_token(token: str, session: AsyncSession) -> User | None:
    hashed = hash_token(token)
    stmt = select(AuthToken).where(
        AuthToken.token == hashed,
        AuthToken.expires_at > _utcnow(),
    )
    result = await session.exec(stmt)
    auth_token = result.first()
    if not auth_token:
        return None
    stmt = select(User).where(User.id == auth_token.user_id)
    result = await session.exec(stmt)
    return result.first()


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization


async def get_current_user(
    authorization: str | None = Depends(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await verify_token(token, session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")
    return user


async def get_optional_user(
    authorization: str | None = Depends(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    token = _extract_token(authorization)
    if not token:
        return None
    user = await verify_token(token, session)
    if user and user.is_banned:
        return None
    return user


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
