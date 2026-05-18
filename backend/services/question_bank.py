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


def _random_questions(db: SASession, part: int, subtype: str, count: int) -> list[Question]:
    pool = db.query(Question).filter(Question.part == part, Question.subtype == subtype).all()
    if not pool:
        raise RuntimeError(f"No questions available for part={part}, subtype={subtype}")
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


def build_session_prompts(db: SASession, parts: Sequence[int]) -> list[dict]:
    """Select questions for each requested part and return prompt payloads.

    Part 1: 3 personal (each 5s prep, 30s rec) + 1 compare set (5s prep, 30s rec per question)
    Part 2: 1 long-turn set (60s prep, 120s rec covering all three questions)
    Part 3: 1 for/against (60s prep, 120s rec)
    """
    result: list[dict] = []

    for part in parts:
        if part == 1:
            personals = _random_questions(db, 1, "personal", 3)
            compares = _random_questions(db, 1, "compare", 1)
            prompts: list[dict] = []
            for q in personals:
                prompts.append(_prompt_payload(q, prep_sec=5, rec_sec=30))
            for q in compares:
                prompts.append(_prompt_payload(q, prep_sec=5, rec_sec=30))
            result.append({"part": 1, "prompts": prompts})

        elif part == 2:
            long_turns = _random_questions(db, 2, "long_turn", 1)
            prompts = [_prompt_payload(q, prep_sec=60, rec_sec=120) for q in long_turns]
            result.append({"part": 2, "prompts": prompts})

        elif part == 3:
            fors = _random_questions(db, 3, "for_against", 1)
            prompts = [_prompt_payload(q, prep_sec=60, rec_sec=120) for q in fors]
            result.append({"part": 3, "prompts": prompts})

        else:
            raise ValueError(f"Invalid part: {part}")

    db.commit()
    return result
