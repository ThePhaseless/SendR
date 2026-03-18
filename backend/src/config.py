import secrets

from pydantic import Field
from pydantic_settings import BaseSettings


def _generate_hmac_key() -> str:
    return secrets.token_hex(32)


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./sendr.db"
    SECRET_KEY: str = "change-me-in-production"
    UPLOAD_DIR: str = "./uploads"
    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:4200"]
    # Email settings
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@sendr.app"
    # File limits
    ANON_MAX_FILES_PER_WEEK: int = 3
    ANON_MAX_FILE_SIZE_MB: int = 100
    FREE_MAX_FILES_PER_WEEK: int = 5
    FREE_MAX_FILE_SIZE_MB: int = 1024
    PREMIUM_MAX_FILES_PER_WEEK: int = 50
    PREMIUM_MAX_FILE_SIZE_MB: int = 10240
    # Max files per single upload
    ANON_MAX_FILES_PER_UPLOAD: int = 10
    FREE_MAX_FILES_PER_UPLOAD: int = 50
    PREMIUM_MAX_FILES_PER_UPLOAD: int = 0  # 0 means unlimited
    # File expiration (days)
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

    model_config = {"env_prefix": "SENDR_"}


settings = Settings()
