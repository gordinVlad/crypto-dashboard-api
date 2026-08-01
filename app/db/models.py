"""
SQLAlchemy ORM models.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # The id used by the external provider (e.g. CoinGecko's "bitcoin")
    external_provider_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_percentage_24h: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    price_history: Mapped[list["PriceHistoryEntry"]] = relationship(
        back_populates="cryptocurrency", cascade="all, delete-orphan"
    )
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="cryptocurrency", cascade="all, delete-orphan"
    )


class PriceHistoryEntry(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cryptocurrency_id: Mapped[int] = mapped_column(
        ForeignKey("cryptocurrencies.id"), nullable=False, index=True
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    cryptocurrency: Mapped["Cryptocurrency"] = relationship(
        back_populates="price_history"
    )

    __table_args__ = (
        UniqueConstraint(
            "cryptocurrency_id", "timestamp", name="uq_coin_history_timestamp"
        ),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    cryptocurrency_id: Mapped[int] = mapped_column(
        ForeignKey("cryptocurrencies.id"), nullable=False, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="watchlist_items")
    cryptocurrency: Mapped["Cryptocurrency"] = relationship(
        back_populates="watchlist_items"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "cryptocurrency_id", name="uq_user_coin_watchlist"),
    )
