from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_QUESTIONS = 1000
MAX_CHOICES = 255
MAX_INSTRUCTIONS_CHARS = 200_000

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ProtocolError(Exception):
    def __init__(self, status: int, message: str, code: str = "invalid_request"):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


@dataclass(slots=True)
class Question:
    id: str
    type: str
    instructions: Any
    criteria: Any

    def display_instructions(self) -> str:
        return text_of(self.instructions)

    def display_criteria(self) -> list[dict[str, Any]]:
        if self.type == "choice":
            if not isinstance(self.criteria, dict):
                return []
            return [
                {"key": str(key), "label": str(key), "description": text_of(value)}
                for key, value in self.criteria.items()
            ]
        if self.type == "score":
            if not isinstance(self.criteria, list):
                return []
            return [
                {"key": str(index), "label": f"Level {index}", "description": text_of(value)}
                for index, value in enumerate(self.criteria)
            ]
        if self.type == "noul":
            if not isinstance(self.criteria, dict):
                return []
            return [
                {"key": key, "label": "True" if key == "true" else "False", "description": text_of(value)}
                for key, value in self.criteria.items()
            ]
        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "instructions": self.instructions,
            "criteria": self.criteria,
            "display": {
                "instructions": self.display_instructions(),
                "criteria": self.display_criteria(),
            },
        }


@dataclass(slots=True)
class ParsedRequest:
    protocol: str
    model: str
    input: Any
    input_text: str
    questions: list[Question]
    raw: dict[str, Any] = field(default_factory=dict)
    input_kind: str = "text"

    def question_map(self) -> dict[str, Question]:
        return {q.id: q for q in self.questions}

    def questions_json(self) -> list[dict[str, Any]]:
        return [q.to_dict() for q in self.questions]


def text_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(value)


def estimate_tokens(parsed: ParsedRequest) -> int:
    total = len(parsed.input_text)
    for question in parsed.questions:
        total += len(question.display_instructions())
        total += sum(len(item["description"]) for item in question.display_criteria())
    return max(1, math.ceil(total / 4))


def _block_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return text_of(block)
    block_type = block.get("type")
    if isinstance(block.get("text"), str):
        return block["text"]
    if block_type in {"image", "audio", "video", "file", "document", "pdf"}:
        uri = block.get("uri") or block.get("file_uri") or block.get("url") or block.get("data")
        mime = block.get("mime_type") or block.get("mimeType") or ""
        name = block.get("name") or block.get("filename") or ""
        label = str(block_type).upper()
        suffix = " · ".join(part for part in (mime, name) if part)
        return f"[{label}{' · ' + suffix if suffix else ''}]\n{uri if isinstance(uri, str) else '[inline media]'}"
    return text_of(block)


def _input_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n\n".join(_block_text(block) for block in value)
    if isinstance(value, dict):
        return _block_text(value)
    return text_of(value)


def _input_kind(value: Any) -> str:
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        kinds = {block.get("type") for block in value if isinstance(block, dict) and block.get("type")}
        media = kinds - {"text"}
        if media:
            return "multimodal"
        return "text"
    return "structured"


def _validate_question_id(qid: str) -> None:
    if not qid or len(qid) > 128 or CONTROL_RE.search(qid):
        raise ProtocolError(400, "问题 ID 必须为 1-128 个可打印字符", "invalid_question_id")


