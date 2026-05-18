"""Minimal Gemini API client (REST, free tier).

We use HTTP directly rather than the SDK to avoid extra dependencies.
"""
import logging
import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def generate_text(system: str, user: str, max_output_tokens: int = 1500) -> str:
    settings = get_settings()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.google_api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        },
    }
    try:
        resp = httpx.post(url, json=payload, timeout=60.0)
    except httpx.HTTPError as e:
        log.exception("Gemini HTTP error")
        raise LLMError(f"Gemini request failed: {e}") from e

    if resp.status_code != 200:
        body = resp.text[:500]
        log.error("Gemini %s: %s", resp.status_code, body)
        raise LLMError(f"Gemini API returned {resp.status_code}: {body}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        log.error("Unexpected Gemini response shape: %s", data)
        raise LLMError(f"Unexpected Gemini response shape: {e}") from e
    return text
