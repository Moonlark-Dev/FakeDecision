from __future__ import annotations

import math

from fake_decision.protocols import Question
from fake_decision.randomize import randomize_answers, random_choice, random_noul, random_score


def _choice() -> Question:
    return Question(id="c", type="choice", instructions="Pick", criteria={f"option_{i}": f"Option {i}" for i in range(4)})


def _score() -> Question:
    return Question(id="s", type="score", instructions="Rate", criteria=["Very low", "Low", "Medium", "High", "Very high"])


def test_noul_range_and_confidence():
    for _ in range(500):
        answer = random_noul(Question(id="n", type="noul", instructions="?", criteria=None))
        assert 0.01 <= answer["noul"] <= 0.99
        assert answer["confidence"] == round(max(answer["noul"], 1 - answer["noul"]), 2)


def test_choice_is_normalized_and_confidence_matches_max():
    for _ in range(500):
        answer = random_choice(_choice())
        probs = answer["probabilities"]
        assert math.isclose(sum(probs.values()), 1.0, abs_tol=0.011)
        assert answer["choice"] == max(probs, key=probs.get)
        assert answer["confidence"] == max(probs.values())


def test_high_confidence_choice_is_not_flat():
    for _ in range(500):
        answer = random_choice(_choice())
        probs = answer["probabilities"]
        if answer["confidence"] >= 0.9:
            ordered = sorted(probs.values(), reverse=True)
            assert ordered[0] - ordered[1] >= 0.1


def test_score_distribution_consistency():
    for _ in range(500):
        answer = random_score(_score())
        probs = answer["probabilities"]
        assert set(probs) == {"0", "1", "2", "3", "4"}
        assert math.isclose(sum(probs.values()), 1.0, abs_tol=0.011)
        expected = round(sum(int(level) * p for level, p in probs.items()), 2)
        assert answer["score"] == expected
        assert answer["confidence"] == max(probs.values())


def test_randomize_only_selected_questions_preserves_others():
    questions = [Question(id="a", type="noul", instructions="", criteria=None), Question(id="b", type="noul", instructions="", criteria=None)]
    existing = {"b": {"type": "noul", "noul": 0.88, "confidence": 0.88}}
    result = randomize_answers(questions, only=["a"], existing=existing)
    assert "a" in result
    assert "b" not in result

    result2 = randomize_answers(questions, only=None, existing=existing)
    assert set(result2) == {"a", "b"}
