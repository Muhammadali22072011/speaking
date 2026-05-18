"""Generate a model C1-level spoken answer for a Part 3 for/against topic.

The frontend results page lets the learner press "Hear a C1 example" on
any Part 3 answer card. We hand the topic and bullet hints to Groq Llama
and ask for a balanced, 130-150-word spoken answer that demonstrates the
discourse markers, complex grammar, and lexical range an examiner would
expect from a C1 candidate. The result is read aloud in the browser via
the existing SpeechSynthesis controller.

Results are cached in process memory by question_id so repeated clicks
don't re-hit the LLM — the Question rows are immutable once seeded so
this cache never goes stale.
"""
import json
import logging
import re
import threading
from typing import Sequence

from backend.services.llm_client import generate_text, LLMError

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert C1-level English speaker producing model answers for the Uzbekistan National Multilevel Speaking exam, Part 3 (for/against debate).

Your model answer must:
- Be 130-160 words long (this fits the 120-second time limit at natural pace).
- Pick exactly two arguments from the FOR side and two from the AGAINST side, paraphrasing them in your own words (do NOT copy the bullets verbatim).
- Open with a discourse-marker hook such as "It is often argued that...", "There is much debate over whether...", or "Opinions are divided on...".
- Use sophisticated linkers: "while", "whereas", "on the other hand", "nevertheless", "by contrast", "having said that", "ultimately".
- Use varied sentence structures: at least one relative clause, one conditional, and one participle/cleft construction.
- Use precise C1 vocabulary and natural collocations (e.g. "a heavy financial burden", "broaden one's horizons", "stifle creativity", "foster a sense of community").
- End with a clear personal verdict introduced by something like "On balance, I would argue that..." or "All things considered, I believe...".
- Be spoken English: contractions are fine, but no slang, no filler ("um", "you know"), no markdown, no bullet points.

Output strict JSON, nothing else:

{"answer": "the full spoken model answer as one paragraph of natural English"}
"""


def _format_bullets(bullets: Sequence[str]) -> str:
    cleaned = [b.strip() for b in bullets if str(b).strip()]
    if not cleaned:
        return "(none provided — invent two plausible ones)"
    return "\n".join(f"- {b}" for b in cleaned)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


_cache: dict[int, str] = {}
_cache_lock = threading.Lock()


def generate_c1_sample(
    question_id: int,
    topic: str,
    for_bullets: Sequence[str],
    against_bullets: Sequence[str],
) -> str:
    """Return a C1-level model answer for the given Part 3 topic.

    Cached per question_id so repeat clicks on the same card don't
    re-invoke the LLM.
    """
    topic = (topic or "").strip()
    if not topic:
        raise RuntimeError("Cannot generate a C1 sample for an empty topic")

    with _cache_lock:
        cached = _cache.get(question_id)
    if cached:
        return cached

    user_msg = (
        f"Topic: {topic}\n\n"
        f"Suggested arguments FOR:\n{_format_bullets(for_bullets)}\n\n"
        f"Suggested arguments AGAINST:\n{_format_bullets(against_bullets)}\n\n"
        "Write the model answer now. Output the JSON object only."
    )

    try:
        raw = generate_text(SYSTEM_PROMPT, user_msg, max_output_tokens=900)
    except LLMError as e:
        raise RuntimeError(f"C1 sample generation failed: {e}") from e

    cleaned = _strip_code_fence(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error("C1 sample returned invalid JSON. Raw: %s", raw[:200])
        raise RuntimeError(f"C1 sample returned invalid JSON: {e}") from e

    answer = str(parsed.get("answer") or "").strip()
    if not answer:
        raise RuntimeError("C1 sample LLM returned an empty answer")

    with _cache_lock:
        _cache[question_id] = answer
    return answer


def clear_cache() -> None:
    """Reset the in-process cache (used by tests)."""
    with _cache_lock:
        _cache.clear()
