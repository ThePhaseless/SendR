import enum
from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (for SQLite compatibility)."""
    return datetime.now(UTC).replace(tzinfo=None)


class UserTier(enum.StrEnum):
    temporary = "temporary"
    free = "free"
    premium = "premium"


class SubscriptionPlan(enum.StrEnum):
    free = "free"
    premium = "premium"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    tier: UserTier = Field(default=UserTier.free)
    is_admin: bool = Field(default=False)
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
    upload_group: str = Field(default_factory=lambda: str(uuid4()), index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = Field(default=True)


class UploadGroupSettings(SQLModel, table=True):
    upload_group: str = Field(primary_key=True, index=True)
    is_public: bool = Field(default=True)
    show_email_stats: bool = Field(default=False)


class UploadPassword(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    upload_group: str = Field(index=True)
    label: str
    password_hash: str
    created_at: datetime = Field(default_factory=_utcnow)


class UploadEmailRecipient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    upload_group: str = Field(index=True)
    email: str
    token_hash: str = Field(index=True)
    notified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


class DownloadLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    upload_group: str = Field(index=True)
    file_upload_id: int | None = Field(default=None, foreign_key="fileupload.id")
    access_type: str  # "public" | "password" | "email" | "owner"
    upload_password_id: int | None = Field(default=None, foreign_key="uploadpassword.id")
    email_recipient_id: int | None = Field(default=None, foreign_key="uploademailrecipient.id")
    downloaded_at: datetime = Field(default_factory=_utcnow)


class Transfer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    upload_group: str = Field(unique=True, index=True)
    message: str | None = Field(default=None)
    recipient_emails: str | None = Field(default=None)  # JSON list of emails
    password_hash: str | None = Field(default=None)
    notify_on_download: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime


class Subscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    plan: SubscriptionPlan
    started_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    is_active: bool = Field(default=True)
