from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from .. import __version__
from ..auth import (
    admin_payload,
    authenticate_admin,
    clear_session_cookie,
    create_backoffice_user,
    create_session,
    get_session_token,
    operator_models,
    require_admin,
    require_role_admin,
    session_admin,
    set_assignments,
    set_session_cookie,
    user_payload,
)
from ..db import now_ms
from ..protocols import ProtocolError
from ..schemas import (
    AdminLoginIn,
    AssignIn,
    AnswerIn,
    DraftIn,
    ModelCreateIn,
    ModelPatchIn,
    OperatorCreateIn,
    OperatorPatchIn,
    PasswordChangeIn,
    RandomizeIn,
    SettingsIn,
    UserPatchIn,
)
from ..security import (
    hash_password,
    new_id,
    validate_email,
    validate_password,
    verify_password,
)
from ..settings import (
    get_all_settings,
    public_model,
    save_settings,
    validate_model_name,
    validate_setting_updates,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _scope_for(request: Request, admin: dict[str, Any]) -> tuple[str, list[Any]]:
    if admin["role"] == "admin":
        return "1=1", []
    models = operator_models(request.app.state.db, admin)
    if not models:
        return "1=0", []
    placeholders = ",".join("?" for _ in models)
    return f"r.model IN ({placeholders})", list(models)


def _can_see(request: Request, admin: dict[str, Any], model: str) -> bool:
    if admin["role"] == "admin":
        return True
    return model in operator_models(request.app.state.db, admin)


def _today_start_ms() -> int:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000)


def _serialize(request: Request, row: Any, admin: dict[str, Any], detail: bool) -> dict[str, Any]:
    return request.app.state.service.serialize_request(
        row, detail=detail, include_private=admin["role"] == "admin"
    )


def _get_visible_request(request: Request, admin: dict[str, Any], request_id: str) -> dict[str, Any]:
    row = request.app.state.service.get_request(request_id)
    if not row or not _can_see(request, admin, row["model"]):
        raise HTTPException(status_code=404, detail="请求不存在")
    return row


# --------------------------------------------------------------------- auth
@router.post("/auth/login")
async def login(request: Request, response: Response, payload: AdminLoginIn) -> dict[str, Any]:
    db = request.app.state.db
    key = f"admin:{_client_ip(request)}:{payload.email.strip().lower()}"
    if not request.app.state.login_limiter.hit(key):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")
    admin = authenticate_admin(db, payload.email, payload.password)
    if not admin:
        raise HTTPException(status_code=401, detail="邮箱或密码不正确")
    request.app.state.login_limiter.reset(key)
    token = create_session(db, "admin", admin["id"], request.headers.get("user-agent"))
    set_session_cookie(response, request, "admin", token)
    db.audit("admin", admin["id"], "admin.login", admin["id"], {"role": admin["role"]})
    return {"admin": admin_payload(db, admin)}


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = get_session_token(request, "admin")
    if token:
        from ..security import hash_token

        request.app.state.db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    clear_session_cookie(response, "admin")
    return {"ok": True}


@router.get("/auth/session")
async def session(request: Request) -> dict[str, Any]:
    admin = session_admin(request)
    db = request.app.state.db
    return {"admin": admin_payload(db, admin) if admin else None, "version": __version__}


@router.get("/me")
async def me(request: Request) -> dict[str, Any]:
    admin = require_admin(request)
    return {"admin": admin_payload(request.app.state.db, admin)}


