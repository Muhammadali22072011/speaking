from backend.services.question_bank import seed_if_empty, build_session_prompts
from backend import database as dbmod
from backend.models import Question


def test_seed_loads_all_four_files():
    seed_if_empty()
    db = dbmod.SessionLocal()
    try:
        total = db.query(Question).count()
        assert total >= 40, f"expected >=40 seeded questions, got {total}"

        # ensure each subtype is populated
        for part, subtype, min_count in [
            (1, "personal", 15),
            (1, "compare", 8),
            (2, "long_turn", 10),
            (3, "for_against", 10),
        ]:
            n = db.query(Question).filter(Question.part == part, Question.subtype == subtype).count()
            assert n >= min_count, f"{part}/{subtype}: expected >={min_count}, got {n}"
    finally:
        db.close()


def test_seed_is_idempotent():
    seed_if_empty()
    seed_if_empty()
    db = dbmod.SessionLocal()
    try:
        total = db.query(Question).count()
        # Should not double-seed
        assert total < 100
    finally:
        db.close()


def test_build_session_prompts_full_test():
    seed_if_empty()
    db = dbmod.SessionLocal()
    try:
        prompts = build_session_prompts(db, [1, 2, 3])
    finally:
        db.close()

    assert len(prompts) == 3
    p1 = prompts[0]
    assert p1["part"] == 1
    # 3 personal + 1 compare = 4 prompts in part 1
    assert len(p1["prompts"]) == 4
    types = [p["type"] for p in p1["prompts"]]
    assert types.count("personal") == 3
    assert types.count("compare") == 1
    # Part 1 timing
    for p in p1["prompts"]:
        assert p["prep_sec"] == 5
        assert p["rec_sec"] == 30

    p2 = prompts[1]
    assert p2["part"] == 2
    assert len(p2["prompts"]) == 1
    assert p2["prompts"][0]["type"] == "long_turn"
    assert p2["prompts"][0]["prep_sec"] == 60
    assert p2["prompts"][0]["rec_sec"] == 120

    p3 = prompts[2]
    assert p3["part"] == 3
    assert len(p3["prompts"]) == 1
    assert p3["prompts"][0]["type"] == "for_against"
    assert p3["prompts"][0]["prep_sec"] == 60
    assert p3["prompts"][0]["rec_sec"] == 120


def test_build_session_prompts_single_part():
    seed_if_empty()
    db = dbmod.SessionLocal()
    try:
        prompts = build_session_prompts(db, [2])
    finally:
        db.close()
    assert len(prompts) == 1
    assert prompts[0]["part"] == 2
