"""
Shared pytest fixtures: an isolated in-memory-like SQLite test database and
a FastAPI TestClient wired to use it instead of the real database file.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_crypto_dashboard.db"
TEST_INTERNAL_API_TOKEN = "test-internal-token-0123456789abcdef"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def internal_api_headers(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", TEST_INTERNAL_API_TOKEN)
    return {"X-Internal-Token": TEST_INTERNAL_API_TOKEN}
