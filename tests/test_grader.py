from unittest.mock import patch, MagicMock

from backend.services.claude_grader import grade_session, score_to_band


def _claude_response(json_text: str):
    block = MagicMock()
    block.type = "text"
    block.text = json_text
    resp = MagicMock()
    resp.content = [block]
    return resp


def test_score_to_band_boundaries():
    assert score_to_band(0) == "below B1"
    assert score_to_band(37) == "below B1"
    assert score_to_band(38) == "B1"
    assert score_to_band(50) == "B1"
    assert score_to_band(51) == "B2"
    assert score_to_band(57) == "B2"
    assert score_to_band(64) == "B2"
    assert score_to_band(65) == "C1"
    assert score_to_band(75) == "C1"


def test_grade_session_parses_json_and_computes_score():
    payload = '{"discourse": 6.5, "grammar": 6.0, "vocabulary": 6.5, "pronunciation": 6.0, "feedback": {"discourse": "OK", "grammar": "OK", "vocabulary": "OK", "pronunciation": "OK", "overall": "B2 candidate.", "improvement_tips": ["use more linkers", "vary tenses"]}}'

    with patch("backend.services.claude_grader.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = _claude_response(payload)

        result = grade_session([
            {"part": 1, "question": "Tell me about your hometown.", "transcript": "I am from Tashkent. It is a big city...", "word_count": 50, "duration_sec": 28.0},
        ])

    assert result["discourse"] == 6.5
    assert result["grammar"] == 6.0
    assert result["vocabulary"] == 6.5
    assert result["pronunciation"] == 6.0
    assert result["raw_sum"] == 25.0
    # 25/36 * 75 = 52.08 → 52
    assert result["score_75"] == 52
    assert result["band"] == "B2"
    assert "improvement_tips" in result["feedback"]
    assert len(result["feedback"]["improvement_tips"]) == 2


def test_grade_session_strips_code_fences():
    payload = '```json\n{"discourse": 4, "grammar": 4, "vocabulary": 4, "pronunciation": 4, "feedback": {"discourse": "", "grammar": "", "vocabulary": "", "pronunciation": "", "overall": "", "improvement_tips": []}}\n```'

    with patch("backend.services.claude_grader.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _claude_response(payload)
        result = grade_session([{"part": 2, "question": "Q", "transcript": "short", "word_count": 1, "duration_sec": 5}])

    assert result["raw_sum"] == 16.0
    assert result["band"] == "below B1"  # 16/36*75 = 33.3 → 33


def test_grade_session_invalid_json_raises():
    with patch("backend.services.claude_grader.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _claude_response("not json at all")
        import pytest
        with pytest.raises(RuntimeError, match="invalid JSON"):
            grade_session([{"part": 1, "question": "q", "transcript": "t", "word_count": 1, "duration_sec": 1}])
