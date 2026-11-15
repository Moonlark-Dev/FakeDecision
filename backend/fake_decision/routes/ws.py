from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..auth import SESSION_COOKIE_ADMIN, admin_payload, operator_models, resolve_session
from ..db import now_ms
from ..realtime import Connection
from ..settings import get_all_settings

router = APIRouter()


def _presence(db: Any, online: set[str]) -> list[dict[str, Any]]:
    rows = db.fetch_all("SELECT id, name, role, last_assigned_at FROM backoffice_users WHERE disabled = 0")
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "role": row["role"],
            "online": row["id"] in online,
            "last_assigned_at": row["last_assigned_at"],
        }
        for row in rows
    ]


@router.websocket("/api/admin/ws")
async def admin_ws(websocket: WebSocket) -> None:
    app = websocket.app
    db = app.state.db
    origin = websocket.headers.get("origin")
    if origin:
        origin_parts = urlsplit(origin)
        host = websocket.headers.get("host", "").split(":")[0]
        if origin_parts.hostname and origin_parts.hostname not in {host, "localhost", "127.0.0.1"}:
            await websocket.accept()
            await websocket.close(code=4403, reason="origin rejected")
            return
    admin = resolve_session(db, websocket.cookies.get(SESSION_COOKIE_ADMIN), "admin")
    await websocket.accept()
    if not admin:
        await websocket.close(code=4401, reason="unauthorized")
        return

    service = app.state.service
    hub = app.state.hub
    models = set(operator_models(db, admin))
    conn = Connection(admin_id=admin["id"], name=admin["name"], role=admin["role"], models=models)
    await hub.register(conn)

    active_clause = "r.status IN ('queued', 'assigned')"
    params: list[Any] = []
    if admin["role"] != "admin":
        if not models:
            active_clause += " AND 1=0"
        else:
            placeholders = ",".join("?" for _ in models)
            active_clause += f" AND r.model IN ({placeholders})"
            params.extend(models)
    rows = db.fetch_all(
        service.base_select() + f" WHERE {active_clause} ORDER BY r.created_at ASC LIMIT 100",
        params,
    )
    settings = get_all_settings(db)
    hello = {
        "type": "hello",
        "data": {
            "admin": admin_payload(db, admin),
            "server_time": now_ms(),
            "pending": [service.serialize_request(row, detail=False, include_private=admin["role"] == "admin") for row in rows],
            "presence": _presence(db, hub.online_ids()),
            "settings": {
                "sound_default": bool(settings["sound_default"]),
                "timeout_fill_enabled": bool(settings["timeout_fill_enabled"]),
                "timeout_fill_lead_seconds": int(settings["timeout_fill_lead_seconds"]),
                "admin_receive_all": bool(settings["admin_receive_all"]),
            },
        },
    }
    await websocket.send_text(json.dumps(hello, ensure_ascii=False))

    async def writer() -> None:
        while True:
            try:
                event = await asyncio.wait_for(conn.queue.get(), timeout=20)
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping", "data": {"time": now_ms()}}, ensure_ascii=False))
                except Exception:
                    return
            except asyncio.CancelledError:
                return
            except Exception:
                return

    writer_task = asyncio.create_task(writer(), name=f"ws-writer-{admin['id']}")
    try:
        await service.assign_queued_for(admin)
        await service.publish_presence()
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "ping":
                # The writer loop owns all websocket writes; ignore client pings
                # (the server heartbeat above is enough to keep the socket alive).
                continue
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        writer_task.cancel()
        await hub.unregister(conn)
        await service.handle_disconnect(admin["id"])
        await service.publish_presence()
        try:
            await websocket.close()
        except Exception:
            pass
