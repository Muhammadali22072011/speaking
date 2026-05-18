"""Pytest fixtures: isolated SQLite DB + dummy API key for every test."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    audio_path = tmp_path / "audio"
    audio_path.mkdir(exist_ok=True)
    monkeypatch.setenv("AUDIO_UPLOAD_DIR", str(audio_path))
    monkeypatch.setenv("DEBUG", "false")

    # Reset cached settings + DB engine so the new env vars take effect
    import backend.config as cfg
    cfg._settings = None
    import backend.database as dbmod
    dbmod._engine = None
    dbmod.SessionLocal = None
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
