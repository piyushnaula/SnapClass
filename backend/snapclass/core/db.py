"""Database engine and session helper."""

from collections.abc import Iterator

from sqlmodel import Session, create_engine

from snapclass.core.config import settings

# pool_pre_ping checks a connection before using it, so a DB restart does not
# leave the API with broken connections.
engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    with Session(engine) as session:
        yield session
