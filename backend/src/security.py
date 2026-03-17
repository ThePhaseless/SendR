import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from config import settings
from database import get_session
from models import AuthToken, User, _utcnow

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
    result = await session.execute(stmt)
    auth_token = result.scalars().first()
    if not auth_token:
        return None
    stmt = select(User).where(User.id == auth_token.user_id)
    result = await session.execute(stmt)
    return result.scalars().first()


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
    return user


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_optional_user(
    authorization: str | None = Depends(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    token = _extract_token(authorization)
    if not token:
        return None
    return await verify_token(token, session)
