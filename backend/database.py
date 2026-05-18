from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
SessionLocal = None  # populated by init_db() / _ensure_engine()


def _ensure_engine():
    global _engine, SessionLocal
    if _engine is not None:
        return _engine
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    _engine = create_engine(settings.database_url, connect_args=connect_args, echo=settings.debug)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def init_db() -> None:
    from backend import models  # noqa: F401 — register models
    engine = _ensure_engine()
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    _ensure_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Module-level `engine` attribute for code that referenced it directly
def __getattr__(name):
    if name == "engine":
        return _ensure_engine()
    raise AttributeError(name)
