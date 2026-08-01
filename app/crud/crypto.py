"""
CRUD operations for Cryptocurrency and PriceHistoryEntry models.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Cryptocurrency, PriceHistoryEntry


def get_all_cryptocurrencies(
    db: Session, skip: int = 0, limit: int = 100
) -> list[Cryptocurrency]:
    return (
        db.query(Cryptocurrency)
        .order_by(Cryptocurrency.market_cap.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_cryptocurrency_by_id(db: Session, crypto_id: int) -> Cryptocurrency | None:
    return db.query(Cryptocurrency).filter(Cryptocurrency.id == crypto_id).first()


def get_cryptocurrency_by_external_id(
    db: Session, external_provider_id: str
) -> Cryptocurrency | None:
    return (
        db.query(Cryptocurrency)
        .filter(Cryptocurrency.external_provider_id == external_provider_id)
        .first()
    )


def upsert_cryptocurrency(db: Session, data: dict) -> tuple[Cryptocurrency, bool]:
    """
    Create a cryptocurrency row if it doesn't exist yet, otherwise update it
    with fresh data from the external provider.

    Returns a tuple of (record, was_created).
    """
    existing = get_cryptocurrency_by_external_id(db, data["external_provider_id"])
    if existing:
        existing.name = data["name"]
        existing.symbol = data["symbol"]
        existing.current_price = data.get("current_price")
        existing.market_cap = data.get("market_cap")
        existing.price_change_percentage_24h = data.get(
            "price_change_percentage_24h"
        )
        existing.image_url = data.get("image_url")
        existing.last_updated_at = datetime.utcnow()
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing, False

    new_record = Cryptocurrency(
        name=data["name"],
        symbol=data["symbol"],
        external_provider_id=data["external_provider_id"],
        current_price=data.get("current_price"),
        market_cap=data.get("market_cap"),
        price_change_percentage_24h=data.get("price_change_percentage_24h"),
        image_url=data.get("image_url"),
        last_updated_at=datetime.utcnow(),
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record, True


def add_price_history_points(
    db: Session, cryptocurrency_id: int, points: list[tuple[datetime, float]]
) -> int:
    """
    Store price history points, skipping ones that already exist
    (same cryptocurrency + timestamp).
    """
    existing_timestamps = {
        ts
        for (ts,) in db.query(PriceHistoryEntry.timestamp)
        .filter(PriceHistoryEntry.cryptocurrency_id == cryptocurrency_id)
        .all()
    }

    added = 0
    for timestamp, price in points:
        if timestamp in existing_timestamps:
            continue
        db.add(
            PriceHistoryEntry(
                cryptocurrency_id=cryptocurrency_id,
                price=price,
                timestamp=timestamp,
            )
        )
        added += 1

    if added:
        db.commit()
    return added


def get_price_history(
    db: Session, cryptocurrency_id: int
) -> list[PriceHistoryEntry]:
    return (
        db.query(PriceHistoryEntry)
        .filter(PriceHistoryEntry.cryptocurrency_id == cryptocurrency_id)
        .order_by(PriceHistoryEntry.timestamp.asc())
        .all()
    )
