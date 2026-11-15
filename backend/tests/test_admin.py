from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_EMAIL, create_key, login_admin, register_user


def test_operator_crud_model_assignment_and_role_guards(client: TestClient):
    login_admin(client)
    created = client.post(
        "/api/admin/operators",
        json={"email": "operator@test.local", "name": "Night Operator", "password": "OperatorPass!123", "models": ["jev-latest"]},
    )
    assert created.status_code == 200, created.text
    operator = created.json()["operator"]
    assert operator["models"] == ["jev-latest"]

    operators = client.get("/api/admin/operators").json()["operators"]
    assert any(item["email"] == "operator@test.local" and item["models"] == ["jev-latest"] for item in operators)

    updated = client.patch(f"/api/admin/operators/{operator['id']}", json={"models": ["jev-latest", "gemini-decision-1"], "disabled": False})
    assert updated.status_code == 200, updated.text
    assert set(updated.json()["operator"]["models"]) == {"jev-latest", "gemini-decision-1"}

    # Operator credentials work, but administrative endpoints are role-gated.
    client.post("/api/admin/auth/logout")
    op_login = client.post("/api/admin/auth/login", json={"email": "operator@test.local", "password": "OperatorPass!123"})
    assert op_login.status_code == 200
    assert client.get("/api/admin/users").status_code == 403
    assert client.get("/api/admin/settings").status_code == 403
    assert client.get("/api/admin/requests?view=active").status_code == 200
    assert [m["name"] for m in client.get("/api/admin/models").json()["models"]]  # read allowed


def test_settings_models_and_audit(client: TestClient):
    login_admin(client)
    settings = client.get("/api/admin/settings").json()
    assert "request_timeout_seconds" in settings["values"]

    invalid = client.put("/api/admin/settings", json={"values": {"timeout_fill_lead_seconds": 200, "request_timeout_seconds": 20}})
    assert invalid.status_code == 422

    updated = client.put(
        "/api/admin/settings",
        json={"values": {"site_name": "Test Decision Co", "timeout_fill_enabled": False, "request_timeout_seconds": 60}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["values"]["site_name"] == "Test Decision Co"
    assert client.get("/api/site").json()["site_name"] == "Test Decision Co"

    created = client.post(
        "/api/admin/models",
        json={
            "name": "test-decision",
            "display_name": "Test Decision",
            "protocol": "both",
            "description": "Test model",
            "context_window": 4096,
            "enabled": True,
            "sort_order": 99,
        },
    )
    assert created.status_code == 200, created.text
    model = created.json()["model"]
    assert model["name"] == "test-decision"

    patched = client.patch(f"/api/admin/models/{model['id']}", json={"display_name": "Test Decision 2", "enabled": False})
    assert patched.status_code == 200
    assert patched.json()["model"]["display_name"] == "Test Decision 2"

    deleted = client.delete(f"/api/admin/models/{model['id']}")
    assert deleted.status_code == 200

    audit = client.get("/api/admin/audit").json()
    actions = {item["action"] for item in audit["logs"]}
    assert "settings.update" in actions
    assert "model.create" in actions


def test_model_rename_cascades_assignment(client: TestClient):
    login_admin(client)
    model = client.post(
        "/api/admin/models",
        json={"name": "rename-me", "display_name": "Rename", "protocol": "both", "description": "", "context_window": 1000, "enabled": True, "sort_order": 1},
    ).json()["model"]
    operator = client.post(
        "/api/admin/operators",
        json={"email": "rename@test.local", "name": "Rename Op", "password": "OperatorPass!123", "models": ["rename-me"]},
    ).json()["operator"]
    renamed = client.patch(f"/api/admin/models/{model['id']}", json={"name": "renamed-model"})
    assert renamed.status_code == 200
    operators = client.get("/api/admin/operators").json()["operators"]
    chosen = next(item for item in operators if item["id"] == operator["id"])
    assert chosen["models"] == ["renamed-model"]


def test_csrf_origin_guard(client: TestClient):
    login_admin(client)
    response = client.put(
        "/api/admin/settings",
        headers={"Origin": "https://evil.example"},
        json={"values": {"site_name": "Hijacked"}},
    )
    assert response.status_code == 403
    assert response.json()["detail"]


def test_user_usage_and_key_revocation(client: TestClient):
    register_user(client)
    key = create_key(client)
    keys = client.get("/api/keys").json()["keys"]
    assert len(keys) == 1
    revoked = client.delete(f"/api/keys/{keys[0]['id']}")
    assert revoked.status_code == 200
    assert client.post("/v1/systemone", headers={"Authorization": f"Bearer {key}"}, json={"model": "jev-latest", "state": "x", "questions": {"q": {"type": "noul", "instructions": "?"}}}).status_code == 401
    usage = client.get("/api/account/usage").json()
    assert usage["total"] == 0
