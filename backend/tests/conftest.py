from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from fake_decision.app import create_app
from fake_decision.config import AppConfig

ADMIN_EMAIL = "admin@test.local"
ADMIN_PASSWORD = "AdminPassword!123"
USER_EMAIL = "user@test.local"
USER_PASSWORD = "UserPassword!123"


@pytest.fixture()
def app(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        admin_email=ADMIN_EMAIL,
        admin_password=ADMIN_PASSWORD,
        secret="test-secret",
        serve_frontend=False,
    )
    return create_app(config)


@pytest.fixture()
def client(app: Any) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def register_user(client: TestClient, email: str = USER_EMAIL, password: str = USER_PASSWORD) -> dict[str, Any]:
    response = client.post("/api/auth/register", json={"email": email, "name": "Test User", "password": password})
    assert response.status_code == 200, response.text
    return response.json()["user"]


def login_user(client: TestClient, email: str = USER_EMAIL, password: str = USER_PASSWORD) -> dict[str, Any]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["user"]


def login_admin(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> dict[str, Any]:
    response = client.post("/api/admin/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["admin"]


def create_key(client: TestClient) -> str:
    response = client.post("/api/keys", json={"name": "Test key"})
    assert response.status_code == 200, response.text
    return response.json()["secret"]


def sample_questions() -> dict[str, Any]:
    return {
        "refund": {
            "type": "noul",
            "instructions": "Does the customer explicitly ask for a refund?",
            "criteria": {"true": "Explicit refund request", "false": "No explicit request"},
        },
        "action": {
            "type": "choice",
            "instructions": "Pick the next support action.",
            "criteria": {"refund": "Refund the duplicate charge", "replace": "Send a replacement"},
        },
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this request?",
            "criteria": ["Low", "Medium", "High"],
        },
    }
