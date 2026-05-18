from unittest.mock import patch

from fastapi.testclient import TestClient


def _client():
    from backend.main import create_app
    from backend.services.question_bank import seed_if_empty
    seed_if_empty()
    app = create_app()
    # The lifespan handler will re-init the DB & re-seed; that's fine because
    # seed_if_empty is idempotent.
    return TestClient(app)


def test_health():
    with _client() as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_start_session_full():
    with _client() as c:
        r = c.post("/api/sessions/start", json={"parts": [1, 2, 3]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "session_id" in body
        assert len(body["parts"]) == 3

        part1 = body["parts"][0]
        assert part1["part"] == 1
        assert len(part1["prompts"]) == 4
        for p in part1["prompts"]:
            assert p["prep_sec"] == 5
            assert p["rec_sec"] == 30

        part2 = body["parts"][1]
        assert part2["part"] == 2
        assert len(part2["prompts"]) == 1
        assert part2["prompts"][0]["prep_sec"] == 60
        assert part2["prompts"][0]["rec_sec"] == 120


def test_start_session_single_part():
    with _client() as c:
        r = c.post("/api/sessions/start", json={"parts": [3]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["parts"]) == 1
        assert body["parts"][0]["part"] == 3


def test_start_session_invalid_part():
    with _client() as c:
        r = c.post("/api/sessions/start", json={"parts": [9]})
        assert r.status_code == 422


def test_progress_empty():
    with _client() as c:
        r = c.get("/api/progress")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_generate_questions_mocked():
    """Question generation endpoint round-trip with mocked LLM."""
    fake = (
        '[{"text": "Tell me about a memorable journey you have made."},'
        ' {"text": "What kinds of skills are most useful in everyday life?"}]'
    )

    with patch("backend.services.claude_generator.generate_text", return_value=fake):
        with _client() as c:
            r = c.post("/api/questions/generate", json={"part": 1, "count": 2})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    assert len(body["inserted_ids"]) == 2


def test_finish_no_answers():
    with _client() as c:
        r = c.post("/api/sessions/start", json={"parts": [1]})
        session_id = r.json()["session_id"]
        r2 = c.post(f"/api/sessions/{session_id}/finish")
        assert r2.status_code == 400  # no answers yet


def _sample_upload_payload() -> dict:
    return {
        "part1_personal": [
            {"text": "Tell me about your hobby."},
            {"text": "What music do you like?"},
            {"text": "Where did you go on your last trip?"},
        ],
        "part1_compare": [
            {
                "pic1": {"emoji": "🚲", "label": "Cycling"},
                "pic2": {"emoji": "🚶", "label": "Walking"},
                "questions": ["What can you see in each picture?", "Which would you prefer?"],
            }
        ],
        "part2": [
            {
                "picture": {"emoji": "🎮", "label": "A favourite game"},
                "questions": [
                    "Tell me about a game you enjoy.",
                    "Why do you find it interesting?",
                    "How can games be useful for learning?",
                ],
            }
        ],
        "part3": [
            {
                "topic": "Should homework be banned at primary school?",
                "for_bullets": ["a", "b", "c", "d"],
                "against_bullets": ["e", "f", "g", "h"],
            }
        ],
    }


def test_upload_questions_round_trip():
    import json
    payload = _sample_upload_payload()
    with _client() as c:
        r = c.post(
            "/api/questions/upload",
            files={"file": ("q.json", json.dumps(payload), "application/json")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["inserted"]["total"] == 6
        assert body["inserted"]["part1_personal"] == 3
        assert body["skipped"] == 0
        assert body["errors"] == []

        stats = c.get("/api/questions/custom").json()
        assert stats["total"] == 6

        # delete
        d = c.delete("/api/questions/custom")
        assert d.status_code == 200
        assert d.json()["deleted"] == 6

        stats2 = c.get("/api/questions/custom").json()
        assert stats2["total"] == 0


def test_upload_questions_partial_invalid():
    import json
    payload = {
        "part1_personal": [
            {"text": "Good question."},
            {"text": ""},          # invalid
            {"nope": "x"},          # invalid
        ],
    }
    with _client() as c:
        r = c.post(
            "/api/questions/upload",
            files={"file": ("q.json", json.dumps(payload), "application/json")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["inserted"]["part1_personal"] == 1
        assert body["skipped"] == 2
        assert len(body["errors"]) == 2


def test_upload_invalid_json():
    with _client() as c:
        r = c.post(
            "/api/questions/upload",
            files={"file": ("q.json", b"not json", "application/json")},
        )
        assert r.status_code == 400


def test_start_session_custom_only_requires_uploads():
    with _client() as c:
        r = c.post("/api/sessions/start", json={"parts": [1], "use_custom_only": True})
        assert r.status_code == 400


def test_start_session_custom_only_succeeds_after_upload():
    import json
    with _client() as c:
        c.post(
            "/api/questions/upload",
            files={"file": ("q.json", json.dumps(_sample_upload_payload()), "application/json")},
        )
        r = c.post("/api/sessions/start", json={"parts": [1, 2, 3], "use_custom_only": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["parts"]) == 3


def test_finish_session_with_mocked_grading():
    """End-to-end: start session, fake an answer, finish, fetch result."""
    from backend import database as dbmod
    from backend.models import Answer

    fake_grade_json = (
        '{"discourse": 6, "grammar": 6, "vocabulary": 6, "pronunciation": 6,'
        '"feedback": {"discourse":"ok","grammar":"ok","vocabulary":"ok","pronunciation":"ok","overall":"B2","improvement_tips":["t1"]}}'
    )

    with patch("backend.services.claude_grader.generate_text", return_value=fake_grade_json):
        with _client() as c:
            r = c.post("/api/sessions/start", json={"parts": [1]})
            session_id = r.json()["session_id"]
            qid = r.json()["parts"][0]["prompts"][0]["question_id"]

            db = dbmod.SessionLocal()
            db.add(Answer(
                session_id=session_id, question_id=qid, question_idx=0,
                audio_path="/tmp/dummy.webm",
                transcript="This is my answer. I talk about hometown.",
                word_count=8, duration_sec=20.0,
            ))
            db.commit(); db.close()

            r2 = c.post(f"/api/sessions/{session_id}/finish")
            assert r2.status_code == 200, r2.text
            grade = r2.json()
            assert grade["raw_sum"] == 24.0
            assert grade["score_75"] == 50  # 24/36*75 = 50
            assert grade["band"] == "B1"

            r3 = c.get(f"/api/sessions/{session_id}/result")
            assert r3.status_code == 200
            body = r3.json()
            assert body["grade"]["score_75"] == 50
            assert len(body["answers"]) == 1
