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
    is_active: bool
    upload_group: str | None = None


class FileListResponse(SQLModel):
    files: list[FileUploadResponse]


class QuotaResponse(SQLModel):
    max_file_size_mb: int
    max_files_per_upload: int


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


class LimitsResponse(SQLModel):
    max_file_size_mb: int
    max_files_per_upload: int


class AdminUserUpdateRequest(SQLModel):
    tier: str | None = None
    is_admin: bool | None = None


class AdminUserListResponse(SQLModel):
    users: list[UserResponse]
    total: int
