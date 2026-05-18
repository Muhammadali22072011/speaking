import json

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.schemas import (
    ClearCustomQuestionsResponse,
    CustomQuestionsStats,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    UploadQuestionsResponse,
)
from backend.services.claude_generator import generate_questions
from backend.services.question_bank import (
    clear_custom_questions,
    custom_question_stats,
    import_user_questions,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 1_000_000  # 1 MB — plenty for thousands of questions


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate(payload: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
    try:
        ids = generate_questions(payload.part, payload.count)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return GenerateQuestionsResponse(inserted_ids=ids, count=len(ids))


@router.post("/upload", response_model=UploadQuestionsResponse)
async def upload(file: UploadFile = File(...)) -> UploadQuestionsResponse:
    """Accept a JSON file with custom questions and insert them as source='user'."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 1 MB)")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e.msg} at line {e.lineno}")

    try:
        result = import_user_questions(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    counts = result["counts"]
    stats = CustomQuestionsStats(**counts, total=sum(counts.values()))
    return UploadQuestionsResponse(inserted=stats, skipped=result["skipped"], errors=result["errors"])


@router.get("/custom", response_model=CustomQuestionsStats)
async def get_custom_stats() -> CustomQuestionsStats:
    stats = custom_question_stats()
    return CustomQuestionsStats(**stats)


@router.delete("/custom", response_model=ClearCustomQuestionsResponse)
async def clear_custom() -> ClearCustomQuestionsResponse:
    return ClearCustomQuestionsResponse(deleted=clear_custom_questions())
