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


def test_transcribe_endpoint_runs_punctuator_and_persists_prosody():
    """POST /api/audio/transcribe should call the punctuator and store the
    punctuated transcript, intonation note, and prosody summary."""
    import json
    from backend import database as dbmod
    from backend.models import Answer

    fake_punct = (
        '{"punctuated": "I am from Tashkent. It is a big city.",'
        ' "intonation_note": "Steady pace with one long pause."}'
    )
    prosody = {
        "pitch_mean_hz": 165.0,
        "pitch_range_hz": 80.0,
        "pause_count": 3,
        "long_pause_count": 1,
        "total_pause_sec": 2.1,
        "pauses": [[1.0, 1.7]],
    }

    with patch("backend.services.punctuator.generate_text", return_value=fake_punct):
        with _client() as c:
            r = c.post("/api/sessions/start", json={"parts": [1]})
            session_id = r.json()["session_id"]
            qid = r.json()["parts"][0]["prompts"][0]["question_id"]

            files = {"audio": ("0.webm", b"fake-webm-bytes", "audio/webm")}
            data = {
                "transcript": "i am from tashkent it is a big city",
                "prosody": json.dumps(prosody),
                "session_id": str(session_id),
                "question_id": str(qid),
                "question_idx": "0",
                "duration_sec": "12.5",
            }
            r2 = c.post("/api/audio/transcribe", files=files, data=data)
            assert r2.status_code == 200, r2.text
            body = r2.json()
            assert body["punctuated_transcript"].startswith("I am from Tashkent")
            assert "Steady pace" in body["intonation_note"]

            db = dbmod.SessionLocal()
            a = db.query(Answer).filter(Answer.session_id == session_id).first()
            assert a is not None
            assert a.punctuated_transcript.startswith("I am from Tashkent")
            assert a.intonation_note == "Steady pace with one long pause."
            assert a.prosody_json["pause_count"] == 3
            db.close()


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
