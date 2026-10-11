import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "secret_key",
    [
        "",
        "   ",
        "change-this-secret-in-production",
        "CHANGE-THIS-SECRET-IN-PRODUCTION",
        "changeme",
        "password",
        "secret123",
        "please-change-this-secret-before-production",
        "A" * 32,
        "abcdefghijklmnopqrstuvwxyz0123456789",
        "qwertyuiopasdfghjklzxcvbnm!@#$%^&*()_+",
        "your-secret-key-here",
    ],
)
def test_production_rejects_missing_or_placeholder_secret_keys(secret_key):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY=secret_key,
        )


def test_production_rejects_default_secret_when_unset():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None, ENVIRONMENT="production")


def test_production_accepts_configured_secret_key():
    secret_key = "M5oXf8Q2vN6kL1pR9tY3wA7cD4gH0jZ6bE2sF8uK5nQ"
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY=secret_key,
    )

    assert settings.SECRET_KEY == secret_key


def test_cors_origins_are_normalized():
    settings = Settings(
        _env_file=None,
        CORS_ORIGINS=[" https://dashboard.example.com "],
    )

    assert settings.CORS_ORIGINS == ["https://dashboard.example.com"]


@pytest.mark.parametrize("origins", [["*"], [""], ["   "]])
def test_cors_rejects_wildcard_or_empty_origins(origins):
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(_env_file=None, CORS_ORIGINS=origins)
