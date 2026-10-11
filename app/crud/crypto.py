"""
CRUD operations for Cryptocurrency and PriceHistoryEntry models.
"""

from datetime import datetime

from sqlalchemy import func
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


def upsert_cryptocurrencies(db: Session, rows: list[dict]) -> tuple[int, int]:
    """
    Upsert multiple cryptocurrency rows in one transaction.

    Returns a tuple of (created_count, updated_count). Any failure rolls back
    the entire batch.
    """
    if not rows:
        return 0, 0

    try:
        external_ids = {row["external_provider_id"] for row in rows}
        existing_records = (
            db.query(Cryptocurrency)
            .filter(Cryptocurrency.external_provider_id.in_(external_ids))
            .all()
        )
        records_by_external_id = {
            record.external_provider_id: record for record in existing_records
        }

        created_count = 0
        updated_count = 0
        now = datetime.utcnow()
        for data in rows:
            record = records_by_external_id.get(data["external_provider_id"])
            if record is None:
                record = Cryptocurrency(
                    external_provider_id=data["external_provider_id"],
                    name=data["name"],
                    symbol=data["symbol"],
                )
                records_by_external_id[record.external_provider_id] = record
                db.add(record)
                created_count += 1
            else:
                updated_count += 1

            record.name = data["name"]
            record.symbol = data["symbol"]
            record.current_price = data.get("current_price")
            record.market_cap = data.get("market_cap")
            record.price_change_percentage_24h = data.get(
                "price_change_percentage_24h"
            )
            record.image_url = data.get("image_url")
            record.last_updated_at = now

        db.commit()
        return created_count, updated_count
    except Exception:
        db.rollback()
        raise


def add_price_history_points(
    db: Session, cryptocurrency_id: int, points: list[tuple[datetime, float]]
) -> int:
    """
    Store price history points, skipping ones that already exist
    (same cryptocurrency + timestamp).
    """
    if not points:
        return 0

    try:
        timestamps = {timestamp for timestamp, _ in points}
        existing_timestamps = {
            timestamp
            for (timestamp,) in db.query(PriceHistoryEntry.timestamp)
            .filter(
                PriceHistoryEntry.cryptocurrency_id == cryptocurrency_id,
                PriceHistoryEntry.timestamp.in_(timestamps),
            )
            .all()
        }

        new_entries = []
        for timestamp, price in points:
            if timestamp in existing_timestamps:
                continue
            existing_timestamps.add(timestamp)
            new_entries.append(
                PriceHistoryEntry(
                    cryptocurrency_id=cryptocurrency_id,
                    price=price,
                    timestamp=timestamp,
                )
            )

        if not new_entries:
            return 0
        db.add_all(new_entries)
        db.commit()
        return len(new_entries)
    except Exception:
        db.rollback()
        raise


def get_price_history(
    db: Session,
    cryptocurrency_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[PriceHistoryEntry]:
    query = db.query(PriceHistoryEntry).filter(
        PriceHistoryEntry.cryptocurrency_id == cryptocurrency_id
    )
    if start_time is not None:
        query = query.filter(PriceHistoryEntry.timestamp >= start_time)
    if end_time is not None:
        query = query.filter(PriceHistoryEntry.timestamp <= end_time)
    return query.order_by(PriceHistoryEntry.timestamp.asc()).all()


def get_price_history_bounds(
    db: Session, cryptocurrency_id: int
) -> tuple[datetime, datetime] | None:
    start_time, end_time = (
        db.query(
            func.min(PriceHistoryEntry.timestamp),
            func.max(PriceHistoryEntry.timestamp),
        )
        .filter(PriceHistoryEntry.cryptocurrency_id == cryptocurrency_id)
        .one()
    )
    if start_time is None or end_time is None:
        return None
    return start_time, end_time
