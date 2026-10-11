from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from app.core.config import settings


def test_initial_migration_creates_current_schema(tmp_path, monkeypatch):
    database_url = URL.create(
        "sqlite", database=str(tmp_path / "migration_test.db")
    ).render_as_string(hide_password=False)
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    alembic_config = Config("alembic.ini")

    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {
            "alembic_version",
            "cryptocurrencies",
            "price_history",
            "users",
            "watchlist_items",
        }.issubset(inspector.get_table_names())
        assert inspector.get_indexes("users") == [
            {
                "name": "ix_users_email",
                "column_names": ["email"],
                "unique": True,
                "dialect_options": {},
            },
            {
                "name": "ix_users_id",
                "column_names": ["id"],
                "unique": False,
                "dialect_options": {},
            },
        ]
    finally:
        engine.dispose()
