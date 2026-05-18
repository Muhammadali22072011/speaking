"""Question bank: seed loading + random selection."""
import json
import logging
import random
from pathlib import Path
from typing import Sequence

from sqlalchemy.orm import Session as SASession

from backend import database as dbmod
from backend.models import Question

log = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"


def _load_json(filename: str) -> list[dict]:
    path = SEED_DIR / filename
    if not path.exists():
        log.warning("Seed file missing: %s", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_if_empty() -> None:
    db = dbmod.SessionLocal()
    try:
        existing = db.query(Question).count()
        if existing > 0:
            log.info("Question bank already populated (%d rows); skipping seed", existing)
            return

        records: list[Question] = []

        for item in _load_json("part1_personal.json"):
            records.append(Question(part=1, subtype="personal", data=item, source="seed"))

        for item in _load_json("part1_compare.json"):
            records.append(Question(part=1, subtype="compare", data=item, source="seed"))

        for item in _load_json("part2.json"):
            records.append(Question(part=2, subtype="long_turn", data=item, source="seed"))

        for item in _load_json("part3.json"):
            records.append(Question(part=3, subtype="for_against", data=item, source="seed"))

        db.add_all(records)
        db.commit()
        log.info("Seeded %d questions into question bank", len(records))
    finally:
        db.close()


def _random_questions(
    db: SASession,
    part: int,
    subtype: str,
    count: int,
    custom_only: bool = False,
) -> list[Question]:
    query = db.query(Question).filter(Question.part == part, Question.subtype == subtype)
    if custom_only:
        query = query.filter(Question.source == "user")
    pool = query.all()
    if not pool:
        scope = "your uploaded" if custom_only else "available"
        raise RuntimeError(f"No {scope} questions for part={part}, subtype={subtype}")
    chosen = random.sample(pool, min(count, len(pool))) if len(pool) >= count else random.choices(pool, k=count)
    for q in chosen:
        q.times_used += 1
    return chosen


def _prompt_payload(q: Question, prep_sec: int, rec_sec: int) -> dict:
    return {
        "question_id": q.id,
        "type": q.subtype,
        "data": q.data,
        "prep_sec": prep_sec,
        "rec_sec": rec_sec,
    }


def build_session_prompts(
    db: SASession,
    parts: Sequence[int],
    custom_only: bool = False,
) -> list[dict]:
    """Select questions for each requested part and return prompt payloads.

    Part 1: 3 personal (each 5s prep, 30s rec) + 1 compare set (5s prep, 30s rec per question)
    Part 2: 1 long-turn set (60s prep, 120s rec covering all three questions)
    Part 3: 1 for/against (60s prep, 120s rec)
    """
    result: list[dict] = []

    for part in parts:
        if part == 1:
            personals = _random_questions(db, 1, "personal", 3, custom_only=custom_only)
            compares = _random_questions(db, 1, "compare", 1, custom_only=custom_only)
            prompts: list[dict] = []
            for q in personals:
                prompts.append(_prompt_payload(q, prep_sec=5, rec_sec=30))
            for q in compares:
                prompts.append(_prompt_payload(q, prep_sec=5, rec_sec=30))
            result.append({"part": 1, "prompts": prompts})

        elif part == 2:
            long_turns = _random_questions(db, 2, "long_turn", 1, custom_only=custom_only)
            prompts = [_prompt_payload(q, prep_sec=60, rec_sec=120) for q in long_turns]
            result.append({"part": 2, "prompts": prompts})

        elif part == 3:
            fors = _random_questions(db, 3, "for_against", 1, custom_only=custom_only)
            prompts = [_prompt_payload(q, prep_sec=60, rec_sec=120) for q in fors]
            result.append({"part": 3, "prompts": prompts})

        else:
            raise ValueError(f"Invalid part: {part}")

    db.commit()
    return result


# --- User-uploaded question import ----------------------------------------

def _validate_personal(item: dict) -> dict:
    text = str(item.get("text") or "").strip()
    if not text:
        raise ValueError("missing 'text'")
    return {"text": text}


def _validate_compare(item: dict) -> dict:
    pic1 = item.get("pic1") or {}
    pic2 = item.get("pic2") or {}
    questions = item.get("questions") or []
    label1 = str(pic1.get("label") or "").strip()
    label2 = str(pic2.get("label") or "").strip()
    if not label1 or not label2:
        raise ValueError("compare item needs pic1.label and pic2.label")
    if not isinstance(questions, list) or len(questions) < 1:
        raise ValueError("compare item needs at least one question")
    return {
        "pic1": {"emoji": str(pic1.get("emoji") or "🖼️"), "label": label1},
        "pic2": {"emoji": str(pic2.get("emoji") or "🖼️"), "label": label2},
        "questions": [str(q).strip() for q in questions if str(q).strip()],
    }


def _validate_long_turn(item: dict) -> dict:
    picture = item.get("picture") or {}
    questions = item.get("questions") or []
    label = str(picture.get("label") or "").strip()
    if not label:
        raise ValueError("part 2 item needs picture.label")
    if not isinstance(questions, list) or len(questions) < 1:
        raise ValueError("part 2 item needs at least one question")
    return {
        "picture": {"emoji": str(picture.get("emoji") or "📌"), "label": label},
        "questions": [str(q).strip() for q in questions if str(q).strip()],
    }


def _validate_for_against(item: dict) -> dict:
    topic = str(item.get("topic") or "").strip()
    fors = item.get("for_bullets") or []
    againsts = item.get("against_bullets") or []
    if not topic:
        raise ValueError("part 3 item needs topic")
    if not isinstance(fors, list) or len(fors) < 1:
        raise ValueError("part 3 item needs at least one for_bullet")
    if not isinstance(againsts, list) or len(againsts) < 1:
        raise ValueError("part 3 item needs at least one against_bullet")
    return {
        "topic": topic,
        "for_bullets": [str(b).strip() for b in fors if str(b).strip()],
        "against_bullets": [str(b).strip() for b in againsts if str(b).strip()],
    }


_SECTIONS = (
    ("part1_personal", 1, "personal", _validate_personal),
    ("part1_compare", 1, "compare", _validate_compare),
    ("part2", 2, "long_turn", _validate_long_turn),
    ("part3", 3, "for_against", _validate_for_against),
)


def import_user_questions(payload: dict) -> dict:
    """Validate and insert user-uploaded questions. Returns counts + errors."""
    if not isinstance(payload, dict):
        raise ValueError("Upload root must be a JSON object")

    counts = {"part1_personal": 0, "part1_compare": 0, "part2": 0, "part3": 0}
    errors: list[str] = []
    skipped = 0
    to_insert: list[Question] = []

    for key, part, subtype, validator in _SECTIONS:
        items = payload.get(key) or []
        if not isinstance(items, list):
            errors.append(f"'{key}' must be a list; got {type(items).__name__}")
            continue
        for idx, item in enumerate(items):
            try:
                data = validator(item if isinstance(item, dict) else {})
            except ValueError as e:
                skipped += 1
                errors.append(f"{key}[{idx}]: {e}")
                continue
            to_insert.append(Question(part=part, subtype=subtype, data=data, source="user"))
            counts[key] += 1

    if not to_insert:
        return {"counts": counts, "skipped": skipped, "errors": errors}

    db = dbmod.SessionLocal()
    try:
        db.add_all(to_insert)
        db.commit()
        log.info("Imported %d user questions", len(to_insert))
    finally:
        db.close()

    return {"counts": counts, "skipped": skipped, "errors": errors}


def custom_question_stats() -> dict:
    """Return per-subtype counts of user-uploaded questions."""
    db = dbmod.SessionLocal()
    try:
        out = {"part1_personal": 0, "part1_compare": 0, "part2": 0, "part3": 0}
        for key, part, subtype, _ in _SECTIONS:
            out[key] = (
                db.query(Question)
                .filter(Question.part == part, Question.subtype == subtype, Question.source == "user")
                .count()
            )
        out["total"] = sum(out.values())
        return out
    finally:
        db.close()


def clear_custom_questions() -> int:
    """Delete all user-uploaded questions. Returns rows deleted."""
    db = dbmod.SessionLocal()
    try:
        deleted = db.query(Question).filter(Question.source == "user").delete()
        db.commit()
        log.info("Cleared %d user questions", deleted)
        return deleted
    finally:
        db.close()
