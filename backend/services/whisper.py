"""OpenAI Whisper transcription wrapper."""
import logging
from pathlib import Path

from openai import OpenAI, OpenAIError

from backend.config import get_settings

log = logging.getLogger(__name__)


def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


def transcribe_file(audio_path: Path) -> str:
    """Transcribe an audio file using OpenAI Whisper. Returns the transcript text.

    Raises RuntimeError on API failure so the router can return 502.
    """
    settings = get_settings()
    client = _client()
    log.info("Transcribing %s (size=%d bytes)", audio_path, audio_path.stat().st_size)

    try:
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model=settings.whisper_model,
                file=f,
                language="en",
                response_format="text",
            )
    except OpenAIError as e:
        log.exception("Whisper API failed")
        raise RuntimeError(f"Whisper API failed: {e}") from e

    # response_format="text" returns a plain string
    text = resp if isinstance(resp, str) else getattr(resp, "text", "")
    return text.strip()
