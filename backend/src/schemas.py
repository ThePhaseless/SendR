from datetime import datetime

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


class FileListResponse(SQLModel):
    files: list[FileUploadResponse]
    quota_used: int
    quota_limit: int


class QuotaResponse(SQLModel):
    files_used: int
    files_limit: int
    max_file_size_mb: int


class AdminUserUpdateRequest(SQLModel):
    tier: str | None = None
    is_admin: bool | None = None


class AdminUserListResponse(SQLModel):
    users: list[UserResponse]
    total: int
