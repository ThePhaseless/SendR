# SendR Workflow Diagrams

The workflows are split into focused diagrams so each one stays readable in a normal documentation viewport.

## Authentication

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as Backend API
    participant Mail as Email
    participant DB as Database

    B->>API: Request login code
    API->>DB: Store expiring code
    API->>Mail: Send verification email
    Mail-->>API: Accepted
    API-->>B: Code requested
    B->>API: Submit code
    API->>DB: Verify code and user
    API-->>B: Set session and CSRF cookies
```

## Upload

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as Backend API
    participant Store as Storage
    participant Q as Scan Queue

    B->>API: Request ALTCHA challenge
    API-->>B: Challenge
    B->>API: Upload files and settings
    API->>API: Check session, CSRF, quota, limits
    API->>Store: Save payload or quarantine copy
    API->>Q: Queue scan when enabled
    API-->>B: Transfer metadata and links
```

## Download

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as Backend API
    participant DB as Database
    participant Store as Storage

    B->>API: Open download link
    API->>DB: Load file or group
    API->>API: Check expiry and access rules
    alt Access allowed
        API->>Store: Read clean payload
        API->>DB: Record download
        API-->>B: File or archive stream
    else Access denied
        API-->>B: Structured error
    end
```

## Owner Management

```mermaid
sequenceDiagram
    participant O as Owner
    participant UI as Dashboard
    participant API as Backend API
    participant DB as Database

    O->>UI: Open dashboard
    UI->>API: List owned transfers
    API->>DB: Query files and groups
    API-->>UI: Upload history
    O->>UI: Edit access or expiry
    UI->>API: Save group settings
    API->>DB: Update metadata
    API-->>UI: Updated transfer
```

## Admin

```mermaid
sequenceDiagram
    participant A as Admin
    participant UI as Admin UI
    participant API as Backend API
    participant DB as Database

    A->>UI: Search users
    UI->>API: List users
    API->>DB: Query users and totals
    API-->>UI: Page of users
    A->>UI: Change tier or remove data
    UI->>API: Admin mutation
    API->>DB: Apply change
    API-->>UI: Result
```
