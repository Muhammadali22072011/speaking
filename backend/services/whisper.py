"""Server-side transcription via Groq's hosted Whisper.

The browser's Web Speech API mishears non-native speech badly (e.g. it
transcribes "countryside" as "countersight" and "cost of living" as
"cause of living"). Groq hosts `whisper-large-v3` on the same OpenAI-
compatible API as the LLM, free tier, no extra credentials needed — we
simply POST the recorded webm/opus blob and get back a much cleaner
transcript.

Whisper accepts an optional `prompt` of up to 224 tokens that biases
vocabulary. We pass the wording of the exam question itself so topic
words ("countryside", "advantages", "cost of living", etc.) are far more
likely to come through correctly.
"""
from __future__ import annotations

import logging

import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)


GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Generic vocabulary hint applied to every call. Helps Whisper lock onto
# English and onto exam-style register even when the per-question prompt
# is short.
_BASE_HINT = (
    "Uzbekistan Multilevel English speaking exam practice. "
    "The candidate discusses topics such as the countryside versus a "
    "big city, advantages and disadvantages, cost of living, education, "
    "hospitals, careers, the environment, technology, family, hobbies, "
    "and travel. Expect non-native phrasing with discourse markers like "
    "\"on the one hand\", \"on the other hand\", \"furthermore\", "
    "\"in addition\", \"in conclusion\"."
)


class WhisperError(RuntimeError):
    pass


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return " ".join(_stringify(v) for v in value if v is not None)
    if isinstance(value, dict):
        return " ".join(_stringify(v) for v in value.values() if v is not None)
    return str(value).strip()


def build_prompt_hint(question_data: dict | None, subtype: str | None = None) -> str:
    """Return a Whisper `prompt` string biased toward the question's wording.

    The data shape depends on subtype:
      personal:    {"text": "..."}
      compare:     {"pic1": {label}, "pic2": {label}, "questions": [...]}
      long_turn:   {"picture": {label}, "questions": [...]}
      for_against: {"topic": "...", "for_bullets": [...], "against_bullets": [...]}
    """
    pieces: list[str] = [_BASE_HINT]
    if isinstance(question_data, dict):
        for key in ("text", "topic"):
            v = _stringify(question_data.get(key))
            if v:
                pieces.append(v)
        for key in ("questions", "for_bullets", "against_bullets"):
            v = _stringify(question_data.get(key))
            if v:
                pieces.append(v)
        for key in ("pic1", "pic2", "picture"):
            sub = question_data.get(key)
            if isinstance(sub, dict):
                v = _stringify(sub.get("label"))
                if v:
                    pieces.append(v)
    hint = " ".join(p for p in pieces if p).strip()
    # Whisper caps the prompt at 224 tokens; keep it well under that.
    if len(hint) > 900:
        hint = hint[:900]
    return hint


def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "answer.webm",
    mime_type: str = "audio/webm",
    prompt: str | None = None,
    language: str = "en",
) -> str:
    """Transcribe a single audio clip with Groq Whisper.

    Returns the plain text transcript. Raises `WhisperError` on any
    failure so the caller can fall back to the browser transcript.
    """
    if not audio_bytes:
        raise WhisperError("empty audio payload")

    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    # httpx multipart: the audio file goes through `files`, the simple
    # text fields go through `data` (NOT `files`, otherwise the server
    # 400s with "field 'model' missing").
    files = {"file": (filename, audio_bytes, mime_type)}
    data = {
        "model": settings.groq_whisper_model,
        "language": language,
        "response_format": "json",
        "temperature": "0",
    }
    if prompt:
        data["prompt"] = prompt

    try:
        resp = httpx.post(
            GROQ_TRANSCRIPTION_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120.0,
        )
    except httpx.HTTPError as e:
        log.exception("Groq Whisper HTTP error")
        raise WhisperError(f"Groq Whisper request failed: {e}") from e

    if resp.status_code != 200:
        body = resp.text[:500]
        log.error("Groq Whisper %s: %s", resp.status_code, body)
        raise WhisperError(f"Groq Whisper returned {resp.status_code}: {body}")

    try:
        payload = resp.json()
    except ValueError as e:
        raise WhisperError(f"Groq Whisper returned non-JSON: {e}") from e

    text = (payload.get("text") or "").strip()
    return text
