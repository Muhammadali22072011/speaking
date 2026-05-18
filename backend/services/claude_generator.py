"""LLM-based question generator (Gemini, free tier)."""
import json
import logging
import re
from typing import Any

from backend import database as dbmod
from backend.models import Question
from backend.services.llm_client import generate_text, LLMError

log = logging.getLogger(__name__)


PART_INSTRUCTIONS = {
    1: 'Generate {count} personal questions suitable for Part 1 of the Multilevel Speaking exam. Each should be answerable in 30 seconds by a B2 candidate, about everyday topics (hobbies, family, work, hometown, education, travel, food, technology, etc.). Avoid politics and controversy. Output a JSON array of objects: [{{"text": "..."}}, ...]',

    2: 'Generate {count} Part 2 prompts. Each consists of a thematic label, an emoji to represent the picture (since we do not have images yet), and three questions following a personal -> analytical -> abstract gradient. Topics: decisions, education, technology, environment, relationships, work, culture. Output JSON array: [{{"label": "...", "emoji": "🎓", "questions": ["personal...", "analytical...", "abstract..."]}}, ...]',

    3: 'Generate {count} Part 3 for/against topics. Each topic must be debatable with clear arguments on both sides. Provide 4 "for" bullets and 4 "against" bullets, each one short phrase (under 12 words). Avoid topics that are too sensitive. Output JSON: [{{"topic": "...", "for_bullets": [...], "against_bullets": [...]}}, ...]',
}

GENERATOR_SYSTEM = "You are a curriculum designer for the Uzbekistan National Multilevel English exam. Output only the requested JSON array, no commentary, no code fences."


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _validate_part1(item: dict) -> dict:
    if "text" not in item or not isinstance(item["text"], str) or not item["text"].strip():
        raise ValueError(f"Part 1 item missing 'text': {item}")
    return {"text": item["text"].strip()}


def _validate_part2(item: dict) -> dict:
    label = item.get("label", "").strip()
    emoji = item.get("emoji", "📌").strip() or "📌"
    questions = item.get("questions", [])
    if not label:
        raise ValueError(f"Part 2 item missing label: {item}")
    if not isinstance(questions, list) or len(questions) != 3:
        raise ValueError(f"Part 2 item must have exactly 3 questions: {item}")
    return {
        "picture": {"emoji": emoji, "label": label},
        "questions": [str(q).strip() for q in questions],
    }


def _validate_part3(item: dict) -> dict:
    topic = item.get("topic", "").strip()
    fors = item.get("for_bullets", [])
    againsts = item.get("against_bullets", [])
    if not topic:
        raise ValueError(f"Part 3 item missing topic: {item}")
    if len(fors) != 4 or len(againsts) != 4:
        raise ValueError(f"Part 3 needs 4 for and 4 against bullets: {item}")
    return {
        "topic": topic,
        "for_bullets": [str(b).strip() for b in fors],
        "against_bullets": [str(b).strip() for b in againsts],
    }


def _subtype_for_part(part: int) -> str:
    return {1: "personal", 2: "long_turn", 3: "for_against"}[part]


def generate_questions(part: int, count: int) -> list[int]:
    if part not in (1, 2, 3):
        raise ValueError(f"Invalid part: {part}")

    prompt = PART_INSTRUCTIONS[part].format(count=count)
    log.info("Generating %d questions for part %d via Gemini", count, part)

    try:
        text = generate_text(GENERATOR_SYSTEM, prompt, max_output_tokens=2000)
    except LLMError as e:
        raise RuntimeError(str(e)) from e

    cleaned = _strip_code_fence(text)
    try:
        items: list[Any] = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error("Generator returned invalid JSON. Raw: %s", text)
        raise RuntimeError(f"Generator returned invalid JSON: {e}") from e

    if not isinstance(items, list):
        raise RuntimeError(f"Generator returned non-list: {type(items)}")

    validator = {1: _validate_part1, 2: _validate_part2, 3: _validate_part3}[part]
    subtype = _subtype_for_part(part)

    validated: list[dict] = []
    for item in items:
        try:
            validated.append(validator(item))
        except ValueError as e:
            log.warning("Skipping invalid generated item: %s", e)

    if not validated:
        raise RuntimeError("Generator produced no valid items")

    db = dbmod.SessionLocal()
    try:
        inserted_ids: list[int] = []
        for v in validated:
            q = Question(part=part, subtype=subtype, data=v, source="generated")
            db.add(q)
            db.flush()
            inserted_ids.append(q.id)
        db.commit()
        log.info("Inserted %d generated questions for part %d", len(inserted_ids), part)
        return inserted_ids
    finally:
        db.close()