def _normalize_instructions(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        if len(value) > MAX_INSTRUCTIONS_CHARS:
            raise ProtocolError(400, "instructions 过长", "invalid_question")
        return value
    if isinstance(value, (dict, list)):
        encoded = text_of(value)
        if len(encoded) > MAX_INSTRUCTIONS_CHARS:
            raise ProtocolError(400, "instructions 过长", "invalid_question")
        return value
    raise ProtocolError(400, "instructions 必须是字符串、对象或数组", "invalid_question")


def _parse_systemone_questions(raw: Any) -> list[Question]:
    if not isinstance(raw, dict) or not raw:
        raise ProtocolError(400, "questions 必须是非空对象", "invalid_questions")
    if len(raw) > MAX_QUESTIONS:
        raise ProtocolError(400, f"每个请求最多 {MAX_QUESTIONS} 个问题", "too_many_questions")
    questions: list[Question] = []
    for qid, spec in raw.items():
        _validate_question_id(str(qid))
        if not isinstance(spec, dict):
            raise ProtocolError(400, f"问题 {qid} 必须是对象", "invalid_question")
        qtype = spec.get("type")
        if qtype == "boolean":
            qtype = "noul"
        if qtype not in {"noul", "choice", "score"}:
            raise ProtocolError(400, f"问题 {qid} 的 type 必须是 noul、choice 或 score", "invalid_question_type")
        instructions = _normalize_instructions(spec.get("instructions"))
        criteria = spec.get("criteria")
        if qtype == "choice":
            if not isinstance(criteria, dict) or len(criteria) < 2:
                raise ProtocolError(400, f"choice 问题 {qid} 需要至少两个选项", "invalid_criteria")
            if len(criteria) > MAX_CHOICES:
                raise ProtocolError(400, f"choice 问题 {qid} 最多 {MAX_CHOICES} 个选项", "invalid_criteria")
        elif qtype == "score":
            if not isinstance(criteria, list) or len(criteria) < 2:
                raise ProtocolError(400, f"score 问题 {qid} 需要至少两个等级", "invalid_criteria")
            if len(criteria) > MAX_CHOICES:
                raise ProtocolError(400, f"score 问题 {qid} 最多 {MAX_CHOICES} 个等级", "invalid_criteria")
        elif criteria is not None and not isinstance(criteria, dict):
            raise ProtocolError(400, f"noul 问题 {qid} 的 criteria 必须是对象", "invalid_criteria")
        questions.append(Question(id=str(qid), type=qtype, instructions=instructions, criteria=criteria))
    return questions


def parse_systemone(body: Any, default_model: str, allowed_models: Iterable[str]) -> ParsedRequest:
    if not isinstance(body, dict):
        raise ProtocolError(400, "请求体必须是 JSON 对象", "invalid_json")
    model = body.get("model") or default_model
    if not isinstance(model, str) or not model.strip():
        raise ProtocolError(400, "缺少 model", "invalid_model")
    model = model.strip()
    allowed = set(allowed_models)
    if model not in allowed:
        raise ProtocolError(404, f"模型不存在或不可用：{model}", "model_not_found")
    if "state" not in body or body["state"] is None:
        raise ProtocolError(400, "缺少非空的 state", "invalid_state")
    state = body["state"]
    if isinstance(state, str) and not state.strip():
        raise ProtocolError(400, "state 不能为空", "invalid_state")
    questions = _parse_systemone_questions(body.get("questions"))
    return ParsedRequest(
        protocol="systemone",
        model=model,
        input=state,
        input_text=_input_text(state),
        questions=questions,
        raw=body,
        input_kind=_input_kind(state),
    )


def parse_google(body: Any, default_model: str, allowed_models: Iterable[str], path_model: str | None = None) -> ParsedRequest:
    if not isinstance(body, dict):
        raise ProtocolError(400, "请求体必须是 JSON 对象", "INVALID_ARGUMENT")
    model = path_model or body.get("model") or default_model
    if not isinstance(model, str) or not model.strip():
        raise ProtocolError(400, "缺少 model", "INVALID_ARGUMENT")
    model = model.strip()
    if model.startswith("models/"):
        model = model[len("models/") :]
    allowed = set(allowed_models)
    if model not in allowed:
        raise ProtocolError(404, f"模型不存在或不可用：{model}", "NOT_FOUND")
    if "input" not in body or body["input"] is None:
        raise ProtocolError(400, "缺少非空的 input", "INVALID_ARGUMENT")
    value = body["input"]
    if isinstance(value, str) and not value.strip():
        raise ProtocolError(400, "input 不能为空", "INVALID_ARGUMENT")
    questions = _parse_systemone_questions(body.get("questions"))
    return ParsedRequest(
        protocol="google",
        model=model,
        input=value,
        input_text=_input_text(value),
        questions=questions,
        raw=body,
        input_kind=_input_kind(value),
    )


def _round(value: float, decimals: int = 2) -> float:
    return round(float(value) + 1e-12, decimals)


def normalize_distribution(values: dict[str, float], winner: str | None = None) -> dict[str, float]:
    if not values:
        raise ProtocolError(422, "概率分布不能为空", "invalid_answer")
    clean: dict[str, float] = {}
    for key, raw in values.items():
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ProtocolError(422, "概率必须是数字", "invalid_answer")
        if not math.isfinite(val) or val < 0 or val > 1:
            raise ProtocolError(422, "概率必须在 0 到 1 之间", "invalid_answer")
        clean[str(key)] = val
    total = sum(clean.values())
    if total <= 0:
        raise ProtocolError(422, "概率之和必须大于 0", "invalid_answer")
    normalized = {key: val / total for key, val in clean.items()}
    decimals = 2 if len(normalized) <= 20 else 3 if len(normalized) <= 100 else 4
    rounded = {key: _round(val, decimals) for key, val in normalized.items()}
    diff = _round(1.0 - sum(rounded.values()), decimals)
    if abs(diff) >= 0.001:
        target_key = winner if winner in rounded else max(rounded, key=rounded.get)
        rounded[target_key] = max(0.0, _round(rounded[target_key] + diff, decimals))
    if winner is not None:
        if winner not in rounded:
            raise ProtocolError(422, "选中项不在概率分布中", "invalid_answer")
        leader = max(rounded, key=rounded.get)
        if leader != winner:
            gap = rounded[leader] - rounded[winner]
            if gap > 0.0201:
                raise ProtocolError(422, "选中项必须是概率最高的选项", "invalid_answer")
            # Repair only floating-point/rounding-scale disagreements; a human
            # selection must remain the argmax without returning a contradiction.
            delta = _round(gap + 0.01)
            if rounded[leader] - delta >= 0:
                rounded[leader] = _round(rounded[leader] - delta)
                rounded[winner] = _round(rounded[winner] + delta)
        if max(rounded.values()) > rounded[winner]:
            raise ProtocolError(422, "选中项必须是概率最高的选项", "invalid_answer")
    return rounded


def _confidence(values: dict[str, float]) -> float:
    return _round(max(values.values()) if values else 0.0)


def normalize_answer(question: Question, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProtocolError(422, f"问题 {question.id} 的回答必须是对象", "invalid_answer")
    qtype = question.type
    if qtype == "noul":
        value = raw.get("noul", raw.get("probability"))
        if value is None:
            raise ProtocolError(422, f"问题 {question.id} 缺少 noul 概率", "invalid_answer")
        try:
            p = float(value)
        except (TypeError, ValueError):
            raise ProtocolError(422, f"问题 {question.id} 的 noul 概率必须是数字", "invalid_answer")
        if not math.isfinite(p):
            raise ProtocolError(422, f"问题 {question.id} 的 noul 概率无效", "invalid_answer")
        p = min(0.99, max(0.01, p))
        return {"type": "noul", "noul": _round(p), "confidence": _round(max(p, 1 - p))}
    if qtype == "choice":
        criteria = question.criteria if isinstance(question.criteria, dict) else {}
        keys = [str(key) for key in criteria.keys()]
        choice = raw.get("choice")
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, dict):
            if not isinstance(choice, str) or choice not in keys:
                raise ProtocolError(422, f"问题 {question.id} 缺少 choice 或概率分布", "invalid_answer")
            confidence = raw.get("confidence", 0.8)
            try:
                p = min(0.99, max(0.51, float(confidence)))
            except (TypeError, ValueError):
                p = 0.8
            rest = (1 - p) / max(1, len(keys) - 1)
            probabilities = {key: (p if key == choice else rest) for key in keys}
        probabilities = {str(key): value for key, value in probabilities.items()}
        if set(probabilities) != set(keys):
            raise ProtocolError(422, f"问题 {question.id} 的概率分布必须覆盖全部选项", "invalid_answer")
        if choice is None:
            choice = max(probabilities, key=probabilities.get)
        if not isinstance(choice, str) or choice not in keys:
            raise ProtocolError(422, f"问题 {question.id} 的 choice 不在选项中", "invalid_answer")
        try:
            numeric = {key: float(value) for key, value in probabilities.items()}
        except (TypeError, ValueError) as exc:
            raise ProtocolError(422, f"问题 {question.id} 的概率必须是数字", "invalid_answer") from exc
        result = normalize_distribution(numeric, winner=choice)
        return {
            "type": "choice",
            "choice": choice,
            "probabilities": result,
            "confidence": _confidence(result),
        }
    if qtype == "score":
        criteria = question.criteria if isinstance(question.criteria, list) else []
        count = len(criteria)
        raw_probs = raw.get("probabilities")
        try:
            if isinstance(raw_probs, dict):
                probabilities = {str(key): float(value) for key, value in raw_probs.items()}
            elif isinstance(raw_probs, list):
                probabilities = {str(index): float(value) for index, value in enumerate(raw_probs)}
            else:
                probabilities = None
        except (TypeError, ValueError) as exc:
            raise ProtocolError(422, f"问题 {question.id} 的概率必须是数字", "invalid_answer") from exc
        if probabilities is None:
            score_value = raw.get("score")
            if score_value is None:
                raise ProtocolError(422, f"问题 {question.id} 缺少概率分布", "invalid_answer")
            try:
                score_value = min(float(count) - 1, max(0.0, float(score_value)))
            except (TypeError, ValueError):
                raise ProtocolError(422, f"问题 {question.id} 的 score 必须是数字", "invalid_answer")
            lower = int(math.floor(score_value))
            upper = min(count - 1, lower + 1)
            if lower == upper:
                probabilities = {str(index): (1.0 if index == lower else 0.0) for index in range(count)}
            else:
                upper_weight = score_value - lower
                probabilities = {
                    str(index): (1 - upper_weight if index == lower else upper_weight if index == upper else 0.0)
                    for index in range(count)
                }
        expected = {str(index) for index in range(count)}
        if set(probabilities) != expected:
            raise ProtocolError(422, f"问题 {question.id} 的概率分布必须覆盖全部等级", "invalid_answer")
        result = normalize_distribution(probabilities)
        score = _round(sum(index * result[str(index)] for index in range(count)))
        legend = {str(index): text_of(value) for index, value in enumerate(criteria)}
        return {
            "type": "score",
            "score": score,
            "probabilities": result,
            "confidence": _confidence(result),
            "legend": legend,
        }
    raise ProtocolError(422, "未知问题类型", "invalid_answer")


def normalize_answers(questions: list[Question], raw_answers: Any, require_all: bool = True) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_answers, dict):
        raise ProtocolError(422, "answers 必须是对象", "invalid_answers")
    answers: dict[str, dict[str, Any]] = {}
    for question in questions:
        if question.id in raw_answers:
            answers[question.id] = normalize_answer(question, raw_answers[question.id])
        elif require_all:
            raise ProtocolError(422, f"问题 {question.id} 尚未回答", "incomplete_answers")
    unknown = set(raw_answers) - {q.id for q in questions}
    if unknown:
        raise ProtocolError(422, f"未知问题：{', '.join(sorted(unknown)[:5])}", "unknown_question")
    return answers


