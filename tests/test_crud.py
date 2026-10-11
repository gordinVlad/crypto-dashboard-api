import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.crud.crypto import upsert_cryptocurrencies
from app.db.models import Cryptocurrency


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
