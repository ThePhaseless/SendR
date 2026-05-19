# Backend Utilities & Infrastructure

The backend infrastructure diagram is split into configuration groups and runtime services to avoid one oversized settings box.

## Runtime Configuration

```mermaid
classDiagram
    direction LR

    class Settings {
      +ENVIRONMENT: str
      +DATABASE_URL: str
      +SECRET_KEY: str
      +is_local: bool
      +is_production: bool
      +smtp_configured: bool
      +validate_runtime_settings()
      +parse_string_list()
    }

    class NetworkSettings {
      +ALLOWED_ORIGINS: list
      +TRUSTED_PROXY_IPS: list
      +SESSION_COOKIE_NAME: str
      +CSRF_COOKIE_NAME: str
      +CSRF_HEADER_NAME: str
    }

    class EmailSettings {
      +SMTP_HOST: str
      +SMTP_PORT: int
      +SMTP_FROM: str
      +RESEND_API_KEY: str
    }

    class TierLimitSettings {
      +fileSizeLimits
      +filesPerUploadLimits
      +weeklyUploadLimits
      +expiryOptions
      +downloadLimits
      +accessListLimits
    }

    class SecuritySettings {
      +DEV_LOGIN_ENABLED: bool
      +AUTH_RATE_LIMIT_PER_MINUTE: int
      +DOWNLOAD_RATE_LIMIT_PER_MINUTE: int
      +altchaSettings
    }

    class StorageSettings {
      +UPLOAD_DIR: str
      +UPLOAD_QUARANTINE_DIR: str
      +spacesCredentials
      +is_s3_configured: bool
      +spaces_endpoint: str
    }

    Settings --> NetworkSettings : includes
    Settings --> EmailSettings : includes
    Settings --> TierLimitSettings : includes
    Settings --> SecuritySettings : includes
    Settings --> StorageSettings : includes

    note for Settings "Strict runtime validation with SENDR_ environment prefix"
```

## Backend Services

```mermaid
classDiagram
    direction LR

    class RateLimiter {
      -max_requests: int
      -window_seconds: int
      +check(key: str)
    }

    class SecurityUtils {
      +hash_password(password): str
      +verify_password(password, hash): bool
      +generate_token(): str
      +create_session(user_id)
      +verify_session(token)
    }

    class EmailUtils {
      +send_verification_email(email, code)
      +send_file_invite_email(...)
      +deliver_with_smtp_or_resend(...)
    }

    class DatabaseUtils {
      +get_session()
      +get_session_context()
      +init_db()
    }

    class StorageUtils {
      +save_upload(...)
      +open_payload(...)
      +delete_payload(...)
      +use_local_or_spaces()
    }

    class BackgroundTasks {
      +cleanup_expired_files(session): int
    }

    class FastAPIApp {
      +title: str
      +description: str
      +version: str
      +lifespan: callable
      +add_middleware()
      +include_router()
    }

    Settings -- RateLimiter : configures
    Settings -- EmailUtils : provides config
    Settings -- DatabaseUtils : provides connection
    Settings -- SecurityUtils : provides secrets
    Settings -- StorageUtils : selects backend

    FastAPIApp --> Settings : uses
    FastAPIApp --> RateLimiter : uses
    FastAPIApp --> DatabaseUtils : uses
    FastAPIApp --> StorageUtils : uses
    FastAPIApp --> BackgroundTasks : runs

    note for RateLimiter "Per-key throttling for auth and downloads"
    note for SecurityUtils "Password hashing, tokens, sessions, and CSRF"
    note for StorageUtils "Local disk or DigitalOcean Spaces payload access"
```

---

Backend configuration, infrastructure helpers, and application-level services.
