import json
import secrets
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


def _generate_hmac_key() -> str:
    return secrets.token_hex(32)


def _default_allowed_origins() -> list[str]:
    return []


class Settings(BaseSettings):
    ENVIRONMENT: str = "production"
    DATABASE_URL: str = "sqlite+aiosqlite:///./sendr.db"
    SECRET_KEY: str = "change-me-in-production"
    UPLOAD_DIR: str = "./uploads"
    # CORS
    ALLOWED_ORIGINS: list[str] = Field(default_factory=_default_allowed_origins)
    # Email settings
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@sendr.app"
    # File limits
    TEMPORARY_MAX_FILE_SIZE_MB: int = 100
    FREE_MAX_FILE_SIZE_MB: int = 1024
    PREMIUM_MAX_FILE_SIZE_MB: int = 10240
    # Max files per single upload
    TEMPORARY_MAX_FILES_PER_UPLOAD: int = 10
    FREE_MAX_FILES_PER_UPLOAD: int = 50
    PREMIUM_MAX_FILES_PER_UPLOAD: int = 0  # 0 means unlimited
    # Weekly upload quotas (0 = unlimited)
    TEMPORARY_MAX_WEEKLY_UPLOADS: int = 3
    FREE_MAX_WEEKLY_UPLOADS: int = 5
    PREMIUM_MAX_WEEKLY_UPLOADS: int = 0
    # Expiry options per tier (hours)
    TEMPORARY_EXPIRY_OPTIONS_HOURS: list[int] = [24, 72]  # 1d or 3d only
    FREE_MIN_EXPIRY_HOURS: int = 1
    FREE_MAX_EXPIRY_HOURS: int = 168  # 7 days
    PREMIUM_MIN_EXPIRY_HOURS: int = 1
    PREMIUM_MAX_EXPIRY_HOURS: int = 720  # 30 days
    # Max downloads per tier
    TEMPORARY_MAX_DOWNLOADS_OPTIONS: list[int] = [1, 0]  # 1 or unlimited only
    FREE_MAX_DOWNLOADS_LIMIT: int = 10
    PREMIUM_MAX_DOWNLOADS_LIMIT: int = 1000
    # Max recipient emails per transfer
    MAX_RECIPIENT_EMAILS: int = 10
    # File expiration (days) - default for backwards compatibility
    FILE_EXPIRY_DAYS: int = 7
    FILE_GRACE_PERIOD_DAYS: int = 7
    # Token expiry
    TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 10
    # Rate limiting
    AUTH_RATE_LIMIT_PER_MINUTE: int = 5
    # Altcha proof-of-work CAPTCHA
    ALTCHA_HMAC_KEY: str = Field(default_factory=_generate_hmac_key)
    ALTCHA_MAX_NUMBER: int = 100000
    ALTCHA_EXPIRE_MINUTES: int = 5
    # Dev mode
    DEV_MODE: bool = False
    # Group download zip threshold (file count above which will_zip is true)
    GROUP_ZIP_THRESHOLD: int = 3

    model_config = {"env_prefix": "SENDR_"}

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        raw_value = value.strip()
        if not raw_value:
            return []

        if raw_value.startswith("["):
            try:
                return json.loads(raw_value)
            except json.JSONDecodeError:
                pass

        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]

    @property
    def is_local_env(self) -> bool:
        return self.ENVIRONMENT.lower() == "local"


settings = Settings()
