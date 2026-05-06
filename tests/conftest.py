"""Shared pytest fixtures for WatchMatch backend integration tests."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import app.db as db_module
from app.db import get_session
from main import app


@pytest.fixture(name="engine", scope="function")
def engine_fixture():
    """In-memory SQLite engine — isolated per test function."""
    _engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(_engine)
    yield _engine
    SQLModel.metadata.drop_all(_engine)


@pytest.fixture(name="client", scope="function")
def client_fixture(engine):
    # Redirect the global engine so the lifespan (seed_movies, migrations)
    # operates on the test in-memory DB instead of watchmatch.db.
    original_engine = db_module.engine
    db_module.engine = engine

    def _get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
    db_module.engine = original_engine  # restore for other test processes


# ---------- helpers ----------

def register(client: TestClient, name="Alice", email="alice@test.com", password="secret123"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
