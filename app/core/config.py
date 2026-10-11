"""
Application configuration.

All configuration values are read from environment variables so that
secrets (JWT secret key, etc.) are never hard-coded in the source code.
A `.env` file can be used locally (see `.env.example`); in production
these variables should be set directly in the hosting environment.
"""

from collections import Counter
from math import log2

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_INSECURE_SECRET_KEYS = {
    "change-this-secret-in-production",
    "changeme",
    "default",
    "development",
    "secret",
    "secret-key",
    "your-secret-key",
    "your-secret-key-here",
}

_ORDERED_SECRET_SEQUENCES = tuple(
    sequence
    for alphabet in ("abcdefghijklmnopqrstuvwxyz", "0123456789")
    for start in range(len(alphabet) - 7)
    for sequence in (alphabet[start : start + 8], alphabet[start : start + 8][::-1])
) + tuple(
    sequence
    for row in ("qwertyuiop", "asdfghjkl", "zxcvbnm")
    for sequence in (row, row[::-1])
)
_MIN_SECRET_ENTROPY_PER_CHARACTER = 4.5


def _has_predictable_sequence(value: str) -> bool:
    normalized_value = value.casefold()
    return any(sequence in normalized_value for sequence in _ORDERED_SECRET_SEQUENCES)


class Settings(BaseSettings):
    # General
    APP_NAME: str = "Crypto Dashboard API"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./crypto_dashboard.db"

    # JWT / Auth
    SECRET_KEY: str = "change-this-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Browser access; configure as a JSON array, e.g. ["https://example.com"].
    CORS_ORIGINS: list[str] = []

    # External provider (CoinGecko)
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"
    COINGECKO_REQUEST_TIMEOUT_SECONDS: int = 15

    # How many coins to fetch/track when refreshing data from the provider
    DEFAULT_COINS_LIMIT: int = 50

    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    LOG_FORMAT: str = "json"  # "json" | "text" (use "text" for local dev)
    LOG_DIR: str = "logs"  # directory for on-disk log files (created if missing)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_production_secret_key(
        cls, value: str, info: ValidationInfo
    ) -> str:
        if info.data.get("ENVIRONMENT", "").strip().casefold() == "production":
            normalized_value = value.strip()
            character_frequencies = Counter(normalized_value)
            estimated_entropy = -sum(
                (count / len(normalized_value)) * log2(count / len(normalized_value))
                for count in character_frequencies.values()
            ) if normalized_value else 0
            if (
                len(normalized_value) < 32
                or normalized_value.casefold() in _INSECURE_SECRET_KEYS
                or estimated_entropy < _MIN_SECRET_ENTROPY_PER_CHARACTER
                or _has_predictable_sequence(normalized_value)
            ):
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters, high-entropy, "
                    "and not a placeholder in production"
                )
            return normalized_value
        return value

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized_origins = [origin.strip() for origin in origins]
        if any(not origin or origin == "*" for origin in normalized_origins):
            raise ValueError("CORS_ORIGINS must contain explicit, non-empty origins")
        return normalized_origins

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
