import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import get_settings
from backend.database import init_db


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    log = logging.getLogger("multilevel.startup")
    log.info("Initialising database (%s)", settings.database_url)
    init_db()

    # Seed question bank on first run
    from backend.services.question_bank import seed_if_empty
    seed_if_empty()

    settings.audio_dir  # ensures dir exists
    log.info("Multilevel Speaking Trainer ready")
    yield
    log.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multilevel Speaking Trainer",
        description="Practice tool for the Uzbekistan National Multilevel English Speaking exam.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        index_path = frontend_dir / "index.html"
        if not index_path.exists():
            return FileResponse(Path(__file__).resolve().parent / "placeholder.html")
        return FileResponse(index_path)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # Routers wired up in later steps
    from backend.routers import sessions, questions, audio, scoring, progress
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
    app.include_router(audio.router, prefix="/api", tags=["audio"])
    app.include_router(scoring.router, prefix="/api/sessions", tags=["scoring"])
    app.include_router(progress.router, prefix="/api/progress", tags=["progress"])

    return app


app = create_app()
