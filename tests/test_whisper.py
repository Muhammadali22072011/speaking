from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.services.whisper import (
    WhisperError,
    build_prompt_hint,
    transcribe_audio,
)


def test_build_prompt_hint_includes_personal_question_text():
    hint = build_prompt_hint({"text": "Tell me about your hometown."}, "personal")
    assert "hometown" in hint.lower()
    # Generic exam vocabulary primer is always included.
    assert "multilevel" in hint.lower()


def test_build_prompt_hint_includes_for_against_topic_and_bullets():
    hint = build_prompt_hint(
        {
            "topic": "Is it better to live in a big city or in the countryside?",
            "for_bullets": ["More career opportunities", "Better hospitals"],
            "against_bullets": ["Cleaner air", "Cost of living is lower"],
        },
        "for_against",
    )
    assert "countryside" in hint.lower()
    assert "cost of living" in hint.lower()
    assert "career" in hint.lower()


def test_build_prompt_hint_includes_compare_labels():
    hint = build_prompt_hint(
        {
            "pic1": {"emoji": "🍳", "label": "Cooking at home"},
            "pic2": {"emoji": "🍽️", "label": "Eating at a restaurant"},
            "questions": ["Which would you prefer on a weekend?"],
        },
        "compare",
    )
    assert "cooking at home" in hint.lower()
    assert "eating at a restaurant" in hint.lower()


def test_build_prompt_hint_handles_none_and_empty():
    hint_none = build_prompt_hint(None, None)
    hint_empty = build_prompt_hint({}, "personal")
    # Should still return at least the base primer, never empty.
    assert "multilevel" in hint_none.lower()
    assert "multilevel" in hint_empty.lower()


def test_build_prompt_hint_caps_length():
    huge = {"text": "x" * 5000}
    hint = build_prompt_hint(huge, "personal")
    assert len(hint) <= 900


def test_transcribe_audio_rejects_empty_payload():
    with pytest.raises(WhisperError):
        transcribe_audio(b"")


def test_transcribe_audio_returns_text_on_success():
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"text": "It is better to live in the countryside."}

    with patch("backend.services.whisper.httpx.post", return_value=fake_resp) as post:
        out = transcribe_audio(b"webm-bytes", prompt="hint", mime_type="audio/webm")

    assert out == "It is better to live in the countryside."
    post.assert_called_once()
    call_kwargs = post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"].startswith("Bearer ")
    assert "file" in call_kwargs["files"]
    assert call_kwargs["data"]["model"] == "whisper-large-v3"
    assert call_kwargs["data"]["language"] == "en"
    assert call_kwargs["data"]["prompt"] == "hint"


def test_transcribe_audio_raises_on_http_error():
    fake_resp = MagicMock(spec=httpx.Response)
    fake_resp.status_code = 500
    fake_resp.text = "internal error"

    with patch("backend.services.whisper.httpx.post", return_value=fake_resp):
        with pytest.raises(WhisperError):
            transcribe_audio(b"webm-bytes")


def test_transcribe_audio_raises_on_network_error():
    with patch(
        "backend.services.whisper.httpx.post",
        side_effect=httpx.ConnectError("no route"),
    ):
        with pytest.raises(WhisperError):
            transcribe_audio(b"webm-bytes")
