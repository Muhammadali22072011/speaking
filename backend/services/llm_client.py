"""Groq Chat Completions client (OpenAI-compatible, free tier).

Groq offers free hosted inference for Llama-3 models with very high speed.
Get a free key at https://console.groq.com/keys
"""
import logging
import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_text(system: str, user: str, max_output_tokens: int = 1500) -> str:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
        "max_tokens": max_output_tokens,
    }
    try:
        resp = httpx.post(GROQ_URL, headers=headers, json=payload, timeout=60.0)
    except httpx.HTTPError as e:
        log.exception("Groq HTTP error")
        raise LLMError(f"Groq request failed: {e}") from e

    if resp.status_code != 200:
        body = resp.text[:500]
        log.error("Groq %s: %s", resp.status_code, body)
        raise LLMError(f"Groq API returned {resp.status_code}: {body}")

    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        log.error("Unexpected Groq response shape: %s", data)
        raise LLMError(f"Unexpected Groq response shape: {e}") from e
    return text
