from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ..auth import (
    api_key_payload,
    authenticate_user,
    clear_session_cookie,
    create_api_key,
    create_session,
    get_session_token,
    register_user,
    require_user,
    session_admin,
    session_user,
    set_session_cookie,
    user_payload,
)
from ..db import now_ms
from ..protocols import (
    ProtocolError,
    build_google_response,
    build_systemone_response,
    estimate_tokens,
    parse_google,
    parse_systemone,
)
from ..schemas import AccountPatchIn, KeyCreateIn, LoginIn, PasswordChangeIn, PlaygroundIn, RegisterIn
from ..security import (
    hash_password,
    validate_email,
    validate_password,
    verify_password,
)
from ..settings import get_all_settings, public_model

router = APIRouter(prefix="/api", tags=["account"])


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_rate(limiter: Any, key: str, detail: str = "操作过于频繁，请稍后再试") -> None:
    if not limiter.hit(key):
        raise HTTPException(status_code=429, detail=detail)


@router.post("/auth/register")
async def register(request: Request, response: Response, payload: RegisterIn) -> dict[str, Any]:
    db = request.app.state.db
    settings = get_all_settings(db)
    if not settings["registration_enabled"]:
        raise HTTPException(status_code=403, detail="当前未开放注册")
    check_rate(request.app.state.register_limiter, client_ip(request))
    email = payload.email.strip().lower()
    error = validate_email(email)
    if error:
        raise HTTPException(status_code=422, detail=error)
    error = validate_password(payload.password)
    if error:
        raise HTTPException(status_code=422, detail=error)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="请输入名称")
    if db.fetch_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    user = register_user(db, email, name, payload.password)
    token = create_session(db, "user", user["id"], request.headers.get("user-agent"))
    set_session_cookie(response, request, "user", token)
    db.audit("user", user["id"], "user.register", user["id"], {"email": email})
    return {"user": user_payload(user)}


@router.post("/auth/login")
async def login(request: Request, response: Response, payload: LoginIn) -> dict[str, Any]:
    db = request.app.state.db
    key = f"{client_ip(request)}:{payload.email.strip().lower()}"
    check_rate(request.app.state.login_limiter, key, "登录尝试过于频繁，请稍后再试")
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码不正确")
    request.app.state.login_limiter.reset(key)
    token = create_session(db, "user", user["id"], request.headers.get("user-agent"))
    set_session_cookie(response, request, "user", token)
    db.audit("user", user["id"], "user.login", user["id"], None)
    return {"user": user_payload(user)}


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = get_session_token(request, "user")
    if token:
        from ..security import hash_token

        request.app.state.db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    clear_session_cookie(response, "user")
    return {"ok": True}


@router.get("/auth/session")
async def session(request: Request) -> dict[str, Any]:
    user = session_user(request)
    admin = session_admin(request)
    return {
        "user": user_payload(user) if user else None,
        "admin": None
        if not admin
        else {
            "id": admin["id"],
            "email": admin["email"],
            "name": admin["name"],
            "role": admin["role"],
        },
    }


@router.get("/account")
async def account(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"user": user_payload(user)}


@router.patch("/account")
async def patch_account(request: Request, payload: AccountPatchIn) -> dict[str, Any]:
    user = require_user(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="请输入名称")
    request.app.state.db.execute("UPDATE users SET name = ? WHERE id = ?", (name, user["id"]))
    updated = request.app.state.db.fetch_one("SELECT * FROM users WHERE id = ?", (user["id"],))
    assert updated is not None
    return {"user": user_payload(dict(updated))}


@router.post("/account/password")
async def change_password(request: Request, payload: PasswordChangeIn) -> dict[str, bool]:
    user = require_user(request)
    if not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=403, detail="当前密码不正确")
    error = validate_password(payload.new_password)
    if error:
        raise HTTPException(status_code=422, detail=error)
    db = request.app.state.db
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), user["id"]))
    db.execute("DELETE FROM sessions WHERE kind = 'user' AND subject_id = ?", (user["id"],))
    db.audit("user", user["id"], "user.password_change", user["id"], None)
    return {"ok": True}


@router.get("/keys")
async def list_keys(request: Request) -> dict[str, Any]:
    user = require_user(request)
    rows = request.app.state.db.fetch_all(
        "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)
    )
    return {"keys": [api_key_payload(dict(row)) for row in rows]}


@router.post("/keys")
async def create_key(request: Request, payload: KeyCreateIn) -> dict[str, Any]:
    user = require_user(request)
    db = request.app.state.db
    count = db.fetch_one(
        "SELECT COUNT(*) AS n FROM api_keys WHERE user_id = ? AND revoked_at IS NULL", (user["id"],)
    )
    if count and count["n"] >= 12:
        raise HTTPException(status_code=400, detail="最多保留 12 个有效 API Key")
    row, secret = create_api_key(db, user["id"], payload.name)
    db.audit("user", user["id"], "key.create", row["id"], {"name": row["name"]})
    return {"key": api_key_payload(row), "secret": secret}


