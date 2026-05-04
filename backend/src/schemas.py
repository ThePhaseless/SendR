from datetime import UTC, datetime  # noqa: TC003
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _serialize_utc_datetime(value: datetime) -> str:
    normalized = (
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    )
    return normalized.isoformat().replace("+00:00", "Z")


ApiDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize_utc_datetime, return_type=str, when_used="json"),
]

EmailAddress = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, strict=True)


class ErrorDetail(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    detail: ErrorDetail


class EmailVerificationRequest(ApiModel):
    email: EmailAddress


class CodeVerificationRequest(ApiModel):
    email: EmailAddress
    code: str = Field(min_length=6, max_length=6)
    create_account: bool = False


class SessionResponse(ApiModel):
    expires_at: ApiDateTime


TokenResponse = SessionResponse


class PasswordLoginRequest(ApiModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=128)


class SetPasswordRequest(ApiModel):
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(ApiModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(ApiModel):
    id: int
    email: str
    tier: str
    is_admin: bool = False
    is_banned: bool = False
    has_password: bool = False


class FileUploadResponse(ApiModel):
    id: int
    original_filename: str
    file_size_bytes: int
    download_url: str
    expires_at: ApiDateTime
    download_count: int
    public_download_count: int = 0
    restricted_download_count: int = 0
    max_downloads: int | None = None
    separate_download_counts: bool = False
    is_active: bool
    upload_group: str | None = None
    message: str | None = None
    is_public: bool = True
    has_passwords: bool = False
    has_email_recipients: bool = False
    viewer_is_owner: bool = False
    group_download_only: bool = False


class FileListResponse(ApiModel):
    files: list[FileUploadResponse]


class QuotaResponse(ApiModel):
    max_file_size_mb: int
    max_files_per_upload: int
    weekly_uploads_limit: int
    weekly_uploads_used: int
    weekly_uploads_remaining: int
    # Weekly size quota (bytes, 0 = unlimited)
    weekly_upload_size_limit_bytes: int = 0
    weekly_upload_size_used_bytes: int = 0
    weekly_upload_size_remaining_bytes: int = 0
    # Expiry options
    expiry_options_hours: list[int] | None = None  # Discrete choices (temporary)
    min_expiry_hours: int | None = None  # Range min (free/premium)
    max_expiry_hours: int | None = None  # Range max (free/premium)
    # Max download options
    max_downloads_options: list[int] | None = None  # Discrete choices (temporary)
    max_downloads_limit: int | None = None  # Upper bound for freeform (free/premium)
    # Access control limits
    max_passwords_per_upload: int = 0
    max_emails_per_upload: int = 0
    # Feature capabilities per tier
    can_use_separate_download_counts: bool = False
    can_use_email_stats: bool = False


class MultiFileUploadResponse(ApiModel):
    files: list[FileUploadResponse]
    upload_group: str
    total_size_bytes: int
    title: str | None = None
    description: str | None = None


class UploadGroupInfoResponse(ApiModel):
    files: list[FileUploadResponse]
    upload_group: str
    total_size_bytes: int
    file_count: int
    will_zip: bool
    is_public: bool = True
    has_passwords: bool = False
    has_email_recipients: bool = False
    separate_download_counts: bool = False
    title: str | None = None
    description: str | None = None
    viewer_is_owner: bool = False


class TransferInfoResponse(ApiModel):
    upload_group: str
    message: str | None = None
    sender_email: str | None = None
    has_password: bool = False
    created_at: ApiDateTime
    expires_at: ApiDateTime
    files: list[FileUploadResponse]
    total_size_bytes: int
    file_count: int


class LimitsResponse(ApiModel):
    max_file_size_mb: int
    max_files_per_upload: int
    weekly_uploads_limit: int
    weekly_upload_size_limit_bytes: int = 0
    # Expiry options for temporary tier
    expiry_options_hours: list[int]
    # Max download options for temporary tier
    max_downloads_options: list[int]
    # Access control limits
    max_passwords_per_upload: int = 1
    max_emails_per_upload: int = 0
    # Feature capabilities (always false for temporary/unauthenticated)
    can_use_separate_download_counts: bool = False
    can_use_email_stats: bool = False


class FileEditRequest(ApiModel):
    original_filename: str | None = None
    message: str | None = None
    expires_in_hours: int | None = None
    max_downloads: int | None = None


class GroupRefreshRequest(ApiModel):
    expiry_hours: int | None = None
    max_downloads: int | None = None
    title: str | None = None
    description: str | None = None


class GroupEditRequest(ApiModel):
    expiry_hours: int | None = None
    max_downloads: int | None = None
    title: str | None = None
    description: str | None = None


class AdminUserUpdateRequest(ApiModel):
    tier: str | None = None
    is_admin: bool | None = None
    is_banned: bool | None = None


class AdminUserListResponse(ApiModel):
    users: list[UserResponse]
    total: int


class AdminUserLoginEntry(ApiModel):
    id: int
    auth_method: str
    ip_address: str | None = None
    logged_in_at: ApiDateTime


class AdminUserLoginListResponse(ApiModel):
    logins: list[AdminUserLoginEntry]


class AdminUserStatsResponse(ApiModel):
    total_transfers: int
    active_transfers: int
    total_files_uploaded: int
    total_uploaded_bytes: int
    total_downloads: int
    login_count: int
    last_login_at: ApiDateTime | None = None


class DownloadStatEntry(ApiModel):
    access_type: str
    identifier: str | None = None  # password label or email address
    download_count: int
    last_download: ApiDateTime | None = None


class DownloadStatsResponse(ApiModel):
    stats: list[DownloadStatEntry]
    total_downloads: int


class PasswordInfo(ApiModel):
    id: int
    label: str


class EmailRecipientInfo(ApiModel):
    id: int
    email: str
    notified: bool


class PasswordEntry(ApiModel):
    label: str
    password: str


class AccessEditRequest(ApiModel):
    is_public: bool | None = None
    show_email_stats: bool | None = None
    separate_download_counts: bool | None = None
    passwords_to_add: list[PasswordEntry] | None = None
    password_ids_to_remove: list[int] | None = None
    emails_to_add: list[str] | None = None
    email_ids_to_remove: list[int] | None = None


class AccessInfoResponse(ApiModel):
    is_public: bool
    passwords: list[PasswordInfo]
    emails: list[EmailRecipientInfo]
    show_email_stats: bool
    separate_download_counts: bool = False


class RecipientDownloadEntry(ApiModel):
    email: str
    download_count: int


class RecipientStatsResponse(ApiModel):
    downloads: list[RecipientDownloadEntry]
    total_downloads: int


class SubscriptionResponse(ApiModel):
    plan: str
    is_active: bool
    started_at: ApiDateTime | None = None
    expires_at: ApiDateTime | None = None
