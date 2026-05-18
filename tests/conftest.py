"""Pytest fixtures: isolated SQLite DB + dummy API keys for every test session."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    audio_path = tmp_path / "audio"
    audio_path.mkdir(exist_ok=True)
    monkeypatch.setenv("AUDIO_UPLOAD_DIR", str(audio_path))
    monkeypatch.setenv("DEBUG", "false")

    # reset the cached settings & db engine so the new env vars take effect
    import backend.config
    backend.config._settings = None
    import backend.database as dbmod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    settings = backend.config.get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    dbmod.engine = create_engine(settings.database_url, connect_args=connect_args)
    dbmod.SessionLocal = sessionmaker(bind=dbmod.engine, autoflush=False, autocommit=False)
    dbmod.init_db()
    yield


@pytest.fixture
def db_session():
    from backend.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
