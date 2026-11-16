from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from typing import Any, Deque

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..db import now_ms
from ..protocols import (
    MAX_REQUEST_BYTES,
    ProtocolError,
    build_google_response,
    build_systemone_response,
    estimate_tokens,
    google_error,
    parse_google,
    parse_systemone,
    systemone_error,
)
from ..security import bearer_token, hash_token
from ..settings import brand_slug, get_all_settings

router = APIRouter(tags=["decision-api"])


class ApiWindows:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        cutoff = now - 60
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def _error(protocol: str, status: int, message: str, code: str) -> JSONResponse:
    if protocol == "google":
        return JSONResponse(google_error(status, message, code), status_code=status)
    return JSONResponse(systemone_error(status, message, code), status_code=status)


def _api_key_token(request: Request, protocol: str) -> str | None:
    if protocol == "google":
        header = request.headers.get("x-goog-api-key")
        if header:
            return header.strip()
        query_key = request.query_params.get("key")
        if query_key:
            return query_key.strip()
    return bearer_token(request.headers.get("authorization")) or request.headers.get("x-api-key")


def _lookup_key(request: Request, protocol: str) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    token = _api_key_token(request, protocol)
    if not token:
        return None, _error(protocol, 401, "缺少 API Key", "invalid_api_key")
    db = request.app.state.db
    row = db.fetch_one(
        "SELECT k.*, u.disabled AS user_disabled, u.email AS user_email, u.name AS user_name "
        "FROM api_keys k JOIN users u ON u.id = k.user_id WHERE k.key_hash = ?",
        (hash_token(token),),
    )
    if not row:
        return None, _error(protocol, 401, "API Key 无效", "invalid_api_key")
    if row["revoked_at"]:
        return None, _error(protocol, 401, "API Key 已被撤销", "invalid_api_key")
    if row["user_disabled"]:
        return None, _error(protocol, 403, "账号已被停用", "account_disabled")
    settings = get_all_settings(db)
    if not request.app.state.api_windows.allow(f"key:{row['id']}", int(settings["rate_limit_per_minute"])):
        return None, _error(protocol, 429, "请求过于频繁", "rate_limit_exceeded")
    db.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now_ms(), row["id"]))
    return dict(row), None


async def _read_body(request: Request, protocol: str) -> tuple[Any | None, JSONResponse | None]:
    length_header = request.headers.get("content-length")
    if length_header:
        try:
            length = int(length_header)
        except ValueError:
            return None, _error(protocol, 400, "Content-Length 无效", "invalid_request")
        if length > MAX_REQUEST_BYTES:
            return None, _error(protocol, 413, "请求体过大", "request_too_large")
    raw = await request.body()
    if len(raw) > MAX_REQUEST_BYTES:
        return None, _error(protocol, 413, "请求体过大", "request_too_large")
    if not raw:
        return None, _error(protocol, 400, "请求体不能为空", "invalid_request")
    try:
        return json.loads(raw), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _error(protocol, 400, "请求体不是有效 JSON", "invalid_json")


def _timeout_ms(request: Request) -> int | None:
    for header in ("x-decision-timeout-ms", "x-request-timeout-ms", "x-timeout-ms"):
        value = request.headers.get(header)
        if value:
            try:
                return int(value)
            except ValueError:
                return None
    query = request.query_params.get("timeout_ms")
    if query:
        try:
            return int(query)
        except ValueError:
            return None
    return None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _success_headers(request_id: str) -> dict[str, str]:
    return {"X-Request-Id": request_id, "Cache-Control": "no-store"}


async def _handle(request: Request, protocol: str, body: Any, path_model: str | None = None) -> JSONResponse:
    db = request.app.state.db
    key, auth_error = _lookup_key(request, protocol)
    if auth_error:
        return auth_error
    assert key is not None
    settings = get_all_settings(db)
    models = db.fetch_all("SELECT * FROM models WHERE enabled = 1 ORDER BY sort_order, name")
    allowed = [row["name"] for row in models]
    try:
        if protocol == "systemone":
            parsed = parse_systemone(body, models[0]["name"] if models else "jev-latest", allowed)
        else:
            parsed = parse_google(body, models[0]["name"] if models else "gemini-decision-1", allowed, path_model)
        model_row = next((row for row in models if row["name"] == parsed.model), None)
        if not model_row:
            raise ProtocolError(404, "模型不存在或不可用", "model_not_found" if protocol == "systemone" else "NOT_FOUND")
        if model_row["protocol"] not in (protocol, "both"):
            raise ProtocolError(400, "该模型不支持当前接口协议", "unsupported_protocol" if protocol == "systemone" else "INVALID_ARGUMENT")
        active = db.fetch_one(
            "SELECT COUNT(*) AS n FROM requests WHERE user_id = ? AND status IN ('queued', 'assigned')",
            (key["user_id"],),
        )
        if active and active["n"] >= int(settings["max_pending_per_user"]):
            raise ProtocolError(429, "当前排队请求过多，请稍后再试", "rate_limit_exceeded" if protocol == "systemone" else "RESOURCE_EXHAUSTED")
    except ProtocolError as exc:
        return _error(protocol, exc.status, exc.message, exc.code)

    row = await request.app.state.service.create(
        parsed,
        user_id=key["user_id"],
        api_key_id=key["id"],
        client_ip=_client_ip(request),
        requested_timeout_ms=_timeout_ms(request),
        raw_request=body,
    )
    started = time.monotonic()
    completed = await request.app.state.service.wait(row["id"], int(row["timeout_seconds"]))
    elapsed = int((time.monotonic() - started) * 1000)
    if completed is None:
        return _error(protocol, 500, "请求状态丢失", "internal_error")
    if completed["status"] == "timed_out":
        return _error(protocol, 504, "等待人工回答超时", "request_timeout" if protocol == "systemone" else "DEADLINE_EXCEEDED")
    if completed["status"] == "cancelled":
        return _error(protocol, 503, "请求已取消", "request_cancelled" if protocol == "systemone" else "UNAVAILABLE")
    if completed["status"] != "answered":
        return _error(protocol, 500, "请求未完成", "internal_error")
    answers = json.loads(completed["answers_json"]) if completed["answers_json"] else {}
    if protocol == "systemone":
        payload = build_systemone_response(parsed.model, parsed, answers, estimate_tokens(parsed))
    else:
        payload = build_google_response(parsed, answers)
    return JSONResponse(payload, headers=_success_headers(row["id"]))


