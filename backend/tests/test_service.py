from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fake_decision.auth import create_backoffice_user, set_assignments
from fake_decision.db import Database
from fake_decision.manager import RequestService
from fake_decision.protocols import parse_systemone
from fake_decision.realtime import Connection, RealtimeHub
from fake_decision.settings import seed_defaults
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, sample_questions


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "service.sqlite3")
    db.initialize()
    seed_defaults(db)
    return db


def test_assignment_draft_preservation_and_autofill(tmp_path: Path):
    async def run():
        db = _db(tmp_path)
        operator = create_backoffice_user(db, "operator@test.local", "Op", "OperatorPass!123", role="operator", model_names=["jev-latest"])
        hub = RealtimeHub()
        conn = Connection(admin_id=operator["id"], name=operator["name"], role="operator", models={"jev-latest"})
        await hub.register(conn)
        service = RequestService(db, hub)
        parsed = parse_systemone(
            {"model": "jev-latest", "state": "A duplicate charge.", "questions": sample_questions()},
            "jev-latest",
            ["jev-latest", "gemini-decision-1"],
        )
        row = await service.create(parsed, user_id=None, api_key_id=None, client_ip="127.0.0.1", requested_timeout_ms=3000)
        assert row["status"] == "assigned"
        assert row["assigned_to"] == operator["id"]
        # Draft only one answer; the auto-fill must keep it byte-for-byte (normalized).
        drafted = service.save_draft(row["id"], {"refund": {"type": "noul", "noul": 0.73}})
        assert drafted is not None
        completed = await service.auto_fill_if_active(row["id"])
        assert completed is not None
        assert completed["status"] == "answered"
        assert completed["auto_filled"] == 1
        answers = json.loads(completed["answers_json"])
        assert answers["refund"]["noul"] == 0.73
        assert set(answers) == {"refund", "action", "urgency"}
        # The waiting HTTP side is released.
        assert service._pending.get(row["id"]) is None
        await hub.unregister(conn)

    asyncio.run(run())


def test_assignment_moves_to_queue_on_disconnect(tmp_path: Path):
    async def run():
        db = _db(tmp_path)
        operator = create_backoffice_user(db, "op2@test.local", "Op 2", "OperatorPass!123", role="operator", model_names=["jev-latest"])
        hub = RealtimeHub()
        conn = Connection(admin_id=operator["id"], name=operator["name"], role="operator", models={"jev-latest"})
        await hub.register(conn)
        service = RequestService(db, hub)
        parsed = parse_systemone(
            {"model": "jev-latest", "state": "x", "questions": sample_questions()},
            "jev-latest",
            ["jev-latest", "gemini-decision-1"],
        )
        row = await service.create(parsed, user_id=None, api_key_id=None, client_ip="127.0.0.1", requested_timeout_ms=3000)
        assert row["status"] == "assigned"
        await hub.unregister(conn)
        await service.handle_disconnect(operator["id"])
        fresh = service.get_request(row["id"])
        assert fresh is not None
        assert fresh["status"] == "queued"
        assert fresh["assigned_to"] is None
        await service.cancel(row["id"], "test")

    asyncio.run(run())


def test_admin_receive_all_off_keeps_admin_out_of_assignment(tmp_path: Path):
    async def run():
        db = _db(tmp_path)
        admin = create_backoffice_user(db, ADMIN_EMAIL, "Admin", ADMIN_PASSWORD, role="admin", model_names=[])
        db.set_setting("admin_receive_all", False)
        hub = RealtimeHub()
        conn = Connection(admin_id=admin["id"], name=admin["name"], role="admin", models={"jev-latest"})
        await hub.register(conn)
        service = RequestService(db, hub)
        parsed = parse_systemone(
            {"model": "jev-latest", "state": "x", "questions": sample_questions()},
            "jev-latest",
            ["jev-latest", "gemini-decision-1"],
        )
        row = await service.create(parsed, user_id=None, api_key_id=None, client_ip="127.0.0.1", requested_timeout_ms=3000)
        assert row["status"] == "queued"
        await service.cancel(row["id"], "test")

    asyncio.run(run())
