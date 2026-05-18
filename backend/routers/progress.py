from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as SASession

from backend.deps import get_db
from backend.models import Session
from backend.schemas import ProgressSession

router = APIRouter()


@router.get("", response_model=list[ProgressSession])
async def progress(db: SASession = Depends(get_db)) -> list[ProgressSession]:
    sessions = db.query(Session).order_by(Session.started_at.asc()).all()
    return [
        ProgressSession(
            session_id=s.id,
            parts=[int(p) for p in s.parts.split(",") if p],
            started_at=s.started_at,
            finished_at=s.finished_at,
            score_75=s.total_score_75,
            band=s.band,
        )
        for s in sessions
    ]
