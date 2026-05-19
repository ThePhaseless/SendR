# Backend API Schemas (Pydantic)

The API schemas are grouped by request area instead of listed as one oversized diagram.

## Auth And Account Schemas

```mermaid
classDiagram
    direction LR

    class EmailVerificationRequest {
      +email: str
    }

    class CodeVerificationRequest {
      +email: str
      +code: str
      +create_account: bool
    }

    class PasswordLoginRequest {
      +email: str
      +password: str
    }

    class SessionResponse {
      +user: UserResponse
      +expires_at: datetime
    }

    class UserResponse {
      +id: int
      +email: str
      +tier: str
      +is_admin: bool
    }

    class PasswordRequests {
      +set_password
      +change_password
    }

    SessionResponse --> UserResponse : contains
    CodeVerificationRequest --> SessionResponse : returns
    PasswordLoginRequest --> SessionResponse : returns

    note for SessionResponse "Browser auth is represented by HttpOnly cookies plus user data"
```

## File And Group Schemas

```mermaid
classDiagram
    direction LR

    class FileUploadResponse {
      +id: int
      +original_filename: str
      +file_size_bytes: int
      +download_url: str
      +scan_status: str
      +expires_at: datetime
    }

    class FileListResponse {
      +files: list
    }

    class MultiFileUploadResponse {
      +files: list
      +upload_group: str
      +total_size_bytes: int
    }

    class UploadGroupInfoResponse {
      +files: list
      +upload_group: str
      +total_size_bytes: int
      +file_count: int
      +will_zip: bool
    }

    class TransferInfoResponse {
      +upload_group: str
      +has_password: bool
      +created_at: datetime
      +expires_at: datetime
      +files: list
    }

    FileListResponse --> FileUploadResponse : contains
    MultiFileUploadResponse --> FileUploadResponse : contains
    UploadGroupInfoResponse --> FileUploadResponse : contains
    TransferInfoResponse --> FileUploadResponse : contains
```

## Access And Statistics Schemas

```mermaid
classDiagram
    direction LR

    class PasswordInfo {
      +id: int
      +label: str
    }

    class EmailRecipientInfo {
      +id: int
      +email: str
      +notified: bool
    }

    class PasswordEntry {
      +label: str
      +password: str
    }

    class AccessEditRequest {
      +publicFlagChanges
      +passwordChanges
      +emailRecipientChanges
    }

    class AccessInfoResponse {
      +is_public: bool
      +passwords: list
      +emails: list
      +show_email_stats: bool
    }

    class DownloadStatEntry {
      +access_type: str
      +identifier: str optional
      +download_count: int
      +last_download: datetime optional
    }

    class DownloadStatsResponse {
      +stats: list
      +total_downloads: int
    }

    class RecipientStatsResponse {
      +downloads: list
      +total_downloads: int
    }

    AccessInfoResponse --> PasswordInfo : contains
    AccessInfoResponse --> EmailRecipientInfo : contains
    AccessEditRequest --> PasswordEntry : adds
    DownloadStatsResponse --> DownloadStatEntry : contains
    RecipientStatsResponse --> DownloadStatEntry : summarizes
```

## Admin, Limits, And Mutations

```mermaid
classDiagram
    direction LR

    class AdminUserUpdateRequest {
      +tier: str optional
      +is_admin: bool optional
    }

    class AdminUserListResponse {
      +users: list
      +total: int
    }

    class AdminUserStatsResponse {
      +total_uploads: int
      +total_bytes: int
      +active_uploads: int
    }

    class SubscriptionResponse {
      +plan: str
      +is_active: bool
      +started_at: datetime optional
    }

    class QuotaResponse {
      +max_file_size_mb: int
      +max_files_per_upload: int
      +weekly_uploads_limit: int
      +weekly_uploads_used: int
      +weekly_uploads_remaining: int
    }

    class LimitsResponse {
      +max_file_size_mb: int
      +max_files_per_upload: int
      +weekly_uploads_limit: int
    }

    class FileEditRequest {
      +filenameMessageUpdates
      +expiryDownloadUpdates
    }

    class GroupMutationRequest {
      +expiry_hours: int optional
      +max_downloads: int optional
      +title: str optional
      +description: str optional
    }

    AdminUserListResponse --> UserResponse : contains
    AdminUserStatsResponse --> UserResponse : describes
    GroupMutationRequest --> FileEditRequest : similar purpose
```

---

Pydantic request and response schemas used by the FastAPI contract.