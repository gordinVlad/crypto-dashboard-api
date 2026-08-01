"""
Application configuration.

All configuration values are read from environment variables so that
secrets (JWT secret key, etc.) are never hard-coded in the source code.
A `.env` file can be used locally (see `.env.example`); in production
these variables should be set directly in the hosting environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # External provider (CoinGecko)
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"
    COINGECKO_REQUEST_TIMEOUT_SECONDS: int = 15

    # How many coins to fetch/track when refreshing data from the provider
    DEFAULT_COINS_LIMIT: int = 50

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
