from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from tests.conftest import create_key, login_admin, register_user, sample_questions


def test_websocket_hello(client: TestClient):
    login_admin(client)
    with client.websocket_connect("/api/admin/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["data"]["admin"]["role"] == "admin"
        assert "settings" in hello["data"]
        assert isinstance(hello["data"]["pending"], list)


def test_live_request_and_human_answer(client: TestClient):
    """The admin socket sees an incoming request, then answers it over HTTP."""
    register_user(client)
    key = create_key(client)
    login_admin(client)
    with client.websocket_connect("/api/admin/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"

        result: dict[str, object] = {}

        def call_api():
            result["response"] = client.post(
                "/v1/systemone",
                headers={"Authorization": f"Bearer {key}", "X-Decision-Timeout-Ms": "20000"},
                json={
                    "model": "jev-latest",
                    "state": "The customer wants a refund for a double charge.",
                    "questions": sample_questions(),
                },
            )

        thread = threading.Thread(target=call_api)
        thread.start()
        event = ws.receive_json()
        deadline = time.time() + 5
        while event["type"] not in {"request.created", "request.assigned"} and time.time() < deadline:
            event = ws.receive_json()
        assert event["type"] in {"request.created", "request.assigned"}
        request = event["data"]["request"]
        request_id = request["id"]
        assert event["data"]["notify"] is True

        randomized = client.post(f"/api/admin/requests/{request_id}/randomize", json={})
        assert randomized.status_code == 200, randomized.text
        answers = randomized.json()["answers"]
        answered = client.post(f"/api/admin/requests/{request_id}/answer", json={"answers": answers})
        assert answered.status_code == 200, answered.text
        assert answered.json()["request"]["status"] == "answered"
        thread.join(timeout=10)
        assert not thread.is_alive()
        response = result["response"]
        assert response.status_code == 200
        body = response.json()
        assert body["answers"]["refund"]["type"] == "noul"
        assert response.headers["x-request-id"] == request_id

        # The completed event arrives on the socket.
        deadline = time.time() + 5
        found = False
        while time.time() < deadline and not found:
            event = ws.receive_json()
            if event["type"] == "request.completed" and event["data"]["request"]["id"] == request_id:
                found = True
        assert found