@router.post("/account/password")
async def change_password(request: Request, payload: PasswordChangeIn) -> dict[str, bool]:
    admin = require_admin(request)
    db = request.app.state.db
    if not verify_password(payload.current_password, admin["password_hash"]):
        raise HTTPException(status_code=403, detail="当前密码不正确")
    error = validate_password(payload.new_password)
    if error:
        raise HTTPException(status_code=422, detail=error)
    db.execute("UPDATE backoffice_users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), admin["id"]))
    db.execute("DELETE FROM sessions WHERE kind = 'admin' AND subject_id = ?", (admin["id"],))
    db.audit("admin", admin["id"], "admin.password_change", admin["id"], None)
    return {"ok": True}


# ----------------------------------------------------------------- overview
@router.get("/overview")
async def overview(request: Request) -> dict[str, Any]:
    admin = require_admin(request)
    db = request.app.state.db
    where, params = _scope_for(request, admin)
    today = _today_start_ms()
    status_rows = db.fetch_all(f"SELECT status, COUNT(*) AS n FROM requests r WHERE {where} GROUP BY status", params)
    status = {row["status"]: row["n"] for row in status_rows}
    today_row = db.fetch_one(
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN status = 'answered' THEN 1 ELSE 0 END) AS answered, "
        f"SUM(CASE WHEN auto_filled = 1 THEN 1 ELSE 0 END) AS auto_filled, "
        f"SUM(CASE WHEN status = 'timed_out' THEN 1 ELSE 0 END) AS timed_out "
        f"FROM requests r WHERE {where} AND created_at >= ?",
        [*params, today],
    )
    avg_row = db.fetch_one(
        f"SELECT AVG(duration_ms) AS avg FROM requests r WHERE {where} AND status = 'answered' AND created_at >= ?",
        [*params, today],
    )
    models_rows = db.fetch_all(
        f"SELECT r.model, COUNT(*) AS n FROM requests r WHERE {where} AND r.created_at >= ? GROUP BY r.model ORDER BY n DESC",
        [*params, today],
    )
    all_models = db.fetch_all("SELECT * FROM models ORDER BY sort_order, name")
    model_counts = {row["model"]: row["n"] for row in models_rows}
    operators = db.fetch_all("SELECT id, name, role, last_assigned_at FROM backoffice_users WHERE disabled = 0")
    online = request.app.state.hub.online_ids()
    online_operators = [
        {"id": row["id"], "name": row["name"], "role": row["role"]}
        for row in operators
        if row["id"] in online
    ]
    recent_rows = db.fetch_all(
        request.app.state.service.base_select()
        + f" WHERE {where} ORDER BY r.created_at DESC LIMIT 8",
        params,
    )
    oldest_row = db.fetch_one(
        f"SELECT MIN(created_at) AS oldest FROM requests r WHERE {where} AND r.status IN ('queued', 'assigned')",
        params,
    )
    return {
        "status_counts": status,
        "active": status.get("queued", 0) + status.get("assigned", 0),
        "queued": status.get("queued", 0),
        "assigned": status.get("assigned", 0),
        "today": {
            "total": today_row["total"] if today_row else 0,
            "answered": (today_row["answered"] or 0) if today_row else 0,
            "auto_filled": (today_row["auto_filled"] or 0) if today_row else 0,
            "timed_out": (today_row["timed_out"] or 0) if today_row else 0,
        },
        "average_duration_ms": round(avg_row["avg"] or 0) if avg_row else 0,
        "oldest_pending_ms": max(0, now_ms() - oldest_row["oldest"]) if oldest_row and oldest_row["oldest"] else 0,
        "models": [
            {
                **public_model(row),
                "today": model_counts.get(row["name"], 0),
            }
            for row in all_models
        ],
        "online_operators": online_operators,
        "recent": [_serialize(request, row, admin, False) for row in recent_rows],
        "server_time": now_ms(),
    }


