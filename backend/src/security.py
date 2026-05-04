import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlmodel import select

from config import settings
from database import get_session
from models import AuthToken, User, _utcnow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def generate_verification_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_secret(secret: str) -> str:
    return password_context.hash(secret)


def verify_secret(secret: str, secret_hash: str | None) -> bool:
    if not secret_hash:
        return False
    try:
        return password_context.verify(secret, secret_hash)
    except UnknownHashError, ValueError:
        return False


def hash_user_password(password: str) -> str:
    return hash_secret(password)


def verify_user_password(password: str, password_hash: str | None) -> bool:
    return verify_secret(password, password_hash)


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


def resolve_request_token(request: Request, authorization: str | None) -> str | None:
    token = _extract_token(authorization)
    if token:
        return token
    return request.cookies.get(settings.SESSION_COOKIE_NAME)


def set_session_cookie(
    response: Response, raw_token: str, expires_at: datetime
) -> None:
    cookie_expires = (
        expires_at.replace(tzinfo=UTC)
        if expires_at.tzinfo is None
        else expires_at.astimezone(UTC)
    )
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        max_age=settings.TOKEN_EXPIRE_MINUTES * 60,
        expires=cookie_expires,
        path="/",
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.is_production,
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        httponly=False,
        max_age=settings.TOKEN_EXPIRE_MINUTES * 60,
        expires=cookie_expires,
        path="/",
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.is_production,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.is_production,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.is_production,
    )


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Depends(api_key_header)] = None,
) -> User:
    token = resolve_request_token(request, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user = await verify_token(token, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned"
        )
    return user


async def get_optional_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Depends(api_key_header)] = None,
) -> User | None:
    token = resolve_request_token(request, authorization)
    if not token:
        return None
    user = await verify_token(token, session)
    if user and user.is_banned:
        return None
    return user


async def get_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
