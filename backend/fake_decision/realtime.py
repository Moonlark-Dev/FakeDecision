from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Connection:
    admin_id: str
    name: str
    role: str
    models: set[str]
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=128))


class RealtimeHub:
    """Fan-out hub for operator dashboards.

    Each browser tab gets one queue. A slow tab drops events instead of blocking
    the request lifecycle; the UI re-syncs with a REST snapshot on reconnect.
    """

    def __init__(self) -> None:
        self._connections: dict[str, list[Connection]] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: Connection) -> None:
        async with self._lock:
            self._connections.setdefault(conn.admin_id, []).append(conn)

    async def unregister(self, conn: Connection) -> None:
        async with self._lock:
            buckets = self._connections.get(conn.admin_id)
            if not buckets:
                return
            self._connections[conn.admin_id] = [item for item in buckets if item is not conn]
            if not self._connections[conn.admin_id]:
                self._connections.pop(conn.admin_id, None)

    def online_ids(self) -> set[str]:
        return set(self._connections.keys())

    def is_online(self, admin_id: str) -> bool:
        return admin_id in self._connections

    async def enqueue(self, conn: Connection, event: dict[str, Any]) -> None:
        try:
            conn.queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    async def publish(
        self,
        event: dict[str, Any],
        *,
        model: str | None = None,
        notify_admin_id: str | None = None,
        all_admins: bool = True,
    ) -> None:
        async with self._lock:
            recipients: list[tuple[Connection, bool]] = []
            for admin_id, conns in self._connections.items():
                for conn in conns:
                    if conn.role == "admin":
                        if all_admins or admin_id == notify_admin_id:
                            recipients.append((conn, admin_id == notify_admin_id))
                    elif model is None or model in conn.models:
                        recipients.append((conn, admin_id == notify_admin_id))
        for conn, is_target in recipients:
            payload = dict(event)
            data = dict(event.get("data") or {})
            data["notify"] = bool(is_target)
            payload["data"] = data
            await self.enqueue(conn, payload)

    async def send_to(self, admin_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._connections.get(admin_id, []))
        for conn in conns:
            payload = dict(event)
            data = dict(event.get("data") or {})
            data["notify"] = True
            payload["data"] = data
            await self.enqueue(conn, payload)
