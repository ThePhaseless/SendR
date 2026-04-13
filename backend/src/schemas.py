from datetime import datetime  # noqa: TC003

from sqlmodel import SQLModel


class EmailVerificationRequest(SQLModel):
    email: str


class CodeVerificationRequest(SQLModel):
    email: str
    code: str
    create_account: bool = False


class TokenResponse(SQLModel):
    token: str
    expires_at: datetime


class UserResponse(SQLModel):
    id: int
    email: str
    tier: str
    is_admin: bool = False


class FileUploadResponse(SQLModel):
    id: int
    original_filename: str
    file_size_bytes: int
    download_url: str
    expires_at: datetime
    download_count: int
    max_downloads: int | None = None
    is_active: bool
    upload_group: str | None = None
    message: str | None = None
    is_public: bool = True
    has_passwords: bool = False
    has_email_recipients: bool = False


class FileListResponse(SQLModel):
    files: list[FileUploadResponse]


class QuotaResponse(SQLModel):
    max_file_size_mb: int
    max_files_per_upload: int
    weekly_uploads_limit: int
    weekly_uploads_used: int
    weekly_uploads_remaining: int
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


class MultiFileUploadResponse(SQLModel):
    files: list[FileUploadResponse]
    upload_group: str
    total_size_bytes: int
    title: str | None = None
    description: str | None = None


class UploadGroupInfoResponse(SQLModel):
    files: list[FileUploadResponse]
    upload_group: str
    total_size_bytes: int
    file_count: int
    will_zip: bool
    is_public: bool = True
    has_passwords: bool = False
    has_email_recipients: bool = False
    title: str | None = None
    description: str | None = None


class TransferInfoResponse(SQLModel):
    upload_group: str
    message: str | None = None
    sender_email: str | None = None
    has_password: bool = False
    created_at: datetime
    expires_at: datetime
    files: list[FileUploadResponse]
    total_size_bytes: int
    file_count: int


class LimitsResponse(SQLModel):
    max_file_size_mb: int
    max_files_per_upload: int
    weekly_uploads_limit: int
    # Expiry options for temporary tier
    expiry_options_hours: list[int]
    # Max download options for temporary tier
    max_downloads_options: list[int]
    # Access control limits
    max_passwords_per_upload: int = 1
    max_emails_per_upload: int = 0


class FileEditRequest(SQLModel):
    original_filename: str | None = None
    message: str | None = None
    expires_in_hours: int | None = None
    max_downloads: int | None = None


class GroupRefreshRequest(SQLModel):
    expiry_hours: int | None = None
    max_downloads: int | None = None
    title: str | None = None
    description: str | None = None


class GroupEditRequest(SQLModel):
    expiry_hours: int | None = None
    max_downloads: int | None = None
    title: str | None = None
    description: str | None = None


class AdminUserUpdateRequest(SQLModel):
    tier: str | None = None
    is_admin: bool | None = None


class AdminUserListResponse(SQLModel):
    users: list[UserResponse]
    total: int


class DownloadStatEntry(SQLModel):
    access_type: str
    identifier: str | None = None  # password label or email address
    download_count: int
    last_download: datetime | None = None


class DownloadStatsResponse(SQLModel):
    stats: list[DownloadStatEntry]
    total_downloads: int


class PasswordInfo(SQLModel):
    id: int
    label: str


class EmailRecipientInfo(SQLModel):
    id: int
    email: str
    notified: bool


class AccessInfoResponse(SQLModel):
    is_public: bool
    passwords: list[PasswordInfo]
    emails: list[EmailRecipientInfo]
    show_email_stats: bool


class RecipientDownloadEntry(SQLModel):
    email: str
    download_count: int


class RecipientStatsResponse(SQLModel):
    downloads: list[RecipientDownloadEntry]
    total_downloads: int


class SubscriptionResponse(SQLModel):
    plan: str
    is_active: bool
    started_at: datetime | None = None
    expires_at: datetime | None = None
