from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from .db import Database, now_ms
from .protocols import (
    ParsedRequest,
    ProtocolError,
    estimate_tokens,
    merge_partial,
    normalize_answers,
)
from .randomize import randomize_answers
from .realtime import RealtimeHub
from .settings import get_all_settings

ACTIVE_STATUSES = ("queued", "assigned")
DEFAULT_TIMEOUT_SECONDS = 120


@dataclass(slots=True)
class PendingRequest:
    id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    monitor: asyncio.Task[None] | None = None
    created_at: int = field(default_factory=now_ms)


def _json_load(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _input_kind(raw: str | None) -> str:
    value = _json_load(raw, None)
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        kinds = {item.get("type") for item in value if isinstance(item, dict) and item.get("type")}
        return "multimodal" if kinds - {"text"} else "text"
    return "structured"


class RequestService:
    def __init__(self, db: Database, hub: RealtimeHub):
        self.db = db
        self.hub = hub
        self._pending: dict[str, PendingRequest] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ helpers
    def settings(self) -> dict[str, Any]:
        return get_all_settings(self.db)

    def default_model(self) -> str | None:
        row = self.db.fetch_one("SELECT name FROM models WHERE enabled = 1 ORDER BY sort_order, name LIMIT 1")
        return row["name"] if row else None

    def enabled_models(self) -> list[str]:
        return [row["name"] for row in self.db.fetch_all("SELECT name FROM models WHERE enabled = 1 ORDER BY sort_order, name")]

    def _timeout_seconds(self, requested_ms: int | None) -> int:
        settings = self.settings()
        default = int(settings.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        if requested_ms is None:
            return max(5, min(900, default))
        try:
            requested = int(requested_ms) / 1000.0
        except (TypeError, ValueError):
            return max(5, min(900, default))
        return max(3, min(900, int(round(requested))))

    def _query_request(self, request_id: str) -> Any:
        return self.db.fetch_one(
            """
            SELECT r.*, a.name AS assigned_name, b.name AS answered_name, u.email AS user_email, u.name AS user_name
            FROM requests r
            LEFT JOIN backoffice_users a ON a.id = r.assigned_to
            LEFT JOIN backoffice_users b ON b.id = r.answered_by
            LEFT JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
            """,
            (request_id,),
        )

    def base_select(self) -> str:
        return """
            SELECT r.*, a.name AS assigned_name, b.name AS answered_name, u.email AS user_email, u.name AS user_name
            FROM requests r
            LEFT JOIN backoffice_users a ON a.id = r.assigned_to
            LEFT JOIN backoffice_users b ON b.id = r.answered_by
            LEFT JOIN users u ON u.id = r.user_id
        """

    # --------------------------------------------------------------- assignment
    def get_request(self, request_id: str) -> dict[str, Any] | None:
        row = self._query_request(request_id)
        return dict(row) if row else None

    def _admin_models(self, admin: dict[str, Any]) -> set[str]:
        if admin["role"] == "admin":
            return set(self.enabled_models())
        return {
            row["model_name"]
            for row in self.db.fetch_all(
                "SELECT model_name FROM model_assignments WHERE backoffice_user_id = ?",
                (admin["id"],),
            )
        }

    def _pick_admin(self, model: str) -> dict[str, Any] | None:
        online = self.hub.online_ids()
        if not online:
            return None
        settings = self.settings()
        admin_receive_all = bool(settings.get("admin_receive_all", True))
        rows = self.db.fetch_all("SELECT * FROM backoffice_users WHERE disabled = 0")
        assignments: dict[str, set[str]] = {}
        for row in self.db.fetch_all("SELECT backoffice_user_id, model_name FROM model_assignments"):
            assignments.setdefault(row["backoffice_user_id"], set()).add(row["model_name"])
        candidates: list[dict[str, Any]] = []
        for row in rows:
            if row["id"] not in online:
                continue
            if row["role"] == "admin":
                if not admin_receive_all:
                    continue
            elif model not in assignments.get(row["id"], set()):
                continue
            candidates.append(dict(row))
        if not candidates:
            return None
        counts = {
            row["assigned_to"]: row["n"]
            for row in self.db.fetch_all(
                "SELECT assigned_to, COUNT(*) AS n FROM requests WHERE status IN ('queued', 'assigned') AND assigned_to IS NOT NULL GROUP BY assigned_to"
            )
        }
        candidates.sort(key=lambda row: (counts.get(row["id"], 0), row["last_assigned_at"] or 0, row["created_at"]))
        chosen = candidates[0]
        self.db.execute(
            "UPDATE backoffice_users SET last_assigned_at = ? WHERE id = ?",
            (now_ms(), chosen["id"]),
        )
        return chosen

    def _assign_in_transaction(self, conn: Any, request_id: str, admin_id: str) -> bool:
        cur = conn.execute(
            "UPDATE requests SET status = 'assigned', assigned_to = ? WHERE id = ? AND status = 'queued'",
            (admin_id, request_id),
        )
        return cur.rowcount > 0

    def assign_request(self, request_id: str, admin_id: str | None, actor: dict[str, Any] | None = None) -> dict[str, Any] | None:
        row = self._query_request(request_id)
        if not row:
            return None
        if row["status"] not in ACTIVE_STATUSES:
            return dict(row)
        if admin_id is None:
            self.db.execute(
                "UPDATE requests SET status = 'queued', assigned_to = NULL WHERE id = ? AND status IN ('queued', 'assigned')",
                (request_id,),
            )
        else:
            self.db.execute(
                "UPDATE requests SET status = 'assigned', assigned_to = ? WHERE id = ? AND status IN ('queued', 'assigned')",
                (admin_id, request_id),
            )
        updated = self._query_request(request_id)
        if updated:
            self._publish_request("request.assigned", updated)
            if actor:
                self.db.audit("admin", actor.get("id"), "request.assign", request_id, {"assigned_to": admin_id})
        return dict(updated) if updated else None

    async def assign_queued_for(self, admin: dict[str, Any]) -> int:
        models = self._admin_models(admin)
        if not models:
            return 0
        placeholders = ",".join("?" for _ in models)
        rows = self.db.fetch_all(
            f"SELECT * FROM requests WHERE status = 'queued' AND model IN ({placeholders}) AND deadline_at > ? ORDER BY created_at ASC LIMIT 50",
            (*models, now_ms()),
        )
        count = 0
        for row in rows:
            if self.db.execute(
                "UPDATE requests SET status = 'assigned', assigned_to = ? WHERE id = ? AND status = 'queued'",
                (admin["id"], row["id"]),
            ):
                self.db.execute(
                    "UPDATE backoffice_users SET last_assigned_at = ? WHERE id = ?",
                    (now_ms(), admin["id"]),
                )
                updated = self._query_request(row["id"])
                if updated:
                    self._publish_request("request.assigned", updated)
                    count += 1
        return count

    async def handle_disconnect(self, admin_id: str) -> None:
        if self.hub.is_online(admin_id):
            return
        rows = self.db.fetch_all(
            "SELECT * FROM requests WHERE assigned_to = ? AND status IN ('queued', 'assigned') AND deadline_at > ?",
            (admin_id, now_ms()),
        )
        for row in rows:
            self.db.execute(
                "UPDATE requests SET status = 'queued', assigned_to = NULL WHERE id = ? AND status IN ('queued', 'assigned')",
                (row["id"],),
            )
            replacement = self._pick_admin(row["model"])
            if replacement:
                self.db.execute(
                    "UPDATE requests SET status = 'assigned', assigned_to = ? WHERE id = ? AND status = 'queued'",
                    (replacement["id"], row["id"]),
                )
            updated = self._query_request(row["id"])
            if updated:
                self._publish_request("request.assigned", updated)

    # ---------------------------------------------------------------- lifecycle
    async def create(
        self,
        parsed: ParsedRequest,
        *,
        user_id: str | None,
        api_key_id: str | None,
        client_ip: str | None,
        requested_timeout_ms: int | None = None,
        raw_request: Any | None = None,
    ) -> dict[str, Any]:
        settings = self.settings()
        timeout_seconds = self._timeout_seconds(requested_timeout_ms)
        now = now_ms()
        deadline_at = now + timeout_seconds * 1000
        fill_enabled = bool(settings.get("timeout_fill_enabled", True))
        lead = int(settings.get("timeout_fill_lead_seconds", 12))
        lead = max(2, min(lead, max(2, int(timeout_seconds * 0.5))))
        auto_fill_at = deadline_at - lead * 1000 if fill_enabled else None
        if auto_fill_at is not None:
            auto_fill_at = max(now + 800, auto_fill_at)
        assigned = self._pick_admin(parsed.model)
        from .security import new_id

        request_id = new_id("req")
        status = "assigned" if assigned else "queued"
        self.db.execute(
            """
            INSERT INTO requests(id, model, protocol, status, input_json, input_text, questions_json,
                                 raw_request, user_id, api_key_id, assigned_to, created_at, deadline_at,
                                 auto_fill_at, timeout_seconds, client_ip)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                parsed.model,
                parsed.protocol,
                status,
                json.dumps(parsed.input, ensure_ascii=False),
                parsed.input_text,
                json.dumps(parsed.questions_json(), ensure_ascii=False),
                json.dumps(raw_request if raw_request is not None else parsed.raw, ensure_ascii=False),
                user_id,
                api_key_id,
                assigned["id"] if assigned else None,
                now,
                deadline_at,
                auto_fill_at,
                timeout_seconds,
                client_ip,
            ),
        )
        pending = PendingRequest(request_id)
        async with self._lock:
            self._pending[request_id] = pending
        target = auto_fill_at if auto_fill_at is not None else deadline_at
        pending.monitor = asyncio.create_task(self._monitor(request_id, target, fill_enabled), name=f"monitor-{request_id}")
        row = self._query_request(request_id)
        assert row is not None
        self._publish_request("request.created", row)
        return dict(row)

    async def _monitor(self, request_id: str, target_ms: int, auto_fill: bool) -> None:
        try:
            delay = max(0, target_ms - now_ms()) / 1000.0
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if auto_fill:
            await self.auto_fill_if_active(request_id)
        else:
            await self.timeout_if_active(request_id)

    def _questions(self, row: dict[str, Any]):
        from .protocols import Question

        result: list[Question] = []
        for item in _json_load(row.get("questions_json"), []):
            result.append(
                Question(
                    id=item["id"],
                    type=item["type"],
                    instructions=item.get("instructions"),
                    criteria=item.get("criteria"),
                )
            )
        return result

    async def wait(self, request_id: str, timeout_seconds: int) -> dict[str, Any] | None:
        pending = self._pending.get(request_id)
        if pending is not None:
            try:
                await asyncio.wait_for(pending.event.wait(), timeout=timeout_seconds + 15)
            except asyncio.TimeoutError:
                await self.timeout_if_active(request_id)
        row = self._query_request(request_id)
        pending = self._pending.pop(request_id, None)
        if pending and pending.monitor and not pending.monitor.done():
            pending.monitor.cancel()
        return dict(row) if row else None

    async def _complete(
        self,
        request_id: str,
        answers: dict[str, Any],
        *,
        answered_by: str | None,
        auto_filled: bool,
        actor_kind: str = "operator",
    ) -> dict[str, Any] | None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
            if row is None:
                return None
            if row["status"] not in ACTIVE_STATUSES:
                return dict(row)
            now = now_ms()
            conn.execute(
                """
                UPDATE requests
                SET status = 'answered', answers_json = ?, answered_by = ?, auto_filled = ?,
                    completed_at = ?, duration_ms = ?, draft_json = NULL
                WHERE id = ? AND status IN ('queued', 'assigned')
                """,
                (
                    json.dumps(answers, ensure_ascii=False),
                    answered_by,
                    1 if auto_filled else 0,
                    now,
                    now - row["created_at"],
                    request_id,
                ),
            )
        updated = self._query_request(request_id)
        pending = None
        async with self._lock:
            pending = self._pending.pop(request_id, None)
        if pending:
            pending.event.set()
            if pending.monitor and pending.monitor is not asyncio.current_task() and not pending.monitor.done():
                pending.monitor.cancel()
        if updated:
            self._publish_request("request.completed", updated)
            self.db.audit(
                actor_kind,
                answered_by,
                "request.auto_fill" if auto_filled else "request.answer",
                request_id,
                {"model": updated["model"], "auto_filled": auto_filled},
            )
        return dict(updated) if updated else None

    async def submit(
        self,
        request_id: str,
        raw_answers: Any,
        *,
        answered_by: str,
        actor_kind: str = "operator",
    ) -> dict[str, Any] | None:
        row = self._query_request(request_id)
        if not row:
            return None
        if row["status"] not in ACTIVE_STATUSES:
            return dict(row)
        questions = self._questions(dict(row))
        answers = normalize_answers(questions, raw_answers, require_all=True)
        return await self._complete(request_id, answers, answered_by=answered_by, auto_filled=False, actor_kind=actor_kind)

    def save_draft(self, request_id: str, raw_answers: Any) -> dict[str, Any] | None:
        row = self._query_request(request_id)
        if not row or row["status"] not in ACTIVE_STATUSES:
            return dict(row) if row else None
        questions = self._questions(dict(row))
        partial = merge_partial(questions, raw_answers)
        self.db.execute(
            "UPDATE requests SET draft_json = ? WHERE id = ? AND status IN ('queued', 'assigned')",
            (json.dumps(partial, ensure_ascii=False), request_id),
        )
        updated = self._query_request(request_id)
        if updated:
            self._publish_request("request.updated", updated)
        return dict(updated) if updated else None

    def randomize(self, request_id: str, only: list[str] | None = None) -> dict[str, Any]:
        row = self._query_request(request_id)
        if not row:
            raise ProtocolError(404, "请求不存在", "request_not_found")
        questions = self._questions(dict(row))
        existing = _json_load(row["draft_json"], {})
        if not isinstance(existing, dict):
            existing = {}
        valid_ids = {question.id for question in questions}
        if only:
            only = [qid for qid in only if qid in valid_ids]
        return randomize_answers(questions, only=only or None, existing=existing)

    async def auto_fill_if_active(self, request_id: str) -> dict[str, Any] | None:
        row = self._query_request(request_id)
        if not row or row["status"] not in ACTIVE_STATUSES:
            return dict(row) if row else None
        row_dict = dict(row)
        questions = self._questions(row_dict)
        existing = merge_partial(questions, _json_load(row_dict.get("draft_json"), {}))
        try:
            generated = randomize_answers(questions, only=None, existing=existing)
            # Preserve valid manually-entered answers, fill only what is missing.
            merged = {question.id: existing.get(question.id) or generated[question.id] for question in questions}
            # Ensure every generated answer is a valid provider answer.
            valid = normalize_answers(questions, merged, require_all=True)
        except Exception:
            # A broken draft must never strand an HTTP request past its deadline.
            valid = normalize_answers(questions, randomize_answers(questions), require_all=True)
        return await self._complete(request_id, valid, answered_by=None, auto_filled=True, actor_kind="system")

    async def timeout_if_active(self, request_id: str) -> dict[str, Any] | None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
            if row is None:
                return None
            if row["status"] not in ACTIVE_STATUSES:
                return dict(row)
            now = now_ms()
            conn.execute(
                "UPDATE requests SET status = 'timed_out', completed_at = ?, duration_ms = ?, error = 'request_timeout' "
                "WHERE id = ? AND status IN ('queued', 'assigned')",
                (now, now - row["created_at"], request_id),
            )
        updated = self._query_request(request_id)
        async with self._lock:
            pending = self._pending.pop(request_id, None)
        if pending:
            pending.event.set()
            if pending.monitor and pending.monitor is not asyncio.current_task() and not pending.monitor.done():
                pending.monitor.cancel()
        if updated:
            self._publish_request("request.completed", updated)
            self.db.audit("system", None, "request.timeout", request_id, {"model": updated["model"]})
        return dict(updated) if updated else None

    async def cancel(self, request_id: str, actor_id: str) -> dict[str, Any] | None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
            if row is None:
                return None
            if row["status"] in ACTIVE_STATUSES:
                conn.execute(
                    "UPDATE requests SET status = 'cancelled', completed_at = ?, error = 'cancelled_by_admin' WHERE id = ?",
                    (now_ms(), request_id),
                )
        updated = self._query_request(request_id)
        async with self._lock:
            pending = self._pending.pop(request_id, None)
        if pending:
            pending.event.set()
            if pending.monitor and not pending.monitor.done():
                pending.monitor.cancel()
        if updated:
            self._publish_request("request.completed", updated)
            self.db.audit("admin", actor_id, "request.cancel", request_id, None)
        return dict(updated) if updated else None

    # ------------------------------------------------------------- serialization
    def serialize_request(self, row: Any, *, detail: bool = True, include_private: bool = False) -> dict[str, Any]:
        data = _row_dict(row)
        answers = _json_load(data.get("answers_json"), None)
        draft = _json_load(data.get("draft_json"), {})
        payload: dict[str, Any] = {
            "id": data.get("id"),
            "model": data.get("model"),
            "protocol": data.get("protocol"),
            "status": data.get("status"),
            "input": _json_load(data.get("input_json"), None),
            "input_text": data.get("input_text", ""),
            "input_kind": _input_kind(data.get("input_json")),
            "questions": _json_load(data.get("questions_json"), []),
            "created_at": data.get("created_at"),
            "deadline_at": data.get("deadline_at"),
            "auto_fill_at": data.get("auto_fill_at"),
            "timeout_seconds": data.get("timeout_seconds"),
            "auto_filled": bool(data.get("auto_filled")),
            "duration_ms": data.get("duration_ms"),
            "error": data.get("error"),
            "assigned_to": {"id": data["assigned_to"], "name": data.get("assigned_name")} if data.get("assigned_to") else None,
            "answered_by": {"id": data["answered_by"], "name": data.get("answered_name")} if data.get("answered_by") else None,
            "answered_count": len(answers or {}),
            "total_questions": len(_json_load(data.get("questions_json"), [])),
            "draft": draft if isinstance(draft, dict) else {},
        }
        if detail:
            payload["answers"] = answers
            payload["input"] = _json_load(data.get("input_json"), None)
        if include_private:
            payload["user"] = (
                {"id": data.get("user_id"), "email": data.get("user_email"), "name": data.get("user_name")}
                if data.get("user_id")
                else None
            )
            payload["raw_request"] = _json_load(data.get("raw_request"), None)
        if data.get("status") in ACTIVE_STATUSES:
            payload["remaining_ms"] = max(0, int(data.get("deadline_at") or now_ms()) - now_ms())
        return payload

    def _publish_request(self, event_type: str, row: Any) -> None:
        request = self.serialize_request(row, detail=True)
        assigned_id = row["assigned_to"] if "assigned_to" in row.keys() else None
        asyncio.create_task(
            self.hub.publish(
                {"type": event_type, "data": {"request": request}},
                model=row["model"],
                notify_admin_id=assigned_id,
                all_admins=True,
            ),
            name=f"publish-{event_type}",
        )

    async def publish_presence(self) -> None:
        rows = self.db.fetch_all("SELECT id, name, role, last_assigned_at FROM backoffice_users WHERE disabled = 0")
        online = self.hub.online_ids()
        data = [
            {
                "id": row["id"],
                "name": row["name"],
                "role": row["role"],
                "online": row["id"] in online,
                "last_assigned_at": row["last_assigned_at"],
            }
            for row in rows
        ]
        await self.hub.publish({"type": "presence", "data": {"operators": data}}, model=None, all_admins=True)

    # ----------------------------------------------------------------- startup
    def recover_after_restart(self) -> int:
        count = self.db.execute(
            "UPDATE requests SET status = 'timed_out', completed_at = ?, duration_ms = ? - created_at, "
            "error = 'server_restart' WHERE status IN ('queued', 'assigned')",
            (now_ms(), now_ms()),
        )
        settings = get_all_settings(self.db)
        retention_days = int(settings.get("history_retention_days", 90))
        cutoff = now_ms() - retention_days * 86400000
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_ms(),))
            conn.execute(
                "DELETE FROM requests WHERE created_at < ? AND status IN ('answered', 'timed_out', 'cancelled')",
                (cutoff,),
            )
            conn.execute("DELETE FROM audit_logs WHERE created_at < ?", (cutoff,))
        return count

    async def shutdown(self) -> None:
        async with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for item in pending:
            if item.monitor and not item.monitor.done():
                item.monitor.cancel()
            item.event.set()
