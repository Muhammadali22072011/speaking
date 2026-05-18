import json
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as SASession

from backend.config import get_settings
from backend.deps import get_db
from backend.models import Answer, Question, Session
from backend.schemas import TranscribeResponse
from backend.services.punctuator import restore_punctuation

router = APIRouter()
log = logging.getLogger(__name__)


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _parse_prosody(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw or raw == "null":
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


@router.post("/audio/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    transcript: str = Form(""),
    prosody: str = Form(""),
    session_id: int = Form(...),
    question_id: int = Form(...),
    question_idx: int = Form(...),
    duration_sec: float = Form(0.0),
    db: SASession = Depends(get_db),
) -> TranscribeResponse:
    """Persist the recorded audio + the transcript captured in the browser.

    Transcription happens client-side via the Web Speech API; the backend
    stores both artefacts, then runs Groq Llama to restore punctuation and
    produce a short intonation note from the prosody features captured
    during recording.
    """
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    settings = get_settings()
    session_dir = settings.audio_dir / str(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    audio_path = session_dir / f"{question_idx}.webm"

    contents = await audio.read()
    with open(audio_path, "wb") as f:
        f.write(contents)

    transcript = (transcript or "").strip()
    wc = _word_count(transcript)
    prosody_data = _parse_prosody(prosody)

    try:
        punct = restore_punctuation(transcript, prosody_data)
    except Exception:
        log.exception("Punctuation restoration failed; using raw transcript")
        punct = {"punctuated": transcript, "intonation_note": ""}
    punctuated = punct.get("punctuated") or transcript
    intonation_note = punct.get("intonation_note") or ""

    existing = (
        db.query(Answer)
        .filter(Answer.session_id == session_id, Answer.question_idx == question_idx)
        .first()
    )
    if existing:
        existing.audio_path = str(audio_path)
        existing.transcript = transcript
        existing.punctuated_transcript = punctuated
        existing.intonation_note = intonation_note
        existing.prosody_json = prosody_data
        existing.word_count = wc
        existing.duration_sec = duration_sec
        existing.question_id = question_id
    else:
        db.add(
            Answer(
                session_id=session_id,
                question_id=question_id,
                question_idx=question_idx,
                audio_path=str(audio_path),
                transcript=transcript,
                punctuated_transcript=punctuated,
                intonation_note=intonation_note,
                prosody_json=prosody_data,
                word_count=wc,
                duration_sec=duration_sec,
            )
        )
    db.commit()

    return TranscribeResponse(
        transcript=transcript,
        punctuated_transcript=punctuated,
        intonation_note=intonation_note,
        word_count=wc,
        duration_sec=duration_sec,
    )


@router.get("/audio/{session_id}/{idx}.webm")
async def get_audio(session_id: int, idx: int) -> FileResponse:
    settings = get_settings()
    path = settings.audio_dir / str(session_id) / f"{idx}.webm"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/webm")
