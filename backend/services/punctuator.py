"""Restore punctuation + capitalization in a raw browser transcript.

The browser's Web Speech API produces lowercase, unpunctuated text. We feed
that text — plus prosody hints captured during recording (pause boundaries,
mean / range pitch) — into Groq Llama and ask for a JSON payload with the
punctuated transcript and a short intonation note.

The intonation note is a one-sentence human-readable description that the
results screen can show to the learner ("you spoke with rich pitch range
but paused a lot"), and the grader also receives it as context.
"""
import json
import logging
import re

from backend.services.llm_client import generate_text, LLMError

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You restore punctuation and capitalization in English speech transcripts produced by browser speech recognition.

The speaker is an Uzbek learner taking the Multilevel Speaking exam, so expect non-native phrasing and small grammar errors. Do NOT fix grammar, do NOT rewrite, do NOT add or remove words. Only add: periods, commas, question marks, exclamation marks, apostrophes, and proper capitalization (sentence starts, the word "I", obvious proper nouns).

Use the prosody hints when provided:
- A LONG pause (>= 0.7 s) in the middle of speech is a strong cue for a full stop or paragraph break.
- A short pause (0.25 s to 0.7 s) is usually a comma.
- A wide pitch range with rising contour at the end of an utterance suggests a question mark.
- A narrow pitch range across the answer indicates monotone delivery.

Output strict JSON, no other text:

{
  "punctuated": "the same words, punctuated and capitalised.",
  "intonation_note": "one short sentence (max 25 words) describing pace, pausing, and pitch variation, or empty string if no prosody data was provided."
}

If the input is empty, output {"punctuated": "", "intonation_note": ""}."""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _format_prosody(prosody: dict | None) -> str:
    if not prosody:
        return "(no prosody data)"
    lines: list[str] = []
    pauses = prosody.get("pauses") or []
    if pauses:
        lines.append("Pauses (start_s, end_s, duration_s, kind):")
        for entry in pauses[:30]:
            try:
                s, e = float(entry[0]), float(entry[1])
            except (TypeError, ValueError, IndexError):
                continue
            d = round(e - s, 2)
            kind = "LONG" if d >= 0.7 else "short"
            lines.append(f"  {s:.2f}-{e:.2f} ({d:.2f}s, {kind})")
    if "pitch_mean_hz" in prosody:
        lines.append(
            f"Pitch: mean={prosody.get('pitch_mean_hz')} Hz, "
            f"p10={prosody.get('pitch_p10_hz')} Hz, p90={prosody.get('pitch_p90_hz')} Hz, "
            f"range={prosody.get('pitch_range_hz')} Hz, std={prosody.get('pitch_std_hz')} Hz"
        )
    if "voiced_ratio" in prosody:
        lines.append(f"Voiced fraction: {prosody.get('voiced_ratio')}")
    if "pause_count" in prosody:
        lines.append(
            f"Pause count: {prosody.get('pause_count')} "
            f"(long >= 0.7s: {prosody.get('long_pause_count', 0)}), "
            f"total pause: {prosody.get('total_pause_sec', 0)} s"
        )
    return "\n".join(lines) or "(no prosody data)"


def restore_punctuation(raw_text: str, prosody: dict | None = None) -> dict:
    """Return {"punctuated": str, "intonation_note": str}.

    Falls back to the raw text and an empty note if the LLM call fails — the
    speaking session must still go through even when Groq is unreachable.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {"punctuated": "", "intonation_note": ""}

    user_msg = (
        f"Raw transcript:\n{raw_text}\n\n"
        f"Prosody hints:\n{_format_prosody(prosody)}\n\n"
        "Output the JSON now."
    )

    try:
        text = generate_text(SYSTEM_PROMPT, user_msg, max_output_tokens=800)
    except LLMError as e:
        log.warning("Punctuator LLM call failed, falling back to raw: %s", e)
        return {"punctuated": raw_text, "intonation_note": ""}

    cleaned = _strip_code_fence(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("Punctuator returned invalid JSON, falling back to raw. Raw: %s", text[:200])
        return {"punctuated": raw_text, "intonation_note": ""}

    punctuated = str(parsed.get("punctuated") or raw_text).strip()
    intonation_note = str(parsed.get("intonation_note") or "").strip()
    return {"punctuated": punctuated, "intonation_note": intonation_note}
