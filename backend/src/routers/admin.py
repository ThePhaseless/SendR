from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import func, select

from src.database import get_session
from models import User, UserTier
from schemas import AdminUserListResponse, AdminUserUpdateRequest, UserResponse
from security import get_admin_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/admin", tags=["admin"])


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

    result = await session.execute(count_stmt)
    total = result.scalar_one()

    offset = (page - 1) * per_page
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    result = await session.execute(stmt)
    users = result.scalars().all()

    return AdminUserListResponse(
        users=[UserResponse(id=u.id, email=u.email, tier=u.tier.value, is_admin=u.is_admin) for u in users],
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
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.tier is not None:
        try:
            user.tier = UserTier(body.tier)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier. Must be one of: {', '.join(t.value for t in UserTier)}",
            ) from err

    if body.is_admin is not None:
        if user.id == admin.id and not body.is_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove your own admin privileges",
            )
        user.is_admin = body.is_admin

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserResponse(id=user.id, email=user.email, tier=user.tier.value, is_admin=user.is_admin)


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
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await session.delete(user)
    await session.commit()

    return {"message": "User deleted"}
