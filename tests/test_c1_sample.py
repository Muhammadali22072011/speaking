from unittest.mock import patch

import pytest

from backend.services import c1_sample as svc
from backend.services.c1_sample import generate_c1_sample
from backend.services.llm_client import LLMError


@pytest.fixture(autouse=True)
def _clear_cache():
    svc.clear_cache()
    yield
    svc.clear_cache()


def test_generate_c1_sample_parses_json_and_returns_answer():
    fake = (
        '{"answer": "It is often argued that living in the countryside '
        'is preferable to city life. While metropolitan areas offer richer '
        'career prospects, they also impose a heavy financial burden..."}'
    )
    with patch("backend.services.c1_sample.generate_text", return_value=fake) as gen:
        out = generate_c1_sample(
            question_id=1,
            topic="Is it better to live in a big city or in the countryside?",
            for_bullets=["More career opportunities", "Better hospitals"],
            against_bullets=["Cleaner air", "Cheaper cost of living"],
        )
    assert out.startswith("It is often argued")
    gen.assert_called_once()
    # The user prompt should mention the topic and both bullet sides.
    user_arg = gen.call_args.args[1]
    assert "countryside" in user_arg.lower()
    assert "career opportunities" in user_arg.lower()
    assert "cheaper cost of living" in user_arg.lower()


def test_generate_c1_sample_caches_by_question_id():
    fake = '{"answer": "Cached answer."}'
    with patch("backend.services.c1_sample.generate_text", return_value=fake) as gen:
        a1 = generate_c1_sample(42, "Some topic", [], [])
        a2 = generate_c1_sample(42, "Some topic", [], [])
    assert a1 == a2 == "Cached answer."
    # Only one LLM call because the second hit came from cache.
    assert gen.call_count == 1


def test_generate_c1_sample_strips_code_fence():
    fake = '```json\n{"answer": "Fenced response."}\n```'
    with patch("backend.services.c1_sample.generate_text", return_value=fake):
        out = generate_c1_sample(1, "Topic", [], [])
    assert out == "Fenced response."


def test_generate_c1_sample_raises_on_empty_topic():
    with pytest.raises(RuntimeError, match="empty topic"):
        generate_c1_sample(1, "", ["a"], ["b"])


def test_generate_c1_sample_raises_on_invalid_json():
    with patch("backend.services.c1_sample.generate_text", return_value="not json"):
        with pytest.raises(RuntimeError, match="invalid JSON"):
            generate_c1_sample(1, "Topic", [], [])


def test_generate_c1_sample_raises_on_empty_answer():
    with patch(
        "backend.services.c1_sample.generate_text",
        return_value='{"answer": "   "}',
    ):
        with pytest.raises(RuntimeError, match="empty answer"):
            generate_c1_sample(1, "Topic", [], [])


def test_generate_c1_sample_wraps_llm_error():
    with patch(
        "backend.services.c1_sample.generate_text",
        side_effect=LLMError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            generate_c1_sample(1, "Topic", [], [])