@router.post("/v1/systemone")
async def systemone(request: Request) -> JSONResponse:
    body, error = await _read_body(request, "systemone")
    if error:
        return error
    return await _handle(request, "systemone", body)


@router.post("/v1beta/decisions")
@router.post("/v1/decisions")
async def google_decisions(request: Request) -> JSONResponse:
    body, error = await _read_body(request, "google")
    if error:
        return error
    return await _handle(request, "google", body)


@router.post("/v1beta/models/{model}:decisions")
async def google_decisions_for_model(request: Request, model: str) -> JSONResponse:
    body, error = await _read_body(request, "google")
    if error:
        return error
    return await _handle(request, "google", body, path_model=model)


@router.get("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    key, error = _lookup_key(request, "systemone")
    if error:
        return error
    db = request.app.state.db
    rows = db.fetch_all("SELECT * FROM models WHERE enabled = 1 AND protocol IN ('systemone', 'both') ORDER BY sort_order, name")
    owner = brand_slug(get_all_settings(db))
    data = [
        {
            "id": row["name"],
            "object": "model",
            "created": int(row["created_at"] / 1000),
            "owned_by": owner,
            "name": row["name"],
            "display_name": row["display_name"],
            "description": row["description"],
            "context_window": row["context_window"],
            "protocols": ["systemone"] + (["google"] if row["protocol"] == "both" else []),
        }
        for row in rows
    ]
    return JSONResponse({"object": "list", "data": data})


@router.get("/v1/models/{model_name}")
async def systemone_model(request: Request, model_name: str) -> JSONResponse:
    _key, error = _lookup_key(request, "systemone")
    if error:
        return error
    db = request.app.state.db
    row = db.fetch_one(
        "SELECT * FROM models WHERE name = ? AND enabled = 1 AND protocol IN ('systemone', 'both')",
        (model_name,),
    )
    if not row:
        return _error("systemone", 404, "模型不存在或不可用", "model_not_found")
    owner = brand_slug(get_all_settings(db))
    return JSONResponse(
        {
            "id": row["name"],
            "object": "model",
            "created": int(row["created_at"] / 1000),
            "owned_by": owner,
            "display_name": row["display_name"],
            "description": row["description"],
            "context_window": row["context_window"],
        }
    )


@router.get("/v1beta/models")
async def google_models(request: Request) -> JSONResponse:
    key, error = _lookup_key(request, "google")
    if error:
        return error
    db = request.app.state.db
    rows = db.fetch_all("SELECT * FROM models WHERE enabled = 1 AND protocol IN ('google', 'both') ORDER BY sort_order, name")
    data = [
        {
            "name": f"models/{row['name']}",
            "displayName": row["display_name"],
            "description": row["description"],
            "inputTokenLimit": row["context_window"],
            "supportedGenerationMethods": ["decisions"],
            "version": "001",
        }
        for row in rows
    ]
    return JSONResponse({"models": data})


@router.get("/v1beta/models/{model_name}")
async def google_model(request: Request, model_name: str) -> JSONResponse:
    _key, error = _lookup_key(request, "google")
    if error:
        return error
    name = model_name.removeprefix("models/")
    row = request.app.state.db.fetch_one(
        "SELECT * FROM models WHERE name = ? AND enabled = 1 AND protocol IN ('google', 'both')",
        (name,),
    )
    if not row:
        return _error("google", 404, "模型不存在或不可用", "NOT_FOUND")
    return JSONResponse(
        {
            "name": f"models/{row['name']}",
            "displayName": row["display_name"],
            "description": row["description"],
            "inputTokenLimit": row["context_window"],
            "supportedGenerationMethods": ["decisions"],
            "version": "001",
        }
    )