def merge_partial(questions: list[Question], raw_answers: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_answers, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for question in questions:
        if question.id not in raw_answers:
            continue
        try:
            result[question.id] = normalize_answer(question, raw_answers[question.id])
        except ProtocolError:
            continue
    return result


def build_systemone_response(
    model: str,
    parsed: ParsedRequest,
    answers: dict[str, dict[str, Any]],
    input_tokens: int,
) -> dict[str, Any]:
    output_answers: dict[str, Any] = {}
    for question in parsed.questions:
        answer = answers[question.id]
        if question.type == "noul":
            output_answers[question.id] = {"type": "noul", "noul": _round(answer["noul"])}
        elif question.type == "choice":
            output_answers[question.id] = {
                "type": "choice",
                "choice": answer["choice"],
                "probabilities": {key: _round(value) for key, value in answer["probabilities"].items()},
                "confidence": _round(answer["confidence"]),
            }
        else:
            output_answers[question.id] = {
                "type": "score",
                "score": _round(answer["score"]),
                "probabilities": {key: _round(value) for key, value in answer["probabilities"].items()},
                "confidence": _round(answer["confidence"]),
                "legend": answer.get("legend", {}),
            }
    return {
        "model": model,
        "answers": output_answers,
        "usage": {"input_tokens": input_tokens, "output_tokens": 0},
        "rounding": {"probabilityDecimals": 2, "scoreDecimals": 2},
    }


def build_google_response(
    parsed: ParsedRequest,
    answers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    output_answers: dict[str, Any] = {}
    for question in parsed.questions:
        answer = answers[question.id]
        if question.type == "noul":
            output_answers[question.id] = {
                "type": "noul",
                "noul": _round(answer["noul"]),
                "confidence": _round(answer["confidence"]),
            }
        elif question.type == "choice":
            output_answers[question.id] = {
                "type": "choice",
                "choice": answer["choice"],
                "probabilities": {key: _round(value) for key, value in answer["probabilities"].items()},
                "confidence": _round(answer["confidence"]),
            }
        else:
            output_answers[question.id] = {
                "type": "score",
                "score": _round(answer["score"]),
                "probabilities": {key: _round(value) for key, value in answer["probabilities"].items()},
                "confidence": _round(answer["confidence"]),
                "legend": answer.get("legend", {}),
            }
    return {"answers": output_answers}


def systemone_error(status: int, message: str, code: str = "invalid_request") -> dict[str, Any]:
    return {"error": {"message": message, "type": code, "code": code, "status": status}}


def google_error(status: int, message: str, code: str = "INVALID_ARGUMENT") -> dict[str, Any]:
    return {"error": {"code": status, "message": message, "status": code}}
