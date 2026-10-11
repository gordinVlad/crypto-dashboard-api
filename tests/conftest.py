"""
Shared pytest fixtures: an isolated in-memory-like SQLite test database and
a FastAPI TestClient wired to use it instead of the real database file.
"""

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import get_db
from app.main import app

TEST_INTERNAL_API_TOKEN = "test-internal-token-0123456789abcdef"


@pytest.fixture()
def migrated_test_database(tmp_path):
    database_url = URL.create(
        "sqlite", database=str(tmp_path / "test_database.db")
    ).render_as_string(hide_password=False)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    alembic_config = Config("alembic.ini")
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    yield engine
    engine.dispose()


@pytest.fixture()
def client(migrated_test_database):
    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=migrated_test_database
    )

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def internal_api_headers(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", TEST_INTERNAL_API_TOKEN)
    return {"X-Internal-Token": TEST_INTERNAL_API_TOKEN}
