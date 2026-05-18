from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@router.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
