"""
Thin client around the CoinGecko public API.

CoinGecko does not require an API key for its free/public endpoints, which
is why it was chosen for this project. All network calls are isolated in
this module so the rest of the application never talks to `httpx` directly.
"""

import time
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CoinGeckoError(Exception):
    """Raised when the external provider request fails or returns bad data."""


class CoinGeckoClient:
    def __init__(self) -> None:
        self.base_url = settings.COINGECKO_BASE_URL
        self.timeout = settings.COINGECKO_REQUEST_TIMEOUT_SECONDS

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self.base_url}{path}"
        logger.debug("coingecko request starting", extra={"url": url, "params": params})
        start = time.perf_counter()
        try:
            response = httpx.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "coingecko request succeeded",
                extra={"url": url, "status_code": response.status_code, "duration_ms": duration_ms},
            )
            return response.json()
        except httpx.HTTPStatusError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(
                "coingecko returned error status",
                extra={
                    "url": url,
                    "status_code": exc.response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            raise CoinGeckoError(
                f"CoinGecko returned an error status {exc.response.status_code} "
                f"for {url}"
            ) from exc
        except httpx.TimeoutException as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(
                "coingecko request timed out",
                extra={"url": url, "duration_ms": duration_ms, "error": str(exc)},
            )
            raise CoinGeckoError(
                f"Failed to reach CoinGecko at {url}: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(
                "coingecko request failed (connection error)",
                extra={"url": url, "duration_ms": duration_ms, "error": str(exc)},
            )
            raise CoinGeckoError(
                f"Failed to reach CoinGecko at {url}: {exc}"
            ) from exc

    def get_markets(self, limit: int | None = None) -> list[dict]:
        """
        Fetch current market data (price, market cap, 24h change, etc.)
        for the top coins by market cap.
        """
        limit = limit or settings.DEFAULT_COINS_LIMIT
        data = self._get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1,
                "price_change_percentage": "24h",
            },
        )
        if not isinstance(data, list):
            raise CoinGeckoError("Unexpected response shape from /coins/markets")
        return data

    def get_coin_details(self, external_provider_id: str) -> dict:
        """Fetch detailed data for a single coin by its CoinGecko id."""
        data = self._get(
            f"/coins/{external_provider_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
            },
        )
        if not isinstance(data, dict):
            raise CoinGeckoError(
                f"Unexpected response shape from /coins/{external_provider_id}"
            )
        return data

    def get_market_chart(
        self, external_provider_id: str, days: int = 7
    ) -> list[tuple[datetime, float]]:
        """
        Fetch historical prices for a coin over the last `days` days.
        Returns a list of (timestamp, price) tuples.
        """
        data = self._get(
            f"/coins/{external_provider_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
        )
        if not isinstance(data, dict) or "prices" not in data:
            raise CoinGeckoError(
                f"Unexpected response shape from market_chart for "
                f"{external_provider_id}"
            )

        points: list[tuple[datetime, float]] = []
        for timestamp_ms, price in data["prices"]:
            ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            points.append((ts, float(price)))
        return points


coingecko_client = CoinGeckoClient()
