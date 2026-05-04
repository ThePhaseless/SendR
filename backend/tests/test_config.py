from config import Settings


def test_default_allowed_origins_is_empty():
    settings = Settings()

    assert settings.ALLOWED_ORIGINS == []


def test_allowed_origins_accept_comma_separated_env_values():
    settings = Settings(
        ALLOWED_ORIGINS="https://sendr.up.railway.app, https://app.example.com"
    )

    assert settings.ALLOWED_ORIGINS == [
        "https://sendr.up.railway.app",
        "https://app.example.com",
    ]
