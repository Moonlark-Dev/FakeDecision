from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    create_key,
    login_admin,
    login_user,
    register_user,
    sample_questions,
)


def test_unauthenticated_provider_errors(client: TestClient):
    response = client.post("/v1/systemone", json={"model": "jev-latest", "state": "x", "questions": sample_questions()})
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["type"] == "invalid_api_key"

    response = client.post("/v1beta/decisions", json={"model": "gemini-decision-1", "input": "x", "questions": sample_questions()})
    assert response.status_code == 401
    assert body["error"]["type"] == "invalid_api_key"


def test_systemone_auto_fill_end_to_end(client: TestClient):
    register_user(client)
    key = create_key(client)
    body = {
        "model": "jev-latest",
        "state": {"ticket": "The same order was charged twice.", "customer": "Ada"},
        "questions": sample_questions(),
    }
    response = client.post(
        "/v1/systemone",
        headers={"Authorization": f"Bearer {key}", "X-Decision-Timeout-Ms": "3000", "X-Request-Id": "client-test"},
        json=body,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert response.headers["x-request-id"].startswith("req_")
    assert payload["model"] == "jev-latest"
    assert set(payload["answers"]) == {"refund", "action", "urgency"}
    refund = payload["answers"]["refund"]
    assert refund["type"] == "noul"
    assert 0.01 <= refund["noul"] <= 0.99
    assert "confidence" not in refund

    action = payload["answers"]["action"]
    assert action["choice"] == max(action["probabilities"], key=action["probabilities"].get)
    assert abs(sum(action["probabilities"].values()) - 1.0) < 0.02
    assert action["confidence"] == max(action["probabilities"].values())

    urgency = payload["answers"]["urgency"]
    assert set(urgency["probabilities"]) == {"0", "1", "2"}
    expected_score = round(sum(int(k) * v for k, v in urgency["probabilities"].items()), 2)
    assert abs(urgency["score"] - expected_score) < 0.02
    assert urgency["legend"]["2"] == "High"
    assert payload["usage"]["output_tokens"] == 0

    login_admin(client)
    history = client.get("/api/admin/requests?view=history&limit=20")
    assert history.status_code == 200
    items = history.json()["requests"]
    request_id = response.headers["x-request-id"]
    assert any(item["id"] == request_id and item["status"] == "answered" for item in items)
    detail = client.get(f"/api/admin/requests/{request_id}")
    assert detail.status_code == 200
    assert detail.json()["request"]["auto_filled"] is True


def test_google_auto_fill_and_protocol_routing(client: TestClient):
    register_user(client)
    key = create_key(client)
    response = client.post(
        "/v1beta/decisions",
        headers={"x-goog-api-key": key, "X-Decision-Timeout-Ms": "3000"},
        json={
            "model": "models/gemini-decision-1",
            "input": [{"type": "text", "text": "A photo of a spill."}, {"type": "image", "uri": "https://example.com/x.jpg", "mime_type": "image/jpeg"}],
            "questions": sample_questions(),
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload["answers"]) == {"refund", "action", "urgency"}
    assert payload["answers"]["refund"]["confidence"] == round(max(payload["answers"]["refund"]["noul"], 1 - payload["answers"]["refund"]["noul"]), 2)

    # A Google-only model must not be accepted by the System One route.
    wrong = client.post(
        "/v1/systemone",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gemini-decision-1", "state": "x", "questions": sample_questions()},
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "unsupported_protocol"

    # Path-scoped Google route.
    path_response = client.post(
        "/v1beta/models/gemini-decision-1:decisions",
        headers={"x-goog-api-key": key, "X-Decision-Timeout-Ms": "3000"},
        json={"input": "x", "questions": sample_questions()},
    )
    assert path_response.status_code == 200


def test_model_listing_and_google_models(client: TestClient):
    register_user(client)
    key = create_key(client)
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    ids = [model["id"] for model in response.json()["data"]]
    assert "jev-latest" in ids
    assert "gemini-decision-1" not in ids

    google = client.get("/v1beta/models", headers={"x-goog-api-key": key})
    assert google.status_code == 200
    names = [model["name"] for model in google.json()["models"]]
    assert "models/gemini-decision-1" in names


def test_console_playground_uses_session(client: TestClient):
    register_user(client)
    response = client.post(
        "/api/console/playground",
        json={
            "protocol": "systemone",
            "model": "jev-latest",
            "input": "A customer asks for a refund.",
            "questions": sample_questions(),
            "timeout_ms": 3000,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["protocol"] == "systemone"
    assert "answers" in data["response"]
    assert data["elapsed_ms"] >= 0


def test_timeout_without_auto_fill(client: TestClient, app):
    from fake_decision.settings import save_settings

    register_user(client)
    key = create_key(client)
    # Disable the feature for this request, then use a short timeout.
    save_settings(app.state.db, {"timeout_fill_enabled": False})
    response = client.post(
        "/v1/systemone",
        headers={"Authorization": f"Bearer {key}", "X-Decision-Timeout-Ms": "3000"},
        json={"model": "jev-latest", "state": "x", "questions": sample_questions()},
    )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "request_timeout"


def test_admin_auth_and_user_management(client: TestClient):
    register_user(client)
    # Logging in as a user and as an admin can coexist; the admin cookie is separate.
    admin = login_admin(client)
    assert admin["role"] == "admin"
    assert ADMIN_EMAIL in admin["email"]
    users = client.get("/api/admin/users")
    assert users.status_code == 200
    assert users.json()["total"] == 1
    user = users.json()["users"][0]
    detail = client.get(f"/api/admin/users/{user['id']}")
    assert detail.status_code == 200
    assert detail.json()["user"]["email"] == "user@test.local"
    patched = client.patch(f"/api/admin/users/{user['id']}", json={"disabled": True})
    assert patched.status_code == 200
    assert patched.json()["user"]["disabled"] is True

    # Disabled users cannot sign in.
    client.post("/api/auth/logout")
    bad = client.post("/api/auth/login", json={"email": "user@test.local", "password": "UserPassword!123"})
    assert bad.status_code == 401
