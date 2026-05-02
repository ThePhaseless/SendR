import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import database
from app import app
from models import AuthToken, User, UserLogin, UserTier
from rate_limit import auth_rate_limiter
from security import create_access_token, hash_token, hash_user_password


@pytest.fixture(autouse=True)
def _reset_auth_rate_limiter():
    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


@pytest.mark.asyncio
async def test_get_limits_returns_basic_tier():
    """GET /api/auth/limits should return basic tier upload limits."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/auth/limits")

    assert response.status_code == 200
    data = response.json()
    assert "max_file_size_mb" in data
    assert "max_files_per_upload" in data
    assert isinstance(data["max_file_size_mb"], int)
    assert isinstance(data["max_files_per_upload"], int)


@pytest.mark.asyncio
async def test_password_login_returns_token_and_records_login():
    async with database.async_session() as session:
        user = User(
            email="password-login@sendr.local",
            tier=UserTier.free,
            password_hash=hash_user_password("TopSecret123"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login-password",
            json={"email": "password-login@sendr.local", "password": "TopSecret123"},
        )

    assert response.status_code == 200
    assert "token" in response.json()

    async with database.async_session() as session:
        result = await session.exec(select(UserLogin).where(UserLogin.user_id == user.id))
        logins = list(result.all())

    assert any(login.auth_method == "password" for login in logins)


@pytest.mark.asyncio
async def test_set_password_allows_future_password_login(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        set_response = await client.post(
            "/api/auth/set-password",
            json={"password": "FreshPass123"},
            headers=auth_headers,
        )

        login_response = await client.post(
            "/api/auth/login-password",
            json={"email": "test@sendr.local", "password": "FreshPass123"},
        )

    assert set_response.status_code == 200
    assert set_response.json()["has_password"] is True
    assert login_response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("auth_headers")
async def test_change_password_replaces_existing_password():
    async with database.async_session() as session:
        result = await session.exec(select(User).where(User.email == "test@sendr.local"))
        user = result.first()
        user.password_hash = hash_user_password("CurrentPass123")
        session.add(user)

        raw_token, expires_at = create_access_token(user.id)
        session.add(AuthToken(user_id=user.id, token=hash_token(raw_token), expires_at=expires_at))
        await session.commit()

    headers = {"Authorization": f"Bearer {raw_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        wrong_current = await client.post(
            "/api/auth/change-password",
            json={"current_password": "WrongPass123", "new_password": "UpdatedPass123"},
            headers=headers,
        )
        change_response = await client.post(
            "/api/auth/change-password",
            json={"current_password": "CurrentPass123", "new_password": "UpdatedPass123"},
            headers=headers,
        )
        old_login = await client.post(
            "/api/auth/login-password",
            json={"email": "test@sendr.local", "password": "CurrentPass123"},
        )
        new_login = await client.post(
            "/api/auth/login-password",
            json={"email": "test@sendr.local", "password": "UpdatedPass123"},
        )

    assert wrong_current.status_code == 400
    assert change_response.status_code == 200
    assert change_response.json()["has_password"] is True
    assert old_login.status_code == 401
    assert new_login.status_code == 200
