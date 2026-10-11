"""
CRUD operations for the user's watchlist.
"""

from sqlalchemy.orm import Session, joinedload

from app.db.models import WatchlistItem


def get_watchlist_for_user(db: Session, user_id: int) -> list[WatchlistItem]:
    return (
        db.query(WatchlistItem)
        .options(joinedload(WatchlistItem.cryptocurrency))
        .filter(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )


def get_watchlist_item(
    db: Session, user_id: int, cryptocurrency_id: int
) -> WatchlistItem | None:
    return (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == user_id,
            WatchlistItem.cryptocurrency_id == cryptocurrency_id,
        )
        .first()
    )


def get_watchlist_item_for_user(
    db: Session, watchlist_item_id: int, user_id: int
) -> WatchlistItem | None:
    return (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.id == watchlist_item_id,
            WatchlistItem.user_id == user_id,
        )
        .first()
    )


def get_watchlist_crypto_ids(
    db: Session, user_id: int, cryptocurrency_ids: list[int] | None = None
) -> set[int]:
    if cryptocurrency_ids is not None and not cryptocurrency_ids:
        return set()

    query = db.query(WatchlistItem.cryptocurrency_id).filter(
        WatchlistItem.user_id == user_id
    )
    if cryptocurrency_ids is not None:
        query = query.filter(WatchlistItem.cryptocurrency_id.in_(cryptocurrency_ids))
    rows = query.all()
    return {row[0] for row in rows}


def add_to_watchlist(
    db: Session, user_id: int, cryptocurrency_id: int
) -> WatchlistItem:
    item = WatchlistItem(user_id=user_id, cryptocurrency_id=cryptocurrency_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def remove_from_watchlist(db: Session, watchlist_item: WatchlistItem) -> None:
    db.delete(watchlist_item)
    db.commit()
