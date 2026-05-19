# Backend Database Models

The database model diagrams are split by responsibility to keep relationships readable.

## Users, Auth, And Subscriptions

```mermaid
classDiagram
    direction LR

    class UserTier {
      <<enumeration>>
      temporary
      free
      premium
    }

    class SubscriptionPlan {
      <<enumeration>>
      free
      premium
    }

    class User {
      +id: int
      +email: str
      +password_hash: str optional
      +tier: UserTier
      +is_admin: bool
      +created_at: datetime
      +updated_at: datetime
    }

    class VerificationCode {
      +id: int
      +email: str
      +code: str
      +expires_at: datetime
      +used: bool
    }

    class AuthToken {
      +id: int
      +user_id: int
      +token: str
      +expires_at: datetime
      +created_at: datetime
    }

    class UserLogin {
      +id: int
      +user_id: int
      +method: str
      +logged_in_at: datetime
    }

    class Subscription {
      +id: int
      +user_id: int
      +plan: SubscriptionPlan
      +started_at: datetime
      +expires_at: datetime
      +is_active: bool
    }

    User --> UserTier : tier
    Subscription --> SubscriptionPlan : plan
    User "1" --> "many" VerificationCode : requests
    User "1" --> "many" AuthToken : sessions
    User "1" --> "many" UserLogin : audit log
    User "1" --> "many" Subscription : plans

    note for User "Account, role, tier, and optional password hash"
    note for AuthToken "Server-side session token backing HttpOnly cookies"
    note for UserLogin "Authentication history for admin review"
```

## Transfers, Access, And Audit

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

    class FileUpload {
      +id: int
      +user_id: int optional
      +original_filename: str
      +stored_filename: str
      +file_size_bytes: int
      +download_token: str
      +upload_group: str
      +scan_status: ScanStatus
      +expires_at: datetime
      +is_active: bool
    }

    class UploadGroupSettings {
      +upload_group: str
      +is_public: bool
      +show_email_stats: bool
      +title: str optional
      +description: str optional
    }

    class UploadPassword {
      +id: int
      +upload_group: str
      +label: str
      +password_hash: str
    }

    class UploadEmailRecipient {
      +id: int
      +upload_group: str
      +email: str
      +token_hash: str
      +notified: bool
    }

    class DownloadLog {
      +id: int
      +upload_group: str
      +file_upload_id: int optional
      +access_type: str
      +downloaded_at: datetime
    }

    class Transfer {
      +id: int
      +user_id: int optional
      +upload_group: str
      +message: str optional
      +notify_on_download: bool
      +created_at: datetime
      +expires_at: datetime
    }

    FileUpload --> ScanStatus : scan state
    Transfer "1" --> "many" FileUpload : contains
    UploadGroupSettings "1" --> "many" FileUpload : configures
    UploadGroupSettings "1" --> "many" UploadPassword : passwords
    UploadGroupSettings "1" --> "many" UploadEmailRecipient : recipients
    FileUpload "1" --> "many" DownloadLog : downloads
    UploadPassword "1" --> "many" DownloadLog : password access
    UploadEmailRecipient "1" --> "many" DownloadLog : email access

    note for FileUpload "One stored payload and its sharing metadata"
    note for UploadGroupSettings "Group-level public/password/email access"
    note for DownloadLog "Audit row for every successful download"
```

---

SQLModel entities for users, transfers, access controls, malware scan state, subscriptions, and download auditing.
