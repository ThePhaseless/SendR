from datetime import datetime  # noqa: TC003

from sqlmodel import SQLModel


class EmailVerificationRequest(SQLModel):
    email: str


class CodeVerificationRequest(SQLModel):
    email: str
    code: str


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
    has_password: bool = False


class FileListResponse(SQLModel):
    files: list[FileUploadResponse]


class QuotaResponse(SQLModel):
    max_file_size_mb: int
    max_files_per_upload: int
    weekly_uploads_limit: int
    weekly_uploads_used: int
    weekly_uploads_remaining: int
    # Expiry options
    expiry_options_hours: list[int] | None = None  # Discrete choices (basic)
    min_expiry_hours: int | None = None  # Range min (free/premium)
    max_expiry_hours: int | None = None  # Range max (free/premium)
    # Max download options
    max_downloads_options: list[int] | None = None  # Discrete choices (basic)
    max_downloads_limit: int | None = None  # Upper bound for freeform (free/premium)


class MultiFileUploadResponse(SQLModel):
    files: list[FileUploadResponse]
    upload_group: str
    total_size_bytes: int


class UploadGroupInfoResponse(SQLModel):
    files: list[FileUploadResponse]
    upload_group: str
    total_size_bytes: int
    file_count: int
    will_zip: bool


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
    # Expiry options for basic tier
    expiry_options_hours: list[int]
    # Max download options for basic tier
    max_downloads_options: list[int]


class FileEditRequest(SQLModel):
    original_filename: str | None = None
    message: str | None = None
    password: str | None = None
    remove_password: bool = False
    expires_in_hours: int | None = None
    max_downloads: int | None = None


class AdminUserUpdateRequest(SQLModel):
    tier: str | None = None
    is_admin: bool | None = None


class AdminUserListResponse(SQLModel):
    users: list[UserResponse]
    total: int


class SubscriptionResponse(SQLModel):
    plan: str
    is_active: bool
    started_at: datetime | None = None
    expires_at: datetime | None = None
