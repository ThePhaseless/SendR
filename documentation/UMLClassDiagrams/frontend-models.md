# Frontend TypeScript Models

Generated models are grouped by feature so the diagrams remain narrow.

## Auth And Admin Models

```mermaid
classDiagram
    direction LR

    class UserResponse {
      +id: number
      +email: string
      +tier: string
      +is_admin: boolean optional
    }

    class SessionResponse {
      +user: UserResponse
      +expires_at: string
    }

    class EmailVerificationRequest {
      +email: string
    }

    class CodeVerificationRequest {
      +email: string
      +code: string
      +create_account: boolean optional
    }

    class PasswordLoginRequest {
      +email: string
      +password: string
    }

    class AdminUserUpdateRequest {
      +tier: string optional
      +is_admin: boolean optional
    }

    class AdminUserListResponse {
      +users: UserResponse array
      +total: number
    }

    class AdminUserStatsResponse {
      +uploadTotals
      +storageTotals
      +activityTotals
    }

    SessionResponse --> UserResponse : contains
    AdminUserListResponse --> UserResponse : contains
```

## File And Access Models

```mermaid
classDiagram
    direction LR

    class ScanStatus {
      <<enumeration>>
      queued
      scanning
      clean
      infected
      failed
    }

    class FileUploadResponse {
      +id: number
      +original_filename: string
      +file_size_bytes: number
      +download_url: string
      +scan_status: ScanStatus
      +expires_at: string
    }

    class FileListResponse {
      +files: FileUploadResponse array
    }

    class MultiFileUploadResponse {
      +files: FileUploadResponse array
      +upload_group: string
      +total_size_bytes: number
    }

    class UploadGroupInfoResponse {
      +files: FileUploadResponse array
      +upload_group: string
      +total_size_bytes: number
      +file_count: number
      +will_zip: boolean
    }

    class PasswordInfo {
      +id: number
      +label: string
    }

    class EmailRecipientInfo {
      +id: number
      +email: string
      +notified: boolean
    }

    class PasswordEntry {
      +label: string
      +password: string
    }

    class AccessEditRequest {
      +publicFlagChanges
      +passwordChanges
      +emailRecipientChanges
    }

    class AccessInfoResponse {
      +is_public: boolean
      +passwords: PasswordInfo array
      +emails: EmailRecipientInfo array
      +show_email_stats: boolean
    }

    FileUploadResponse --> ScanStatus : scan state
    FileListResponse --> FileUploadResponse : contains
    MultiFileUploadResponse --> FileUploadResponse : contains
    UploadGroupInfoResponse --> FileUploadResponse : contains
    AccessInfoResponse --> PasswordInfo : contains
    AccessInfoResponse --> EmailRecipientInfo : contains
    AccessEditRequest --> PasswordEntry : adds
```

## Limits, Mutations, And Stats

```mermaid
classDiagram
    direction LR

    class QuotaResponse {
      +max_file_size_mb: number
      +max_files_per_upload: number
      +weekly_uploads_limit: number
      +weekly_uploads_used: number
      +weekly_uploads_remaining: number
    }

    class LimitsResponse {
      +max_file_size_mb: number
      +max_files_per_upload: number
      +weekly_uploads_limit: number
    }

    class FileEditRequest {
      +filenameMessageUpdates
      +expiryDownloadUpdates
    }

    class GroupRefreshRequest {
      +expiry_hours: number optional
      +max_downloads: number optional
      +title: string optional
      +description: string optional
    }

    class GroupEditRequest {
      +expiry_hours: number optional
      +max_downloads: number optional
      +title: string optional
      +description: string optional
    }

    class SubscriptionResponse {
      +plan: string
      +is_active: boolean
      +started_at: string optional
    }

    class DownloadStatEntry {
      +access_type: string
      +identifier: string optional
      +download_count: number
      +last_download: string optional
    }

    class DownloadStatsResponse {
      +stats: DownloadStatEntry array
      +total_downloads: number
    }

    class RecipientDownloadEntry {
      +email: string
      +download_count: number
    }

    class RecipientStatsResponse {
      +downloads: RecipientDownloadEntry array
      +total_downloads: number
    }

    DownloadStatsResponse --> DownloadStatEntry : contains
    RecipientStatsResponse --> RecipientDownloadEntry : contains
```

---

TypeScript models generated from the backend OpenAPI contract.