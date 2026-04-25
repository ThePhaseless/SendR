from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlmodel import select

from database import get_session
from models import Subscription, SubscriptionPlan, User, UserTier, _utcnow
from schemas import SubscriptionResponse
from security import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("")
async def get_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    stmt = select(Subscription).where(
        Subscription.user_id == user.id,
        Subscription.is_active == True,  # noqa: E712
    )
    result = await session.exec(stmt)
    sub = result.first()

    if sub:
        return SubscriptionResponse(
            plan=sub.plan,
            is_active=True,
            started_at=sub.started_at,
            expires_at=sub.expires_at,
        )
    return SubscriptionResponse(plan="free", is_active=False)


@router.post("/upgrade")
async def upgrade_to_premium(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    """Mock upgrade to premium. In production, this would integrate with a payment provider."""
    # Deactivate existing subscriptions
    stmt = select(Subscription).where(
        Subscription.user_id == user.id,
        Subscription.is_active == True,  # noqa: E712
    )
    result = await session.exec(stmt)
    for old_sub in result.all():
        old_sub.is_active = False
        session.add(old_sub)

    now = _utcnow()
    sub = Subscription(
        user_id=user.id,
        plan=SubscriptionPlan.premium,
        started_at=now,
        expires_at=now + timedelta(days=30),
        is_active=True,
    )
    session.add(sub)

    # Upgrade user tier
    user.tier = UserTier.premium
    user.updated_at = now
    session.add(user)

    await session.commit()
    await session.refresh(sub)

    return SubscriptionResponse(
        plan=sub.plan,
        is_active=True,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
    )


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    """Cancel premium subscription. Downgrades user to free tier."""
    stmt = select(Subscription).where(
        Subscription.user_id == user.id,
        Subscription.is_active == True,  # noqa: E712
    )
    result = await session.exec(stmt)
    sub = result.first()

    if sub:
        sub.is_active = False
        session.add(sub)

    user.tier = UserTier.free
    user.updated_at = _utcnow()
    session.add(user)
    await session.commit()

    return SubscriptionResponse(plan="free", is_active=False)
