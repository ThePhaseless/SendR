from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import func, select

from config import settings
from database import get_session
from models import FileUpload, User, UserLogin, UserTier, _utcnow
from routers.files import _load_group_access, _to_response
from schemas import (
    AdminUserListResponse,
    AdminUserLoginEntry,
    AdminUserLoginListResponse,
    AdminUserStatsResponse,
    AdminUserUpdateRequest,
    FileListResponse,
    UserResponse,
)
from security import get_admin_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _get_user_or_404(session: AsyncSession, user_id: int) -> User:
    result = await session.exec(select(User).where(User.id == user_id))
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> AdminUserListResponse:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if search:
        stmt = stmt.where(User.email.contains(search))
        count_stmt = count_stmt.where(User.email.contains(search))

    result = await session.exec(count_stmt)
    total = result.one()

    offset = (page - 1) * per_page
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    result = await session.exec(stmt)
    users = result.all()

    return AdminUserListResponse(
        users=[
            UserResponse(
                id=u.id,
                email=u.email,
                tier=u.tier.value,
                is_admin=u.is_admin,
                is_banned=u.is_banned,
            )
            for u in users
        ],
        total=total,
    )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: AdminUserUpdateRequest,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    stmt = select(User).where(User.id == user_id)
    result = await session.exec(stmt)
    user = result.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if body.tier is not None:
        try:
            user.tier = UserTier(body.tier)
        except ValueError as err:
            valid_tiers = ", ".join(t.value for t in UserTier)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier. Must be one of: {valid_tiers}",
            ) from err

    if body.is_admin is not None:
        if user.id == admin.id and not body.is_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove your own admin privileges",
            )
        user.is_admin = body.is_admin

    if body.is_banned is not None:
        if user.id == admin.id and body.is_banned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot ban your own account",
            )
        user.is_banned = body.is_banned

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        tier=user.tier.value,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    stmt = select(User).where(User.id == user_id)
    result = await session.exec(stmt)
    user = result.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await session.delete(user)
    await session.commit()

    return {"message": "User deleted"}


@router.get("/users/{user_id}/uploads")
async def list_user_uploads(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> FileListResponse:
    await _get_user_or_404(session, user_id)
    now = _utcnow()
    grace_cutoff = now - timedelta(
        days=max(settings.FILE_GRACE_PERIOD_DAYS, settings.PREMIUM_REFRESH_GRACE_DAYS)
    )
    stmt = (
        select(FileUpload)
        .where(
            FileUpload.user_id == user_id,
            FileUpload.is_active == True,  # noqa: E712
            FileUpload.expires_at > grace_cutoff,
        )
        .order_by(FileUpload.created_at.desc())
    )
    result = await session.exec(stmt)
    files = list(result.all())

    group_access_cache: dict[str, tuple[object | None, int, int]] = {}
    for file_upload in files:
        if file_upload.upload_group not in group_access_cache:
            group_settings, passwords, email_recipients = await _load_group_access(
                session, file_upload.upload_group
            )
            group_access_cache[file_upload.upload_group] = (
                group_settings,
                len(passwords),
                len(email_recipients),
            )

    return FileListResponse(
        files=[
            _to_response(file_upload, *group_access_cache[file_upload.upload_group])
            for file_upload in files
        ],
    )


@router.get("/users/{user_id}/logins")
async def list_user_logins(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> AdminUserLoginListResponse:
    await _get_user_or_404(session, user_id)
    result = await session.exec(
        select(UserLogin)
        .where(UserLogin.user_id == user_id)
        .order_by(UserLogin.logged_in_at.desc())
        .limit(50)
    )
    logins = list(result.all())

    return AdminUserLoginListResponse(
        logins=[
            AdminUserLoginEntry(
                id=login.id,
                auth_method=login.auth_method,
                ip_address=login.ip_address,
                logged_in_at=login.logged_in_at,
            )
            for login in logins
        ]
    )


@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> AdminUserStatsResponse:
    await _get_user_or_404(session, user_id)
    now = _utcnow()

    total_transfers_result = await session.exec(
        select(func.count(func.distinct(FileUpload.upload_group))).where(
            FileUpload.user_id == user_id
        )
    )
    active_transfers_result = await session.exec(
        select(func.count(func.distinct(FileUpload.upload_group))).where(
            FileUpload.user_id == user_id,
            FileUpload.is_active == True,  # noqa: E712
            FileUpload.expires_at > now,
        )
    )
    total_files_result = await session.exec(
        select(func.count(FileUpload.id)).where(FileUpload.user_id == user_id)
    )
    total_uploaded_bytes_result = await session.exec(
        select(func.coalesce(func.sum(FileUpload.file_size_bytes), 0)).where(
            FileUpload.user_id == user_id
        )
    )
    total_downloads_result = await session.exec(
        select(func.coalesce(func.sum(FileUpload.download_count), 0)).where(
            FileUpload.user_id == user_id
        )
    )
    login_count_result = await session.exec(
        select(func.count(UserLogin.id)).where(UserLogin.user_id == user_id)
    )
    last_login_result = await session.exec(
        select(func.max(UserLogin.logged_in_at)).where(UserLogin.user_id == user_id)
    )

    return AdminUserStatsResponse(
        total_transfers=total_transfers_result.one(),
        active_transfers=active_transfers_result.one(),
        total_files_uploaded=total_files_result.one(),
        total_uploaded_bytes=total_uploaded_bytes_result.one(),
        total_downloads=total_downloads_result.one(),
        login_count=login_count_result.one(),
        last_login_at=last_login_result.one(),
    )


@router.delete(
    "/users/{user_id}/transfers/{upload_group}", status_code=status.HTTP_200_OK
)
async def delete_user_transfer(
    user_id: int,
    upload_group: str,
    _admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    stmt = select(FileUpload).where(
        FileUpload.user_id == user_id,
        FileUpload.upload_group == upload_group,
        FileUpload.is_active == True,  # noqa: E712
    )
    result = await session.exec(stmt)
    files = list(result.all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found"
        )

    for file_upload in files:
        file_upload.is_active = False
        session.add(file_upload)

    await session.commit()

    return {"message": "Transfer deleted"}
