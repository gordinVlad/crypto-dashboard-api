"""
Cryptocurrency routes: listing, details, refresh from external provider,
and historical price data.
"""

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    require_internal_api_token,
)
from app.core.logging import get_logger
from app.crud.crypto import (
    add_price_history_points,
    get_all_cryptocurrencies,
    get_cryptocurrency_by_id,
    get_price_history,
    get_price_history_bounds,
    upsert_cryptocurrency,
)
from app.crud.watchlist import get_watchlist_crypto_ids
from app.db.database import get_db
from app.db.models import User
from app.schemas.crypto import (
    CryptocurrencyDetail,
    CryptocurrencyOut,
    PriceHistoryOut,
    PriceHistoryPoint,
    RefreshResult,
)
from app.services.coingecko_client import CoinGeckoError, coingecko_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cryptocurrencies", tags=["cryptocurrencies"])


@router.get("", response_model=list[CryptocurrencyOut])
def list_cryptocurrencies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    Get the dashboard-style list of current cryptocurrency rates.
    Data comes from the local database; call `POST /refresh` first (or
    periodically) to sync it with the external provider.

    If an authenticated user's token is provided, each coin is flagged
    with `is_in_watchlist` for that user.
    """
    coins = get_all_cryptocurrencies(db, skip=skip, limit=limit)
    watchlist_ids = (
        get_watchlist_crypto_ids(db, current_user.id) if current_user else set()
    )

    result = []
    for coin in coins:
        item = CryptocurrencyOut.model_validate(coin)
        item.is_in_watchlist = coin.id in watchlist_ids
        result.append(item)
    return result


@router.get("/{crypto_id}", response_model=CryptocurrencyDetail)
def get_cryptocurrency(
    crypto_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Get detailed information for a single cryptocurrency by internal id."""
    coin = get_cryptocurrency_by_id(db, crypto_id)
    if not coin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cryptocurrency not found"
        )
    item = CryptocurrencyDetail.model_validate(coin)
    if current_user:
        item.is_in_watchlist = coin.id in get_watchlist_crypto_ids(db, current_user.id)
    return item


@router.get("/{crypto_id}/history", response_model=PriceHistoryOut)
def get_cryptocurrency_history(
    crypto_id: int,
    days: int = Query(7, ge=1, le=365, description="Number of days of history"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Get historical price data for a cryptocurrency.

    Return only points in the requested date range. Refetch when the local
    cache does not cover that range, then merge the new points into the cache.
    """
    coin = get_cryptocurrency_by_id(db, crypto_id)
    if not coin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cryptocurrency not found"
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_time = now - timedelta(days=days)
    coverage_tolerance = (
        timedelta(minutes=5)
        if days <= 1
        else timedelta(hours=1)
        if days <= 90
        else timedelta(days=1)
    )
    cache_bounds = get_price_history_bounds(db, crypto_id)
    cache_covers_requested_range = (
        cache_bounds is not None
        and cache_bounds[0] <= start_time + coverage_tolerance
        and cache_bounds[1] >= now - coverage_tolerance
    )

    if cache_covers_requested_range:
        logger.debug(
            "price history cache hit",
            extra={"crypto_id": crypto_id, "days": days},
        )
    else:
        logger.info(
            "price history cache incomplete, fetching from coingecko",
            extra={
                "crypto_id": crypto_id,
                "external_provider_id": coin.external_provider_id,
                "days": days,
                "cache_bounds": cache_bounds,
            },
        )
        try:
            points = coingecko_client.get_market_chart(
                coin.external_provider_id, days=days
            )
        except CoinGeckoError as exc:
            logger.warning(
                "failed to fetch price history from coingecko",
                extra={"crypto_id": crypto_id, "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch history from external provider: {exc}",
            ) from exc

        points_added = add_price_history_points(db, crypto_id, points)
        logger.info(
            "price history fetched and persisted",
            extra={"crypto_id": crypto_id, "points_added": points_added},
        )

    existing_history = get_price_history(
        db, crypto_id, start_time=start_time, end_time=now
    )

    return PriceHistoryOut(
        cryptocurrency_id=coin.id,
        symbol=coin.symbol,
        points=[
            PriceHistoryPoint(price=p.price, timestamp=p.timestamp)
            for p in existing_history
        ],
    )


@router.post("/refresh", response_model=RefreshResult)
def refresh_cryptocurrencies(
    limit: int = Query(50, ge=1, le=250),
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_api_token),
):
    """
    Refresh cryptocurrency data from the external provider (CoinGecko).

    Fetches the current top coins by market cap and upserts them into the
    local database (creating new records or updating existing ones).
    """
    start = time.perf_counter()
    try:
        markets = coingecko_client.get_markets(limit=limit)
    except CoinGeckoError as exc:
        logger.warning(
            "crypto refresh failed to fetch from coingecko",
            extra={"limit": limit, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch data from external provider: {exc}",
        ) from exc

    created_count = 0
    updated_count = 0

    for coin_data in markets:
        record_data = {
            "name": coin_data.get("name"),
            "symbol": (coin_data.get("symbol") or "").upper(),
            "external_provider_id": coin_data.get("id"),
            "current_price": coin_data.get("current_price"),
            "market_cap": coin_data.get("market_cap"),
            "price_change_percentage_24h": coin_data.get(
                "price_change_percentage_24h"
            ),
            "image_url": coin_data.get("image"),
        }
        if not record_data["external_provider_id"] or not record_data["name"]:
            continue

        _, was_created = upsert_cryptocurrency(db, record_data)
        if was_created:
            created_count += 1
        else:
            updated_count += 1

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "crypto refresh completed",
        extra={
            "created_count": created_count,
            "updated_count": updated_count,
            "duration_ms": duration_ms,
            "limit": limit,
        },
    )

    return RefreshResult(
        updated_count=updated_count,
        created_count=created_count,
        message=f"Synced {created_count + updated_count} coins from CoinGecko",
    )
