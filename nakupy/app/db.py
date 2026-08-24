"""Pripojeni k SQLite databazi."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def init_engine(settings: Settings) -> Engine:
    """Vytvori engine, zapne WAL a zalozi schema."""
    global _engine, _SessionFactory

    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - trivialni
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    Base.metadata.create_all(engine)
    _engine = engine
    _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return engine


def get_session_factory() -> sessionmaker[Session]:
    if _SessionFactory is None:
        raise RuntimeError("Databaze neni inicializovana - zavolej init_engine().")
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session s automatickym commitem / rollbackem."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
