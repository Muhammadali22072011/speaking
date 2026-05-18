from unittest.mock import patch

from backend.services.punctuator import restore_punctuation


def test_restore_punctuation_empty_input_skips_llm():
    with patch("backend.services.punctuator.generate_text") as gen:
        result = restore_punctuation("", None)
    gen.assert_not_called()
    assert result == {"punctuated": "", "intonation_note": ""}


def test_restore_punctuation_parses_json_response():
    fake = (
        '{"punctuated": "I am from Tashkent. It is a big city.",'
        ' "intonation_note": "Steady pace with one long pause."}'
    )
    with patch("backend.services.punctuator.generate_text", return_value=fake):
        result = restore_punctuation(
            "i am from tashkent it is a big city",
            {"pauses": [[1.2, 2.0]], "pitch_mean_hz": 150.0},
        )
    assert result["punctuated"].startswith("I am from Tashkent")
    assert result["punctuated"].endswith(".")
    assert "Steady pace" in result["intonation_note"]


def test_restore_punctuation_strips_code_fence():
    fake = '```json\n{"punctuated": "Hello, world.", "intonation_note": ""}\n```'
    with patch("backend.services.punctuator.generate_text", return_value=fake):
        result = restore_punctuation("hello world", None)
    assert result["punctuated"] == "Hello, world."


def test_restore_punctuation_falls_back_on_invalid_json():
    with patch("backend.services.punctuator.generate_text", return_value="not json"):
        result = restore_punctuation("some text", None)
    assert result["punctuated"] == "some text"
    assert result["intonation_note"] == ""


def test_restore_punctuation_falls_back_on_llm_error():
    from backend.services.punctuator import LLMError
    with patch("backend.services.punctuator.generate_text", side_effect=LLMError("boom")):
        result = restore_punctuation("hello", None)
    assert result == {"punctuated": "hello", "intonation_note": ""}


def test_format_prosody_handles_missing_fields():
    from backend.services.punctuator import _format_prosody
    assert _format_prosody(None) == "(no prosody data)"
    out = _format_prosody({"pauses": [[1.0, 1.6]], "pitch_mean_hz": 180})
    assert "1.00-1.60" in out
    assert "180" in out
