from __future__ import annotations

import json
import time
from typing import Any

from fastapi import HTTPException, Request, Response

from .db import Database, now_ms
from .security import (
    hash_password,
    hash_token,
    new_id,
    new_session_token,
    verify_password,
)

SESSION_COOKIE_USER = "fd_user"
SESSION_COOKIE_ADMIN = "fd_admin"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600


def _cookie_secure(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def set_session_cookie(response: Response, request: Request, kind: str, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_USER if kind == "user" else SESSION_COOKIE_ADMIN,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, kind: str) -> None:
    response.delete_cookie(
        SESSION_COOKIE_USER if kind == "user" else SESSION_COOKIE_ADMIN,
        path="/",
        httponly=True,
        samesite="lax",
    )


def create_session(db: Database, kind: str, subject_id: str, user_agent: str | None = None) -> str:
    token = new_session_token()
    now = now_ms()
    db.execute(
        "INSERT INTO sessions(token_hash, kind, subject_id, created_at, expires_at, user_agent) VALUES(?, ?, ?, ?, ?, ?)",
        (hash_token(token), kind, subject_id, now, now + SESSION_MAX_AGE_SECONDS * 1000, (user_agent or "")[:400]),
    )
    return token


def resolve_session(db: Database, token: str | None, kind: str) -> dict[str, Any] | None:
    if not token:
        return None
    row = db.fetch_one(
        "SELECT * FROM sessions WHERE token_hash = ? AND kind = ? AND expires_at > ?",
        (hash_token(token), kind, now_ms()),
    )
    if not row:
        return None
    table = "users" if kind == "user" else "backoffice_users"
    subject = db.fetch_one(f"SELECT * FROM {table} WHERE id = ?", (row["subject_id"],))
    if not subject or subject["disabled"]:
        return None
    return dict(subject)


def get_session_token(request: Request, kind: str) -> str | None:
    return request.cookies.get(SESSION_COOKIE_USER if kind == "user" else SESSION_COOKIE_ADMIN)


def session_user(request: Request) -> dict[str, Any] | None:
    db: Database = request.app.state.db
    return resolve_session(db, get_session_token(request, "user"), "user")


def session_admin(request: Request) -> dict[str, Any] | None:
    db: Database = request.app.state.db
    return resolve_session(db, get_session_token(request, "admin"), "admin")


def require_user(request: Request) -> dict[str, Any]:
    user = session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def require_admin(request: Request) -> dict[str, Any]:
    user = session_admin(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录管理后台")
    return user


def require_role_admin(request: Request) -> dict[str, Any]:
    user = require_admin(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def operator_models(db: Database, admin: dict[str, Any]) -> list[str]:
    if admin["role"] == "admin":
        return [row["name"] for row in db.fetch_all("SELECT name FROM models WHERE enabled = 1 ORDER BY sort_order, name")]
    return [
        row["model_name"]
        for row in db.fetch_all(
            "SELECT model_name FROM model_assignments WHERE backoffice_user_id = ? ORDER BY model_name",
            (admin["id"],),
        )
    ]


def admin_payload(db: Database, admin: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": admin["id"],
        "email": admin["email"],
        "name": admin["name"],
        "role": admin["role"],
        "disabled": bool(admin["disabled"]),
        "models": operator_models(db, admin),
        "created_at": admin["created_at"],
        "last_login_at": admin["last_login_at"],
    }


def user_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "disabled": bool(user["disabled"]),
        "created_at": user["created_at"],
        "last_login_at": user["last_login_at"],
    }


def authenticate_user(db: Database, email: str, password: str) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM users WHERE email = ?", (email.strip(),))
    if not row or row["disabled"]:
        # Keep the work factor similar for unknown users by hashing their input.
        verify_password(password, hash_password("invalid-password-placeholder"))
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_ms(), row["id"]))
    refreshed = db.fetch_one("SELECT * FROM users WHERE id = ?", (row["id"],))
    return dict(refreshed) if refreshed else None


def authenticate_admin(db: Database, email: str, password: str) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM backoffice_users WHERE email = ?", (email.strip(),))
    if not row or row["disabled"]:
        verify_password(password, hash_password("invalid-password-placeholder"))
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    db.execute("UPDATE backoffice_users SET last_login_at = ? WHERE id = ?", (now_ms(), row["id"]))
    refreshed = db.fetch_one("SELECT * FROM backoffice_users WHERE id = ?", (row["id"],))
    return dict(refreshed) if refreshed else None


def register_user(db: Database, email: str, name: str, password: str) -> dict[str, Any]:
    email = email.strip().lower()
    name = name.strip()
    now = now_ms()
    uid = new_id("usr")
    db.execute(
        "INSERT INTO users(id, email, name, password_hash, created_at) VALUES(?, ?, ?, ?, ?)",
        (uid, email, name, hash_password(password), now),
    )
    row = db.fetch_one("SELECT * FROM users WHERE id = ?", (uid,))
    assert row is not None
    return dict(row)


def create_backoffice_user(
    db: Database,
    email: str,
    name: str,
    password: str,
    role: str = "operator",
    model_names: list[str] | None = None,
) -> dict[str, Any]:
    uid = new_id("bku")
    db.execute(
        "INSERT INTO backoffice_users(id, email, name, password_hash, role, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        (uid, email.strip().lower(), name.strip(), hash_password(password), role, now_ms()),
    )
    if model_names:
        set_assignments(db, uid, model_names)
    row = db.fetch_one("SELECT * FROM backoffice_users WHERE id = ?", (uid,))
    assert row is not None
    return dict(row)


def set_assignments(db: Database, user_id: str, model_names: list[str]) -> None:
    valid = {
        row["name"]
        for row in db.fetch_all("SELECT name FROM models")
    }
    selected = [name for name in dict.fromkeys(model_names) if name in valid]
    with db.transaction() as conn:
        conn.execute("DELETE FROM model_assignments WHERE backoffice_user_id = ?", (user_id,))
        for name in selected:
            conn.execute(
                "INSERT INTO model_assignments(backoffice_user_id, model_name) VALUES(?, ?)",
                (user_id, name),
            )


def create_api_key(db: Database, user_id: str, name: str) -> tuple[dict[str, Any], str]:
    from .security import new_api_key

    secret, prefix, last_four, key_hash = new_api_key()
    kid = new_id("key")
    db.execute(
        "INSERT INTO api_keys(id, user_id, name, prefix, last_four, key_hash, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (kid, user_id, name.strip()[:80] or "Default key", prefix, last_four, key_hash, now_ms()),
    )
    row = db.fetch_one("SELECT * FROM api_keys WHERE id = ?", (kid,))
    assert row is not None
    return dict(row), secret


def api_key_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "prefix": row["prefix"],
        "last_four": row["last_four"],
        "masked": f"{row['prefix']}…{row['last_four']}",
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
        "revoked_at": row["revoked_at"],
    }
