"""Claude API wrapper for grading a Speaking session."""
import json
import logging
import re

from anthropic import Anthropic, APIError

from backend.config import get_settings

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an examiner for the Uzbekistan National Multilevel English Speaking exam. You grade speaking performances against four criteria, each on a 0–9 scale:

1. Discourse Management — coherence, organisation, ability to develop ideas, use of cohesive devices, ability to fill the time appropriately
2. Grammar Range and Accuracy — variety of structures, error density and gravity
3. Vocabulary Range and Appropriacy — lexical breadth, topic-appropriate word choice, collocation
4. Pronunciation — Note: you only see transcripts, so estimate from spelling patterns, word repetition, and obvious fluency markers. Be conservative and flag this estimation.

Use these CEFR anchors (raw sum out of 36 → 75-point converted scale):
- 0–17 raw / 0–37 converted → below B1
- 18–24 raw / 38–50 converted → B1
- 25–30 raw / 51–64 converted → B2
- 31–36 raw / 65–75 converted → C1

A B2 candidate sustains long turns with minimal hesitation, uses a range of tenses and complex sentences, expresses and justifies opinions, and in Part 3 produces a clearly organised balanced argument with linkers.

You will receive transcripts of all answers in a session. Output strict JSON only, no other text:

{
  "discourse": 0.0,
  "grammar": 0.0,
  "vocabulary": 0.0,
  "pronunciation": 0.0,
  "feedback": {
    "discourse": "...",
    "grammar": "...",
    "vocabulary": "...",
    "pronunciation": "...",
    "overall": "...",
    "improvement_tips": ["tip 1", "tip 2", "tip 3"]
  }
}

Score conservatively. Most learners are B1–B2; only give 7+ when transcripts show genuine range and accuracy. Empty or very short transcripts get low scores."""


def _format_answers(answers: list[dict]) -> str:
    lines: list[str] = []
    for i, a in enumerate(answers, 1):
        lines.append(f"--- Answer {i} (Part {a['part']}) ---")
        lines.append(f"Question: {a['question']}")
        lines.append(f"Duration: {a.get('duration_sec', 0):.1f}s  |  Word count: {a.get('word_count', 0)}")
        lines.append(f"Transcript: {a.get('transcript') or '(empty)'}")
        lines.append("")
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # remove opening fence (optionally with language)
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def score_to_band(score_75: int) -> str:
    if score_75 <= 37:
        return "below B1"
    if score_75 <= 50:
        return "B1"
    if score_75 <= 64:
        return "B2"
    return "C1"


def grade_session(answers: list[dict]) -> dict:
    """Call Claude to grade a list of answers.

    Each answer dict has keys: part, question, transcript, word_count, duration_sec.
    Returns: {
        discourse, grammar, vocabulary, pronunciation,
        raw_sum, score_75, band, feedback: {...}
    }
    """
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    parts = sorted({a["part"] for a in answers})
    user_msg = (
        f"Grade this Speaking session. Parts attempted: {parts}.\n\n"
        f"{_format_answers(answers)}\n"
        "Output the JSON score now."
    )

    try:
        resp = client.messages.create(
            model=settings.claude_model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except APIError as e:
        log.exception("Claude API failed")
        raise RuntimeError(f"Claude grading API failed: {e}") from e

    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    log.debug("Claude raw output: %s", text)
    cleaned = _strip_code_fence(text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error("Failed to parse Claude JSON. Raw: %s", text)
        raise RuntimeError(f"Claude returned invalid JSON: {e}") from e

    discourse = float(parsed.get("discourse", 0))
    grammar = float(parsed.get("grammar", 0))
    vocabulary = float(parsed.get("vocabulary", 0))
    pronunciation = float(parsed.get("pronunciation", 0))
    feedback = parsed.get("feedback", {})

    for k in ("discourse", "grammar", "vocabulary", "pronunciation", "overall"):
        feedback.setdefault(k, "")
    feedback.setdefault("improvement_tips", [])

    raw_sum = round(discourse + grammar + vocabulary + pronunciation, 2)
    score_75 = round(raw_sum / 36.0 * 75.0)
    band = score_to_band(score_75)

    return {
        "discourse": discourse,
        "grammar": grammar,
        "vocabulary": vocabulary,
        "pronunciation": pronunciation,
        "raw_sum": raw_sum,
        "score_75": score_75,
        "band": band,
        "feedback": feedback,
    }
