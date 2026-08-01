"""
Pydantic schemas for cryptocurrency data and price history.
"""

from datetime import datetime

from pydantic import BaseModel


class CryptocurrencyOut(BaseModel):
    id: int
    name: str
    symbol: str
    external_provider_id: str
    current_price: float | None = None
    market_cap: float | None = None
    price_change_percentage_24h: float | None = None
    image_url: str | None = None
    last_updated_at: datetime | None = None
    is_in_watchlist: bool = False

    class Config:
        from_attributes = True


class CryptocurrencyDetail(CryptocurrencyOut):
    """Same fields as the list view for now; kept separate so the detail
    endpoint can be extended with extra fields later without breaking the
    list endpoint's response shape."""


class PriceHistoryPoint(BaseModel):
    price: float
    timestamp: datetime

    class Config:
        from_attributes = True


class PriceHistoryOut(BaseModel):
    cryptocurrency_id: int
    symbol: str
    points: list[PriceHistoryPoint]


class RefreshResult(BaseModel):
    updated_count: int
    created_count: int
    message: str
