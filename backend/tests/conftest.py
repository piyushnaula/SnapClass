"""Shared test setup.

Tests run against a REAL Postgres database (snapclass_test) and Redis db 15,
because pgvector, JSONB and row locks cannot be faked with SQLite.
Run inside Docker:  docker compose run --rm api pytest
"""

import os
import tempfile

# Point the app at the test database BEFORE importing anything from snapclass.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://snapclass:snapclass@localhost:5432/snapclass_test"
)
os.environ["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0").rsplit("/", 1)[0] + "/15"
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="snapclass-test-media-")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

if not os.environ["DATABASE_URL"].endswith("_test"):
    raise RuntimeError("Refusing to run tests against a database whose name does not end in _test")

import snapclass.core.security as security  # noqa: E402

security.BCRYPT_COST = 4  # fast hashing in tests only (production uses 12)


@pytest.fixture(scope="session")
def engine():
    from sqlmodel import SQLModel

    import snapclass.models  # noqa: F401
    from snapclass.core.db import engine

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def clean_state(request):
    """Empty every table and the Redis test db before each test."""
    if "unit" in request.node.nodeid.split("/"):
        yield  # pure unit tests need no database
        return
    engine = request.getfixturevalue("engine")
    from sqlmodel import Session, SQLModel

    from snapclass.core.redis_client import get_redis
    from snapclass.models import ConsentText

    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    get_redis().flushdb()
    with Session(engine) as db:
        db.add(ConsentText(version=1, body="Test consent text"))
        db.commit()
    yield


@pytest.fixture
def db(engine):
    from sqlmodel import Session

    with Session(engine) as session:
        yield session


@pytest.fixture
def queued(monkeypatch):
    """Replace the real queue with a list, so tests can see what was queued."""
    calls: list[tuple] = []
    monkeypatch.setattr("snapclass.services.session_service.enqueue_match", lambda sid: calls.append(("match", sid)))
    monkeypatch.setattr(
        "snapclass.services.biometric_service.enqueue_enrollment",
        lambda kind, job_id, student_id, keys: calls.append((kind, job_id, student_id, keys)),
    )
    return calls


@pytest.fixture
def client(queued):
    from fastapi.testclient import TestClient

    from snapclass.main import app

    return TestClient(app)


# ---------- helpers ----------

PASSWORD = "correct-horse-battery"


def make_user(db, role: str, email: str, roll_no: str | None = None, name: str = "Test User"):
    from snapclass.core.security import hash_password
    from snapclass.models import User

    user = User(email=email, password_hash=hash_password(PASSWORD), full_name=name, role=role, roll_no=roll_no)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email: str, password: str = PASSWORD) -> dict:
    response = client.post("/api/v1/auth/login", json={"login_id": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def tiny_jpeg() -> bytes:
    import cv2
    import numpy as np

    ok, data = cv2.imencode(".jpg", np.full((64, 64, 3), 128, dtype=np.uint8))
    assert ok
    return data.tobytes()
