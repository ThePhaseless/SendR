import enum
from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (for SQLite compatibility)."""
    return datetime.now(UTC).replace(tzinfo=None)


class UserTier(enum.StrEnum):
    anonymous = "anonymous"
    free = "free"
    premium = "premium"


class SubscriptionPlan(enum.StrEnum):
    free = "free"
    premium = "premium"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    tier: UserTier = Field(default=UserTier.free)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class VerificationCode(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    code: str
    expires_at: datetime
    used: bool = Field(default=False)


class AuthToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=_utcnow)


class FileUpload(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    original_filename: str
    stored_filename: str = Field(default_factory=lambda: str(uuid4()))
    file_size_bytes: int
    download_token: str = Field(unique=True, index=True)
    download_count: int = Field(default=0)
    max_downloads: int | None = Field(default=None)
    expires_at: datetime
    created_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = Field(default=True)


class Subscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    plan: SubscriptionPlan
    started_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    is_active: bool = Field(default=True)
