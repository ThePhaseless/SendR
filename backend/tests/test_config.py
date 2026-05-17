import pytest

from config import Settings


def test_default_allowed_origins_is_empty():
    settings = Settings()

    assert settings.ALLOWED_ORIGINS == []


def test_allowed_origins_accept_comma_separated_env_values():
    settings = Settings.model_validate(
        {"ALLOWED_ORIGINS": "https://sendr.up.railway.app, https://app.example.com"}
    )

    assert settings.ALLOWED_ORIGINS == [
        "https://sendr.up.railway.app",
        "https://app.example.com",
    ]


def test_dev_login_requires_explicit_opt_in():
    settings = Settings.model_validate({"ENVIRONMENT": "local"})

    assert settings.DEV_LOGIN_ENABLED is False


def test_dev_login_cannot_be_enabled_outside_local():
    with pytest.raises(ValueError, match="SENDR_DEV_LOGIN_ENABLED"):
        Settings.model_validate({"ENVIRONMENT": "test", "DEV_LOGIN_ENABLED": True})
