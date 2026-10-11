"""
Watchlist routes: add, list, and remove cryptocurrencies from the
authenticated user's personal watchlist.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.crud.crypto import (
    get_cryptocurrency_by_external_id,
    get_cryptocurrency_by_id,
)
from app.crud.watchlist import (
    add_to_watchlist,
    get_watchlist_for_user,
    get_watchlist_item,
    get_watchlist_item_for_user,
    remove_from_watchlist,
)
from app.db.database import get_db
from app.db.models import User
from app.schemas.crypto import CryptocurrencyOut
from app.schemas.watchlist import WatchlistAddRequest, WatchlistItemOut

logger = get_logger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemOut])
def get_my_watchlist(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Retrieve the authenticated user's watchlist."""
    items = get_watchlist_for_user(db, current_user.id)
    result = []
    for item in items:
        crypto_out = CryptocurrencyOut.model_validate(item.cryptocurrency)
        crypto_out.is_in_watchlist = True
        result.append(
            WatchlistItemOut(
                id=item.id, added_at=item.added_at, cryptocurrency=crypto_out
            )
        )
    return result


@router.post("", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
def add_watchlist_item(
    payload: WatchlistAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a cryptocurrency to the authenticated user's watchlist.

    Accepts either the internal `cryptocurrency_id` or the
    `external_provider_id` (e.g. "bitcoin") — at least one is required.
    """
    if payload.cryptocurrency_id is None and payload.external_provider_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either cryptocurrency_id or external_provider_id",
        )

    coin = None
    if payload.cryptocurrency_id is not None:
        coin = get_cryptocurrency_by_id(db, payload.cryptocurrency_id)
    elif payload.external_provider_id is not None:
        coin = get_cryptocurrency_by_external_id(db, payload.external_provider_id)

    if not coin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cryptocurrency not found. Try refreshing coin data first "
            "via POST /api/cryptocurrencies/refresh.",
        )

    existing = get_watchlist_item(db, current_user.id, coin.id)
    if existing:
        logger.info(
            "watchlist add attempted for existing item",
            extra={"user_id": current_user.id, "crypto_id": coin.id},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This cryptocurrency is already in your watchlist",
        )

    item = add_to_watchlist(db, current_user.id, coin.id)
    logger.info(
        "watchlist item added",
        extra={"user_id": current_user.id, "crypto_id": coin.id, "symbol": coin.symbol},
    )
    crypto_out = CryptocurrencyOut.model_validate(coin)
    crypto_out.is_in_watchlist = True
    return WatchlistItemOut(id=item.id, added_at=item.added_at, cryptocurrency=crypto_out)


@router.delete("/{watchlist_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_watchlist_item(
    watchlist_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an item from the authenticated user's watchlist."""
    item = get_watchlist_item_for_user(db, watchlist_item_id, current_user.id)
    if not item:
        logger.info(
            "watchlist remove attempted for missing item",
            extra={"user_id": current_user.id, "watchlist_item_id": watchlist_item_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist item not found"
        )
    remove_from_watchlist(db, item)
    logger.info(
        "watchlist item removed",
        extra={
            "user_id": current_user.id,
            "watchlist_item_id": watchlist_item_id,
            "crypto_id": item.cryptocurrency_id,
        },
    )
    return None
