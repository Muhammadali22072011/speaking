from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SASession

from backend.deps import get_db
from backend.models import Answer, Grade, Question, Session
from backend.schemas import (
    AnswerOut,
    GradeFeedback,
    GradeResponse,
    SessionResultResponse,
)
from backend.services.claude_grader import grade_session

router = APIRouter()
log = logging.getLogger(__name__)


def _question_text_for_prompt(q: Question) -> str:
    """Render a question's data field as a single string for the grader."""
    d = q.data
    if q.subtype == "personal":
        return d.get("text", "")
    if q.subtype == "compare":
        labels = f"{d.get('pic1', {}).get('label', '')} vs {d.get('pic2', {}).get('label', '')}"
        qs = " | ".join(d.get("questions", []))
        return f"Picture comparison ({labels}). Questions: {qs}"
    if q.subtype == "long_turn":
        label = d.get("picture", {}).get("label", "")
        qs = " | ".join(d.get("questions", []))
        return f"Long turn on '{label}'. Questions: {qs}"
    if q.subtype == "for_against":
        topic = d.get("topic", "")
        return f"For/against debate: {topic}"
    return str(d)


def _grade_to_response(session_id: int, grade: Grade) -> GradeResponse:
    return GradeResponse(
        session_id=session_id,
        discourse=grade.discourse,
        grammar=grade.grammar,
        vocabulary=grade.vocabulary,
        pronunciation=grade.pronunciation,
        raw_sum=grade.raw_sum,
        score_75=grade.score_75,
        band=grade.band,
        feedback=GradeFeedback(**grade.feedback_json),
        graded_at=grade.graded_at,
    )


@router.post("/{session_id}/finish", response_model=GradeResponse)
async def finish_session(session_id: int, db: SASession = Depends(get_db)) -> GradeResponse:
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answers = (
        db.query(Answer)
        .filter(Answer.session_id == session_id)
        .order_by(Answer.question_idx.asc())
        .all()
    )
    if not answers:
        raise HTTPException(status_code=400, detail="Session has no answers to grade")

    payload: list[dict] = []
    for a in answers:
        q = db.get(Question, a.question_id)
        payload.append(
            {
                "part": q.part if q else 0,
                "question": _question_text_for_prompt(q) if q else "",
                "transcript": a.transcript,
                "punctuated_transcript": a.punctuated_transcript or "",
                "intonation_note": a.intonation_note or "",
                "prosody": a.prosody_json or None,
                "word_count": a.word_count,
                "duration_sec": a.duration_sec,
            }
        )

    try:
        result = grade_session(payload)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Upsert grade (in case of re-finish)
    grade = db.query(Grade).filter(Grade.session_id == session_id).first()
    if grade:
        grade.discourse = result["discourse"]
        grade.grammar = result["grammar"]
        grade.vocabulary = result["vocabulary"]
        grade.pronunciation = result["pronunciation"]
        grade.raw_sum = result["raw_sum"]
        grade.score_75 = result["score_75"]
        grade.band = result["band"]
        grade.feedback_json = result["feedback"]
        grade.graded_at = datetime.utcnow()
    else:
        grade = Grade(
            session_id=session_id,
            discourse=result["discourse"],
            grammar=result["grammar"],
            vocabulary=result["vocabulary"],
            pronunciation=result["pronunciation"],
            raw_sum=result["raw_sum"],
            score_75=result["score_75"],
            band=result["band"],
            feedback_json=result["feedback"],
        )
        db.add(grade)

    session.finished_at = datetime.utcnow()
    session.total_score_75 = result["score_75"]
    session.band = result["band"]
    db.commit()
    db.refresh(grade)

    return _grade_to_response(session_id, grade)


@router.get("/{session_id}/result", response_model=SessionResultResponse)
async def get_result(session_id: int, db: SASession = Depends(get_db)) -> SessionResultResponse:
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answers = (
        db.query(Answer)
        .filter(Answer.session_id == session_id)
        .order_by(Answer.question_idx.asc())
        .all()
    )
    grade = db.query(Grade).filter(Grade.session_id == session_id).first()

    answer_payloads: list[AnswerOut] = []
    for a in answers:
        q = db.get(Question, a.question_id)
        answer_payloads.append(
            AnswerOut(
                id=a.id,
                question_id=a.question_id,
                question_idx=a.question_idx,
                question_part=q.part if q else 0,
                question_subtype=q.subtype if q else "",
                question_data=q.data if q else {},
                transcript=a.transcript,
                punctuated_transcript=a.punctuated_transcript,
                intonation_note=a.intonation_note,
                prosody=a.prosody_json,
                word_count=a.word_count,
                duration_sec=a.duration_sec,
                audio_url=f"/api/audio/{session_id}/{a.question_idx}.webm",
            )
        )

    return SessionResultResponse(
        session_id=session_id,
        parts=[int(p) for p in session.parts.split(",") if p],
        started_at=session.started_at,
        finished_at=session.finished_at,
        grade=_grade_to_response(session_id, grade) if grade else None,
        answers=answer_payloads,
    )
