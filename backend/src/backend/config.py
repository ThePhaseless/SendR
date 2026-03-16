from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./sendr.db"
    SECRET_KEY: str = "change-me-in-production"
    UPLOAD_DIR: str = "./uploads"
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
    # File expiration (days)
    FILE_EXPIRY_DAYS: int = 7
    FILE_GRACE_PERIOD_DAYS: int = 7
    # Token expiry
    TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 10

    model_config = {"env_prefix": "SENDR_"}


settings = Settings()
