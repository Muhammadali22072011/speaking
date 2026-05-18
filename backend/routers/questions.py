from fastapi import APIRouter, HTTPException

from backend.schemas import GenerateQuestionsRequest, GenerateQuestionsResponse
from backend.services.claude_generator import generate_questions

router = APIRouter()


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate(payload: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
    try:
        ids = generate_questions(payload.part, payload.count)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return GenerateQuestionsResponse(inserted_ids=ids, count=len(ids))
