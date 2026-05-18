from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SASession

from backend.deps import get_db
from backend.models import Session
from backend.schemas import StartSessionRequest, StartSessionResponse
from backend.services.question_bank import build_session_prompts

router = APIRouter()


@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    payload: StartSessionRequest,
    db: SASession = Depends(get_db),
) -> StartSessionResponse:
    try:
        parts_payload = build_session_prompts(db, payload.parts, custom_only=payload.use_custom_only)
    except RuntimeError as e:
        raise HTTPException(status_code=400 if payload.use_custom_only else 500, detail=str(e))

    session = Session(parts=",".join(str(p) for p in payload.parts))
    db.add(session)
    db.commit()
    db.refresh(session)

    return StartSessionResponse(session_id=session.id, parts=parts_payload)