@router.delete("/keys/{key_id}")
async def revoke_key(request: Request, key_id: str) -> dict[str, bool]:
    user = require_user(request)
    db = request.app.state.db
    row = db.fetch_one("SELECT * FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    db.execute("UPDATE api_keys SET revoked_at = ? WHERE id = ?", (now_ms(), key_id))
    db.audit("user", user["id"], "key.revoke", key_id, None)
    return {"ok": True}


@router.get("/account/usage")
async def usage(request: Request, days: int = 30) -> dict[str, Any]:
    user = require_user(request)
    days = max(1, min(365, days))
    since = now_ms() - days * 86400000
    db = request.app.state.db
    totals = db.fetch_one(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status = 'answered' THEN 1 ELSE 0 END) AS answered, "
        "SUM(CASE WHEN status = 'timed_out' THEN 1 ELSE 0 END) AS timed_out, "
        "AVG(CASE WHEN status = 'answered' THEN duration_ms END) AS avg_duration "
        "FROM requests WHERE user_id = ? AND created_at >= ?",
        (user["id"], since),
    )
    by_model = db.fetch_all(
        "SELECT model, COUNT(*) AS n, SUM(CASE WHEN status = 'answered' THEN 1 ELSE 0 END) AS answered "
        "FROM requests WHERE user_id = ? AND created_at >= ? GROUP BY model ORDER BY n DESC",
        (user["id"], since),
    )
    recent_rows = db.fetch_all(
        "SELECT id, model, protocol, status, created_at, duration_ms, auto_filled "
        "FROM requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
        (user["id"],),
    )
    return {
        "days": days,
        "total": totals["total"] if totals else 0,
        "answered": (totals["answered"] or 0) if totals else 0,
        "timed_out": (totals["timed_out"] or 0) if totals else 0,
        "avg_duration_ms": round(totals["avg_duration"] or 0) if totals else 0,
        "by_model": [dict(row) for row in by_model],
        "recent": [dict(row) for row in recent_rows],
    }


@router.get("/console/models")
async def console_models(request: Request) -> dict[str, Any]:
    require_user(request)
    rows = request.app.state.db.fetch_all("SELECT * FROM models WHERE enabled = 1 ORDER BY sort_order, name")
    result = []
    for row in rows:
        item = public_model(row)
        item["protocols"] = ["systemone", "google"] if item["protocol"] == "both" else [item["protocol"]]
        result.append(item)
    return {"models": result}


@router.post("/console/playground")
async def playground(request: Request, payload: PlaygroundIn) -> JSONResponse:
    user = require_user(request)
    db = request.app.state.db
    settings = get_all_settings(db)
    check_rate(request.app.state.playground_limiter, user["id"], "试玩请求过于频繁，请稍后再试")
    active = db.fetch_one(
        "SELECT COUNT(*) AS n FROM requests WHERE user_id = ? AND status IN ('queued', 'assigned')",
        (user["id"],),
    )
    if active and active["n"] >= int(settings["max_pending_per_user"]):
        raise HTTPException(status_code=429, detail="当前排队请求过多，请稍后再试")
    model_row = db.fetch_one("SELECT * FROM models WHERE name = ? AND enabled = 1", (payload.model,))
    if not model_row:
        raise HTTPException(status_code=404, detail="模型不存在或不可用")
    if model_row["protocol"] not in (payload.protocol, "both"):
        raise HTTPException(status_code=400, detail="该模型不支持所选协议")
    allowed = [row["name"] for row in db.fetch_all("SELECT name FROM models WHERE enabled = 1")]
    body: dict[str, Any] = {
        "model": payload.model,
        "questions": payload.questions,
    }
    try:
        if payload.protocol == "systemone":
            body["state"] = payload.input
            parsed = parse_systemone(body, payload.model, allowed)
        else:
            body["input"] = payload.input
            parsed = parse_google(body, payload.model, allowed)
        started = time.monotonic()
        row = await request.app.state.service.create(
            parsed,
            user_id=user["id"],
            api_key_id=None,
            client_ip=client_ip(request),
            requested_timeout_ms=payload.timeout_ms,
            raw_request=body,
        )
        completed = await request.app.state.service.wait(row["id"], int(row["timeout_seconds"]))
        elapsed = int((time.monotonic() - started) * 1000)
        if completed is None:
            return JSONResponse({"detail": "请求不存在"}, status_code=500)
        if completed["status"] == "timed_out":
            return JSONResponse({"detail": "请求超时，未获得回答", "code": "request_timeout"}, status_code=504)
        if completed["status"] == "cancelled":
            return JSONResponse({"detail": "请求已被取消", "code": "request_cancelled"}, status_code=503)
        answers = json.loads(completed["answers_json"]) if completed["answers_json"] else {}
        if payload.protocol == "systemone":
            response = build_systemone_response(parsed.model, parsed, answers, estimate_tokens(parsed))
        else:
            response = build_google_response(parsed, answers)
        return JSONResponse(
            {
                "request_id": completed["id"],
                "protocol": payload.protocol,
                "model": payload.model,
                "response": response,
                "elapsed_ms": elapsed,
            }
        )
    except ProtocolError as exc:
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status)
