from config import Settings


def test_default_allowed_origins_include_production_frontend():
    settings = Settings()

    assert "https://sendr.up.railway.app" in settings.ALLOWED_ORIGINS
    assert "http://localhost:4200" in settings.ALLOWED_ORIGINS


def test_allowed_origins_accept_comma_separated_env_values():
    settings = Settings(ALLOWED_ORIGINS="https://sendr.up.railway.app, https://app.example.com")

    assert settings.ALLOWED_ORIGINS == [
        "https://sendr.up.railway.app",
        "https://app.example.com",
    ]
