"""
Pydantic schemas for the user's watchlist.
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.crypto import CryptocurrencyOut


class WatchlistAddRequest(BaseModel):
    # Either the internal numeric id or the external provider id can be used
    # to add a coin, whichever the client already has on hand.
    cryptocurrency_id: int | None = None
    external_provider_id: str | None = None


class WatchlistItemOut(BaseModel):
    id: int
    added_at: datetime
    cryptocurrency: CryptocurrencyOut

    class Config:
        from_attributes = True
