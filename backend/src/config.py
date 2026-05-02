import json
import logging
import secrets
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


def _generate_hmac_key() -> str:
    return secrets.token_hex(32)


def _default_allowed_origins() -> list[str]:
    return []


class Settings(BaseSettings):
    ENVIRONMENT: str = "local"
    DATABASE_URL: str = "sqlite+aiosqlite:///./sendr.db"
    SECRET_KEY: str = "change-me-in-production"
    UPLOAD_DIR: str = "./uploads"
    # CORS
    ALLOWED_ORIGINS: list[str] = Field(default_factory=_default_allowed_origins)
    # Email settings
    SMTP_HOST: str = ""
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
    # Weekly upload size quotas in MB (0 = unlimited)
    TEMPORARY_MAX_WEEKLY_UPLOAD_SIZE_MB: int = 0
    FREE_MAX_WEEKLY_UPLOAD_SIZE_MB: int = 0
    PREMIUM_MAX_WEEKLY_UPLOAD_SIZE_MB: int = 51200  # 50 GB
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
    # Passwords per upload (0 = unlimited)
    TEMPORARY_MAX_PASSWORDS_PER_UPLOAD: int = 1
    FREE_MAX_PASSWORDS_PER_UPLOAD: int = 3
    PREMIUM_MAX_PASSWORDS_PER_UPLOAD: int = 0
    # Email invites per upload (0 = unlimited for premium, disabled for temp)
    TEMPORARY_MAX_EMAILS_PER_UPLOAD: int = 0  # disabled
    FREE_MAX_EMAILS_PER_UPLOAD: int = 5
    PREMIUM_MAX_EMAILS_PER_UPLOAD: int = 0  # unlimited
    # File expiration (days) - default for backwards compatibility
    FILE_EXPIRY_DAYS: int = 7
    FILE_GRACE_PERIOD_DAYS: int = 7
    PREMIUM_REFRESH_GRACE_DAYS: int = 14
    # Token expiry
    TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 10
    # Rate limiting
    AUTH_RATE_LIMIT_PER_MINUTE: int = 5
    # Altcha proof-of-work CAPTCHA
    ALTCHA_HMAC_KEY: str = Field(default_factory=_generate_hmac_key)
    ALTCHA_MAX_NUMBER: int = 100000
    ALTCHA_EXPIRE_MINUTES: int = 5
    # Group download zip threshold (file count above which will_zip is true)
    GROUP_ZIP_THRESHOLD: int = 3
    # Optional ClamAV upload scanning
    VIRUS_SCANNING_ENABLED: bool = False
    CLAMAV_HOST: str = "127.0.0.1"
    CLAMAV_PORT: int = 3310
    CLAMAV_UNIX_SOCKET: str = "/var/run/clamav/clamd.ctl"

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
    def is_local(self) -> bool:
        return self.ENVIRONMENT.lower() == "local"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST)

    @model_validator(mode="after")
    def validate_smtp_for_production(self) -> Settings:
        if self.ENVIRONMENT.lower() == "production" and not self.smtp_configured:
            raise ValueError("SENDR_SMTP_HOST must be set when SENDR_ENVIRONMENT is 'production'")
        return self


settings = Settings()
logger = logging.getLogger(__name__)
logger.info(f"Configuration loaded: ENVIRONMENT={settings.ENVIRONMENT}")
