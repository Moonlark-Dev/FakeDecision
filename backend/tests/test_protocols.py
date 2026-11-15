from __future__ import annotations

import math

import pytest

from fake_decision.protocols import (
    ProtocolError,
    Question,
    build_google_response,
    build_systemone_response,
    normalize_answer,
    normalize_answers,
    parse_google,
    parse_systemone,
)
from tests.conftest import sample_questions


ALLOWED = ["jev-latest", "gemini-decision-1"]


def test_systemone_parse_and_response_shape():
    parsed = parse_systemone({"model": "jev-latest", "state": {"ticket": "double charge"}, "questions": sample_questions()}, "jev-latest", ALLOWED)
    assert parsed.protocol == "systemone"
    assert len(parsed.questions) == 3
    answers = {
        "refund": {"type": "noul", "noul": 0.91},
        "action": {"type": "choice", "choice": "refund", "probabilities": {"refund": 0.88, "replace": 0.12}, "confidence": 0.88},
        "urgency": {"type": "score", "score": 1.67, "probabilities": {"0": 0.05, "1": 0.23, "2": 0.72}, "confidence": 0.72, "legend": {"0": "Low", "1": "Medium", "2": "High"}},
    }
    normalized = normalize_answers(parsed.questions, answers)
    payload = build_systemone_response("jev-latest", parsed, normalized, 42)
    assert payload["model"] == "jev-latest"
    assert payload["usage"] == {"input_tokens": 42, "output_tokens": 0}
    assert payload["answers"]["refund"] == {"type": "noul", "noul": 0.91}
    assert payload["answers"]["action"]["choice"] == "refund"
    assert payload["answers"]["urgency"]["score"] == pytest.approx(1.67, abs=0.01)


def test_google_parse_and_response_shape():
    parsed = parse_google(
        {
            "model": "gemini-decision-1",
            "input": [{"type": "text", "text": "A spill near the counter."}, {"type": "image", "uri": "https://example.com/spill.jpg", "mime_type": "image/jpeg"}],
            "questions": sample_questions(),
        },
        "gemini-decision-1",
        ALLOWED,
    )
    assert parsed.input_kind == "multimodal"
    answers = {
        "refund": {"type": "noul", "noul": 0.63},
        "action": {"type": "choice", "choice": "replace", "probabilities": {"refund": 0.3, "replace": 0.7}, "confidence": 0.7},
        "urgency": {"type": "score", "score": 1.2, "probabilities": {"0": 0.2, "1": 0.4, "2": 0.4}, "confidence": 0.4, "legend": {"0": "Low", "1": "Medium", "2": "High"}},
    }
    normalized = normalize_answers(parsed.questions, answers)
    payload = build_google_response(parsed, normalized)
    assert "model" not in payload
    assert payload["answers"]["refund"] == {"type": "noul", "noul": 0.63, "confidence": 0.63}
    assert payload["answers"]["action"]["confidence"] == 0.7
    assert payload["answers"]["urgency"]["confidence"] == 0.4


def test_rejects_bad_choice_probabilities():
    question = Question(
        id="action",
        type="choice",
        instructions="Pick",
        criteria={"a": "A", "b": "B", "c": "C"},
    )
    with pytest.raises(ProtocolError):
        normalize_answer(question, {"type": "choice", "choice": "a", "probabilities": {"a": 0.1, "b": 0.8, "c": 0.1}})
    with pytest.raises(ProtocolError):
        normalize_answer(question, {"type": "choice", "choice": "a", "probabilities": {"a": 0.8, "b": 0.2}})


def test_normalizes_rounding_and_winner():
    question = Question(id="action", type="choice", instructions="Pick", criteria={"a": "A", "b": "B", "c": "C"})
    answer = normalize_answer(question, {"type": "choice", "choice": "a", "probabilities": {"a": 0.3333, "b": 0.3333, "c": 0.3334}})
    assert answer["choice"] == "a"
    assert answer["probabilities"]["a"] == max(answer["probabilities"].values())
    assert math.isclose(sum(answer["probabilities"].values()), 1.0, abs_tol=0.011)


def test_score_derivation_from_manual_score():
    question = Question(id="s", type="score", instructions="Rate", criteria=["Low", "Mid", "High"])
    answer = normalize_answer(question, {"type": "score", "score": 2})
    assert answer["score"] == pytest.approx(2.0, abs=0.15)
    assert answer["probabilities"]["2"] == max(answer["probabilities"].values())


def test_question_validation():
    with pytest.raises(ProtocolError):
        parse_systemone({"model": "jev-latest", "state": "x", "questions": {}}, "jev-latest", ALLOWED)
    with pytest.raises(ProtocolError):
        parse_systemone({"model": "jev-latest", "state": "x", "questions": {"q": {"type": "choice", "instructions": "x", "criteria": {"only": "one"}}}}, "jev-latest", ALLOWED)
    with pytest.raises(ProtocolError):
        parse_systemone({"model": "nope", "state": "x", "questions": sample_questions()}, "jev-latest", ALLOWED)
    with pytest.raises(ProtocolError):
        parse_google({"model": "gemini-decision-1", "input": "", "questions": sample_questions()}, "gemini-decision-1", ALLOWED)


def test_boolean_alias():
    parsed = parse_systemone(
        {"model": "jev-latest", "state": "x", "questions": {"q": {"type": "boolean", "instructions": "Yes?"}}},
        "jev-latest",
        ALLOWED,
    )
    assert parsed.questions[0].type == "noul"