# ----------------------------------------------------------------- requests
@router.get("/requests")
async def list_requests(
    request: Request,
    view: str = Query("active", pattern="^(active|history|all)$"),
    status: str | None = None,
    model: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    admin = require_admin(request)
    db = request.app.state.db
    where, params = _scope_for(request, admin)
    clauses = [where]
    if view == "active":
        clauses.append("r.status IN ('queued', 'assigned')")
    elif view == "history":
        clauses.append("r.status IN ('answered', 'timed_out', 'cancelled')")
    if status:
        if status not in {"queued", "assigned", "answered", "timed_out", "cancelled", "active"}:
            raise HTTPException(status_code=422, detail="无效的状态筛选")
        if status == "active":
            clauses.append("r.status IN ('queued', 'assigned')")
        else:
            clauses.append("r.status = ?")
            params.append(status)
    if model:
        clauses.append("r.model = ?")
        params.append(model)
    if q:
        clauses.append("(r.id LIKE ? OR r.input_text LIKE ? OR r.model LIKE ?)")
        needle = f"%{q.strip()}%"
        params.extend([needle, needle, needle])
    where_sql = " AND ".join(clauses)
    order = "r.created_at ASC" if view == "active" else "r.created_at DESC"
    count_row = db.fetch_one(f"SELECT COUNT(*) AS n FROM requests r WHERE {where_sql}", params)
    rows = db.fetch_all(
        request.app.state.service.base_select()
        + f" WHERE {where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return {
        "requests": [_serialize(request, row, admin, False) for row in rows],
        "total": count_row["n"] if count_row else 0,
        "limit": limit,
        "offset": offset,
        "server_time": now_ms(),
    }


@router.get("/requests/{request_id}")
async def request_detail(request: Request, request_id: str) -> dict[str, Any]:
    admin = require_admin(request)
    row = _get_visible_request(request, admin, request_id)
    return {"request": _serialize(request, row, admin, True), "server_time": now_ms()}


@router.post("/requests/{request_id}/answer")
async def answer_request(request: Request, request_id: str, payload: AnswerIn) -> dict[str, Any]:
    admin = require_admin(request)
    row = _get_visible_request(request, admin, request_id)
    if row["status"] not in {"queued", "assigned"}:
        raise HTTPException(status_code=409, detail="该请求已结束")
    try:
        completed = await request.app.state.service.submit(
            request_id,
            payload.answers,
            answered_by=admin["id"],
            actor_kind="admin" if admin["role"] == "admin" else "operator",
        )
    except ProtocolError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    if not completed:
        raise HTTPException(status_code=404, detail="请求不存在")
    if completed["status"] != "answered":
        raise HTTPException(status_code=409, detail="该请求已被系统结束")
    if completed.get("auto_filled"):
        raise HTTPException(status_code=409, detail="该请求已由系统自动补全")
    fresh = request.app.state.service.get_request(request_id)
    return {"request": _serialize(request, fresh, admin, True) if fresh else completed}


@router.put("/requests/{request_id}/draft")
async def save_draft(request: Request, request_id: str, payload: DraftIn) -> dict[str, Any]:
    admin = require_admin(request)
    _get_visible_request(request, admin, request_id)
    fresh = request.app.state.service.save_draft(request_id, payload.answers)
    if not fresh:
        raise HTTPException(status_code=404, detail="请求不存在")
    return {"draft": fresh.get("draft_json") and json.loads(fresh["draft_json"]) or {}}


@router.post("/requests/{request_id}/randomize")
async def randomize(request: Request, request_id: str, payload: RandomizeIn) -> dict[str, Any]:
    admin = require_admin(request)
    _get_visible_request(request, admin, request_id)
    try:
        answers = request.app.state.service.randomize(request_id, payload.question_ids)
    except ProtocolError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return {"answers": answers}


@router.put("/requests/{request_id}/assign")
async def assign(request: Request, request_id: str, payload: AssignIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    _get_visible_request(request, admin, request_id)
    if payload.operator_id:
        operator = request.app.state.db.fetch_one(
            "SELECT * FROM backoffice_users WHERE id = ? AND disabled = 0", (payload.operator_id,)
        )
        if not operator:
            raise HTTPException(status_code=404, detail="后台用户不存在")
    updated = request.app.state.service.assign_request(request_id, payload.operator_id, admin)
    if not updated:
        raise HTTPException(status_code=404, detail="请求不存在")
    return {"request": _serialize(request, updated, admin, True)}


@router.post("/requests/{request_id}/cancel")
async def cancel(request: Request, request_id: str) -> dict[str, Any]:
    admin = require_role_admin(request)
    _get_visible_request(request, admin, request_id)
    updated = await request.app.state.service.cancel(request_id, admin["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="请求不存在")
    return {"request": _serialize(request, updated, admin, True)}


# ---------------------------------------------------------------- operators
@router.get("/operators")
async def list_operators(request: Request) -> dict[str, Any]:
    require_role_admin(request)
    db = request.app.state.db
    rows = db.fetch_all("SELECT * FROM backoffice_users ORDER BY created_at")
    assignments: dict[str, list[str]] = {}
    for row in db.fetch_all("SELECT backoffice_user_id, model_name FROM model_assignments ORDER BY model_name"):
        assignments.setdefault(row["backoffice_user_id"], []).append(row["model_name"])
    counts = {
        row["assigned_to"]: row["n"]
        for row in db.fetch_all(
            "SELECT assigned_to, COUNT(*) AS n FROM requests WHERE status IN ('queued', 'assigned') AND assigned_to IS NOT NULL GROUP BY assigned_to"
        )
    }
    online = request.app.state.hub.online_ids()
    return {
        "operators": [
            {
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "role": row["role"],
                "disabled": bool(row["disabled"]),
                "created_at": row["created_at"],
                "last_login_at": row["last_login_at"],
                "last_assigned_at": row["last_assigned_at"],
                "models": assignments.get(row["id"], []),
                "online": row["id"] in online,
                "active_requests": counts.get(row["id"], 0),
            }
            for row in rows
        ]
    }


@router.post("/operators")
async def create_operator(request: Request, payload: OperatorCreateIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    db = request.app.state.db
    email = payload.email.strip().lower()
    error = validate_email(email)
    if error:
        raise HTTPException(status_code=422, detail=error)
    error = validate_password(payload.password)
    if error:
        raise HTTPException(status_code=422, detail=error)
    if db.fetch_one("SELECT id FROM backoffice_users WHERE email = ?", (email,)):
        raise HTTPException(status_code=409, detail="该邮箱已存在")
    operator = create_backoffice_user(db, email, payload.name, payload.password, role="operator", model_names=payload.models)
    db.audit("admin", admin["id"], "operator.create", operator["id"], {"email": email, "models": payload.models})
    return {"operator": {**{k: operator[k] for k in ("id", "email", "name", "role", "created_at")}, "models": payload.models, "disabled": False, "online": False}}


@router.patch("/operators/{operator_id}")
async def patch_operator(request: Request, operator_id: str, payload: OperatorPatchIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    db = request.app.state.db
    row = db.fetch_one("SELECT * FROM backoffice_users WHERE id = ?", (operator_id,))
    if not row:
        raise HTTPException(status_code=404, detail="后台用户不存在")
    if row["role"] == "admin":
        raise HTTPException(status_code=400, detail="不能在后台用户列表中修改管理员")
    if operator_id == admin["id"] and payload.disabled:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    updates: list[str] = []
    values: list[Any] = []
    if payload.name is not None:
        updates.append("name = ?")
        values.append(payload.name.strip())
    if payload.disabled is not None:
        updates.append("disabled = ?")
        values.append(1 if payload.disabled else 0)
    if payload.password is not None:
        error = validate_password(payload.password)
        if error:
            raise HTTPException(status_code=422, detail=error)
        updates.append("password_hash = ?")
        values.append(hash_password(payload.password))
    if updates:
        db.execute(f"UPDATE backoffice_users SET {', '.join(updates)} WHERE id = ?", [*values, operator_id])
    if payload.models is not None:
        set_assignments(db, operator_id, payload.models)
    if payload.disabled:
        db.execute("DELETE FROM sessions WHERE kind = 'admin' AND subject_id = ?", (operator_id,))
        active = db.fetch_all(
            "SELECT id FROM requests WHERE assigned_to = ? AND status IN ('queued', 'assigned')", (operator_id,)
        )
        for active_row in active:
            db.execute(
                "UPDATE requests SET status = 'queued', assigned_to = NULL WHERE id = ? AND status IN ('queued', 'assigned')",
                (active_row["id"],),
            )
            fresh = request.app.state.service.get_request(active_row["id"])
            if fresh:
                await request.app.state.service.hub.publish(
                    {"type": "request.assigned", "data": {"request": request.app.state.service.serialize_request(fresh)}},
                    model=fresh["model"],
                )
    db.audit("admin", admin["id"], "operator.update", operator_id, payload.model_dump(exclude_unset=True, exclude={"password"}))
    fresh_row = db.fetch_one("SELECT * FROM backoffice_users WHERE id = ?", (operator_id,))
    assert fresh_row is not None
    model_names = [r["model_name"] for r in db.fetch_all("SELECT model_name FROM model_assignments WHERE backoffice_user_id = ?", (operator_id,))]
    return {
        "operator": {
            "id": fresh_row["id"],
            "email": fresh_row["email"],
            "name": fresh_row["name"],
            "role": fresh_row["role"],
            "disabled": bool(fresh_row["disabled"]),
            "created_at": fresh_row["created_at"],
            "last_login_at": fresh_row["last_login_at"],
            "last_assigned_at": fresh_row["last_assigned_at"],
            "models": model_names,
            "online": request.app.state.hub.is_online(operator_id),
            "active_requests": 0,
        }
    }


# ------------------------------------------------------------------- users
@router.get("/users")
async def list_users(
    request: Request,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    require_role_admin(request)
    db = request.app.state.db
    clauses = ["1=1"]
    params: list[Any] = []
    if q:
        clauses.append("(u.email LIKE ? OR u.name LIKE ?)")
        needle = f"%{q.strip()}%"
        params.extend([needle, needle])
    where = " AND ".join(clauses)
    total = db.fetch_one(f"SELECT COUNT(*) AS n FROM users u WHERE {where}", params)
    rows = db.fetch_all(
        f"SELECT u.*, (SELECT COUNT(*) FROM requests r WHERE r.user_id = u.id) AS request_count, "
        f"(SELECT MAX(r.created_at) FROM requests r WHERE r.user_id = u.id) AS last_request_at "
        f"FROM users u WHERE {where} ORDER BY u.created_at DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return {
        "users": [
            {
                **user_payload(dict(row)),
                "request_count": row["request_count"],
                "last_request_at": row["last_request_at"],
            }
            for row in rows
        ],
        "total": total["n"] if total else 0,
    }


@router.get("/users/{user_id}")
async def user_detail(request: Request, user_id: str) -> dict[str, Any]:
    require_role_admin(request)
    db = request.app.state.db
    user = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    usage = db.fetch_all(
        "SELECT model, COUNT(*) AS n FROM requests WHERE user_id = ? GROUP BY model ORDER BY n DESC",
        (user_id,),
    )
    keys = db.fetch_all("SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    recent = db.fetch_all(
        "SELECT id, model, protocol, status, created_at, duration_ms, auto_filled FROM requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (user_id,),
    )
    return {
        "user": user_payload(dict(user)),
        "usage": [dict(row) for row in usage],
        "keys": [
            {"id": row["id"], "name": row["name"], "prefix": row["prefix"], "last_four": row["last_four"], "created_at": row["created_at"], "last_used_at": row["last_used_at"], "revoked_at": row["revoked_at"]}
            for row in keys
        ],
        "recent": [dict(row) for row in recent],
    }


@router.patch("/users/{user_id}")
async def patch_user(request: Request, user_id: str, payload: UserPatchIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    db = request.app.state.db
    row = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    updates: list[str] = []
    values: list[Any] = []
    if payload.name is not None:
        updates.append("name = ?")
        values.append(payload.name.strip())
    if payload.disabled is not None:
        updates.append("disabled = ?")
        values.append(1 if payload.disabled else 0)
        if payload.disabled:
            db.execute("DELETE FROM sessions WHERE kind = 'user' AND subject_id = ?", (user_id,))
    if payload.password is not None:
        error = validate_password(payload.password)
        if error:
            raise HTTPException(status_code=422, detail=error)
        updates.append("password_hash = ?")
        values.append(hash_password(payload.password))
        db.execute("DELETE FROM sessions WHERE kind = 'user' AND subject_id = ?", (user_id,))
    if updates:
        db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", [*values, user_id])
    db.audit("admin", admin["id"], "user.update", user_id, payload.model_dump(exclude_unset=True, exclude={"password"}))
    fresh = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    assert fresh is not None
    return {"user": user_payload(dict(fresh))}


# ------------------------------------------------------------------ models
@router.get("/models")
async def list_models(request: Request) -> dict[str, Any]:
    require_admin(request)
    db = request.app.state.db
    rows = db.fetch_all("SELECT * FROM models ORDER BY sort_order, name")
    counts = {
        row["model_name"]: row["n"]
        for row in db.fetch_all("SELECT model_name, COUNT(*) AS n FROM model_assignments GROUP BY model_name")
    }
    return {
        "models": [
            {
                **public_model(row),
                "assigned_count": counts.get(row["name"], 0),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    }


@router.post("/models")
async def create_model(request: Request, payload: ModelCreateIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    db = request.app.state.db
    error = validate_model_name(payload.name)
    if error:
        raise HTTPException(status_code=422, detail=error)
    if db.fetch_one("SELECT id FROM models WHERE name = ?", (payload.name,)):
        raise HTTPException(status_code=409, detail="模型名已存在")
    model_id = new_id("mdl")
    db.execute(
        "INSERT INTO models(id, name, display_name, protocol, description, context_window, enabled, sort_order, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            model_id,
            payload.name,
            payload.display_name.strip(),
            payload.protocol,
            payload.description.strip(),
            payload.context_window,
            1 if payload.enabled else 0,
            payload.sort_order,
            now_ms(),
        ),
    )
    db.audit("admin", admin["id"], "model.create", model_id, {"name": payload.name})
    row = db.fetch_one("SELECT * FROM models WHERE id = ?", (model_id,))
    assert row is not None
    return {"model": {**public_model(row), "assigned_count": 0, "created_at": row["created_at"]}}


@router.patch("/models/{model_id}")
async def patch_model(request: Request, model_id: str, payload: ModelPatchIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    db = request.app.state.db
    row = db.fetch_one("SELECT * FROM models WHERE id = ?", (model_id,))
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    values = payload.model_dump(exclude_unset=True, exclude={"name"})
    if payload.name is not None and payload.name != row["name"]:
        error = validate_model_name(payload.name)
        if error:
            raise HTTPException(status_code=422, detail=error)
        if db.fetch_one("SELECT id FROM models WHERE name = ? AND id != ?", (payload.name, model_id)):
            raise HTTPException(status_code=409, detail="模型名已存在")
        with db.transaction() as conn:
            conn.execute("UPDATE models SET name = ? WHERE id = ?", (payload.name, model_id))
            conn.execute("UPDATE model_assignments SET model_name = ? WHERE model_name = ?", (payload.name, row["name"]))
    if "enabled" in values and not values["enabled"]:
        enabled = db.fetch_one("SELECT COUNT(*) AS n FROM models WHERE enabled = 1 AND id != ?", (model_id,))
        if enabled and enabled["n"] == 0:
            raise HTTPException(status_code=400, detail="至少需要保留一个启用的模型")
    updates: list[str] = []
    params: list[Any] = []
    for key in ("display_name", "protocol", "description", "context_window", "enabled", "sort_order"):
        if key in values:
            updates.append(f"{key} = ?")
            params.append(1 if key == "enabled" and values[key] else values[key] if key != "enabled" else 0)
    if updates:
        db.execute(f"UPDATE models SET {', '.join(updates)} WHERE id = ?", [*params, model_id])
    db.audit("admin", admin["id"], "model.update", model_id, payload.model_dump(exclude_unset=True))
    fresh = db.fetch_one("SELECT * FROM models WHERE id = ?", (model_id,))
    assert fresh is not None
    return {"model": public_model(fresh)}


@router.delete("/models/{model_id}")
async def delete_model(request: Request, model_id: str) -> dict[str, bool]:
    admin = require_role_admin(request)
    db = request.app.state.db
    row = db.fetch_one("SELECT * FROM models WHERE id = ?", (model_id,))
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    used = db.fetch_one("SELECT COUNT(*) AS n FROM requests WHERE model = ?", (row["name"],))
    if used and used["n"]:
        raise HTTPException(status_code=409, detail="该模型已有历史请求，只能停用")
    with db.transaction() as conn:
        if row["enabled"]:
            enabled = conn.execute("SELECT COUNT(*) AS n FROM models WHERE enabled = 1 AND id != ?", (model_id,)).fetchone()
            if enabled and enabled["n"] == 0:
                raise HTTPException(status_code=400, detail="至少需要保留一个启用的模型")
        conn.execute("DELETE FROM model_assignments WHERE model_name = ?", (row["name"],))
        conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
    db.audit("admin", admin["id"], "model.delete", model_id, {"name": row["name"]})
    return {"ok": True}


# ---------------------------------------------------------------- settings
@router.get("/settings")
async def settings_get(request: Request) -> dict[str, Any]:
    require_role_admin(request)
    db = request.app.state.db
    return {
        "values": get_all_settings(db),
        "version": __version__,
        "limits": {
            "request_timeout_seconds": [15, 900],
            "timeout_fill_lead_seconds": [2, 120],
            "max_pending_per_user": [1, 500],
            "rate_limit_per_minute": [1, 10000],
        },
    }


@router.put("/settings")
async def settings_put(request: Request, payload: SettingsIn) -> dict[str, Any]:
    admin = require_role_admin(request)
    db = request.app.state.db
    clean, errors = validate_setting_updates(payload.values)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    merged = get_all_settings(db)
    merged.update(clean)
    if int(merged["timeout_fill_lead_seconds"]) >= int(merged["request_timeout_seconds"]):
        raise HTTPException(status_code=422, detail="自动补全提前量必须小于请求超时时间")
    save_settings(db, clean)
    db.audit("admin", admin["id"], "settings.update", None, {"keys": sorted(clean)})
    return {"values": get_all_settings(db)}


# ------------------------------------------------------------------- audit
@router.get("/audit")
async def audit_log(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    require_role_admin(request)
    db = request.app.state.db
    total = db.fetch_one("SELECT COUNT(*) AS n FROM audit_logs")
    rows = db.fetch_all(
        "SELECT a.*, b.name AS admin_name FROM audit_logs a LEFT JOIN backoffice_users b ON b.id = a.actor_id "
        "ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return {
        "logs": [
            {
                "id": row["id"],
                "actor_kind": row["actor_kind"],
                "actor_id": row["actor_id"],
                "actor_name": row["admin_name"] or row["actor_kind"],
                "action": row["action"],
                "target": row["target"],
                "detail": json.loads(row["detail"]) if row["detail"] else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ],
        "total": total["n"] if total else 0,
    }


@router.get("/export/requests")
async def export_requests(request: Request) -> Response:
    admin = require_role_admin(request)
    db = request.app.state.db
    where, params = _scope_for(request, admin)
    rows = db.fetch_all(
        request.app.state.service.base_select() + f" WHERE {where} ORDER BY r.created_at DESC LIMIT 10000",
        params,
    )
    data = [request.app.state.service.serialize_request(row, detail=True, include_private=True) for row in rows]
    encoded = json.dumps({"exported_at": now_ms(), "requests": data}, ensure_ascii=False, indent=2)
    return Response(
        encoded,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="fakedecision-requests.json"'},
    )


@router.get("/presence")
async def presence(request: Request) -> dict[str, Any]:
    admin = require_admin(request)
    db = request.app.state.db
    rows = db.fetch_all("SELECT id, name, role, last_assigned_at FROM backoffice_users WHERE disabled = 0")
    online = request.app.state.hub.online_ids()
    return {
        "operators": [
            {
                "id": row["id"],
                "name": row["name"],
                "role": row["role"],
                "online": row["id"] in online,
                "last_assigned_at": row["last_assigned_at"],
            }
            for row in rows
        ],
        "me": admin["id"],
    }
