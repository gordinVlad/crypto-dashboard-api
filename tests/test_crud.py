import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import event
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.crud.crypto import upsert_cryptocurrencies
from app.db.models import Cryptocurrency, PriceHistoryEntry, User, WatchlistItem


def test_cryptocurrency_batch_upsert_commits_once(migrated_test_database):
    session = Session(migrated_test_database)
    commit_count = 0

    def count_commit(_session):
        nonlocal commit_count
        commit_count += 1

    event.listen(session, "after_commit", count_commit)
    try:
        created, updated = upsert_cryptocurrencies(
            session,
            [
                {
                    "external_provider_id": "bitcoin",
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "current_price": 65000.0,
                },
                {
                    "external_provider_id": "ethereum",
                    "name": "Ethereum",
                    "symbol": "ETH",
                    "current_price": 3400.0,
                },
            ],
        )

        assert (created, updated) == (2, 0)
        assert commit_count == 1

        created, updated = upsert_cryptocurrencies(
            session,
            [
                {
                    "external_provider_id": "bitcoin",
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "current_price": 66000.0,
                }
            ],
        )
        assert (created, updated) == (0, 1)
        assert commit_count == 2
    finally:
        event.remove(session, "after_commit", count_commit)
        session.close()


def test_cryptocurrency_batch_upsert_rolls_back_on_error(migrated_test_database):
    session = Session(migrated_test_database)
    try:
        with pytest.raises(KeyError):
            upsert_cryptocurrencies(
                session,
                [
                    {
                        "external_provider_id": "bitcoin",
                        "name": "Bitcoin",
                        "symbol": "BTC",
                    },
                    {
                        "external_provider_id": "invalid",
                        "symbol": "INV",
                    },
                ],
            )

        assert session.query(Cryptocurrency).count() == 0
    finally:
        session.close()


def test_model_datetimes_are_utc_aware_after_database_round_trip(
    migrated_test_database,
):
    session = Session(migrated_test_database)
    try:
        user = User(email="utc@example.com", hashed_password="hashed")
        coin = Cryptocurrency(
            name="Bitcoin",
            symbol="BTC",
            external_provider_id="bitcoin",
            last_updated_at=datetime.now(timezone.utc),
        )
        session.add_all([user, coin])
        session.flush()
        history = PriceHistoryEntry(
            cryptocurrency_id=coin.id,
            price=65000.0,
            timestamp=datetime.now(timezone(timedelta(hours=3))),
        )
        watchlist_item = WatchlistItem(user_id=user.id, cryptocurrency_id=coin.id)
        session.add_all([history, watchlist_item])
        session.commit()

        session.expire_all()
        stored_user = session.query(User).filter_by(id=user.id).one()
        stored_coin = session.query(Cryptocurrency).filter_by(id=coin.id).one()
        stored_history = (
            session.query(PriceHistoryEntry).filter_by(id=history.id).one()
        )
        stored_item = session.query(WatchlistItem).filter_by(id=watchlist_item.id).one()

        for value in (
            stored_user.created_at,
            stored_coin.last_updated_at,
            stored_history.timestamp,
            stored_item.added_at,
        ):
            assert value is not None
            assert value.tzinfo is not None
            assert value.utcoffset() == timedelta(0)

        assert stored_history.timestamp == history.timestamp.astimezone(timezone.utc)
    finally:
        session.close()


def test_datetime_columns_reject_naive_values(migrated_test_database):
    session = Session(migrated_test_database)
    try:
        session.add(
            Cryptocurrency(
                name="Bitcoin",
                symbol="BTC",
                external_provider_id="bitcoin",
                last_updated_at=datetime(2026, 1, 1),
            )
        )
        with pytest.raises(StatementError, match="timezone-aware"):
            session.commit()
        session.rollback()
    finally:
        session.close()
