from __future__ import annotations

import math
import random
from typing import Any

from .protocols import Question, normalize_distribution

RNG = random.SystemRandom()


def _mix_confidence() -> float:
    """A human-ish confidence distribution.

    Most answers are fairly sure, but not machine-perfect. There is a deliberate
    tail of ambiguous answers so the output does not look like `random.uniform`.
    """
    roll = RNG.random()
    if roll < 0.18:
        return RNG.uniform(0.38, 0.55)
    if roll < 0.48:
        return RNG.uniform(0.55, 0.72)
    if roll < 0.82:
        return RNG.uniform(0.72, 0.88)
    if roll < 0.97:
        return RNG.uniform(0.88, 0.965)
    return RNG.uniform(0.965, 0.99)


def random_noul(question: Question) -> dict[str, Any]:
    roll = RNG.random()
    if roll < 0.12:
        p = RNG.uniform(0.49, 0.55)
    elif roll < 0.32:
        p = RNG.uniform(0.55, 0.7)
    elif roll < 0.52:
        p = RNG.uniform(0.3, 0.45)
    elif roll < 0.72:
        p = RNG.uniform(0.7, 0.84)
    elif roll < 0.9:
        p = RNG.uniform(0.16, 0.3)
    else:
        p = RNG.choice([RNG.uniform(0.84, 0.97), RNG.uniform(0.03, 0.16)])
    p = round(min(0.99, max(0.01, p)), 2)
    return {"type": "noul", "noul": p, "confidence": round(max(p, 1 - p), 2)}


def _choice_winner(keys: list[str], criteria: dict[str, Any]) -> str:
    """Pick an option with a mild preference for earlier, non-empty descriptions."""
    weights: list[float] = []
    for index, key in enumerate(keys):
        description = criteria.get(key)
        weight = 1.0 / (1.0 + index * 0.06)
        if isinstance(description, str) and description.strip():
            weight *= 1.12
        if any(token in key.lower() for token in ("recommended", "default", "primary")):
            weight *= 1.25
        weights.append(weight)
    total = sum(weights)
    target = RNG.random() * total
    cursor = 0.0
    for key, weight in zip(keys, weights):
        cursor += weight
        if target <= cursor:
            return key
    return keys[-1]


def random_choice(question: Question) -> dict[str, Any]:
    criteria = question.criteria if isinstance(question.criteria, dict) else {}
    keys = [str(key) for key in criteria.keys()]
    if len(keys) < 2:
        raise ValueError("choice questions need at least two options")
    confidence = min(0.985, max(0.51, _mix_confidence()))
    winner = _choice_winner(keys, criteria)
    remaining = 1.0 - confidence
    others = [key for key in keys if key != winner]
    # Dirichlet-ish weights. A high-confidence answer leaves visibly little
    # probability mass for the runner-up, never a near-uniform high-confidence map.
    raw = [-math.log(max(1e-9, RNG.random())) for _ in others]
    total = sum(raw) or 1.0
    probabilities: dict[str, float] = {winner: confidence}
    for key, value in zip(others, raw):
        probabilities[key] = remaining * value / total
    result = normalize_distribution(probabilities, winner=winner)
    return {
        "type": "choice",
        "choice": winner,
        "probabilities": result,
        "confidence": round(max(result.values()), 2),
    }


def random_score(question: Question) -> dict[str, Any]:
    criteria = question.criteria if isinstance(question.criteria, list) else []
    count = len(criteria)
    if count < 2:
        raise ValueError("score questions need at least two levels")
    # A latent "true rating" plus varying uncertainty, then discretize through a
    # Gaussian-ish window over the ordered rubric. This yields plausible scores
    # such as 1.6/3 (0.12, 0.31, 0.41, 0.16) rather than a uniform map.
    confidence = _mix_confidence()
    if confidence > 0.9:
        sigma = RNG.uniform(0.35, 0.6)
    elif confidence > 0.78:
        sigma = RNG.uniform(0.55, 0.9)
    elif confidence > 0.65:
        sigma = RNG.uniform(0.85, 1.35)
    else:
        sigma = RNG.uniform(1.3, 2.2)
    center = RNG.uniform(0, count - 1)
    # Occasionally cluster near the low/high end, as graders often do.
    if RNG.random() < 0.18:
        center = RNG.uniform(0, max(0.1, count * 0.35))
    elif RNG.random() < 0.18:
        center = RNG.uniform(count * 0.65, count - 1)
    weights: list[float] = []
    for index in range(count):
        skew = 1.0 + (RNG.random() - 0.5) * 0.08
        weights.append(math.exp(-((index - center) ** 2) / (2 * sigma * sigma)) * skew)
    total = sum(weights)
    probabilities = {str(index): weights[index] / total for index in range(count)}
    result = normalize_distribution(probabilities)
    score = round(sum(index * result[str(index)] for index in range(count)), 2)
    return {
        "type": "score",
        "score": score,
        "probabilities": result,
        "confidence": round(max(result.values()), 2),
        "legend": {str(index): str(criteria[index]) for index in range(count)},
    }


def random_answer(question: Question) -> dict[str, Any]:
    if question.type == "noul":
        return random_noul(question)
    if question.type == "choice":
        return random_choice(question)
    if question.type == "score":
        return random_score(question)
    raise ValueError(f"unsupported question type: {question.type}")


def randomize_answers(
    questions: list[Question],
    only: list[str] | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    selected = set(only) if only else None
    result: dict[str, dict[str, Any]] = {}
    for question in questions:
        if selected is not None and question.id not in selected:
            continue
        result[question.id] = random_answer(question)
    return result
