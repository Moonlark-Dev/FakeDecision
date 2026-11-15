from __future__ import annotations

import json
from typing import Any

from .db import Database, now_ms
from .security import MODEL_NAME_RE, new_id

DEFAULT_SETTINGS: dict[str, Any] = {
    "site_name": "Noema",
    "site_tagline": "Typed decisions for software that needs an answer.",
    "site_description": "Calibrated yes/no probabilities, bounded choices and rubric scores over one shared context. One endpoint, no output tokens.",
    "public_base_url": "",
    "registration_enabled": True,
    "request_timeout_seconds": 120,
    "timeout_fill_enabled": True,
    "timeout_fill_lead_seconds": 12,
    "admin_receive_all": True,
    "sound_default": True,
    "announcement": "",
    "history_retention_days": 90,
    "max_pending_per_user": 30,
    "rate_limit_per_minute": 90,
    "support_email": "support@noema.dev",
    "docs_url": "",
    "show_register_cta": True,
}

SETTING_TYPES: dict[str, type] = {
    "site_name": str,
    "site_tagline": str,
    "site_description": str,
    "public_base_url": str,
    "registration_enabled": bool,
    "request_timeout_seconds": int,
    "timeout_fill_enabled": bool,
    "timeout_fill_lead_seconds": int,
    "admin_receive_all": bool,
    "sound_default": bool,
    "announcement": str,
    "history_retention_days": int,
    "max_pending_per_user": int,
    "rate_limit_per_minute": int,
    "support_email": str,
    "docs_url": str,
    "show_register_cta": bool,
}

SETTING_LIMITS: dict[str, tuple[int, int]] = {
    "request_timeout_seconds": (15, 900),
    "timeout_fill_lead_seconds": (2, 120),
    "history_retention_days": (1, 3650),
    "max_pending_per_user": (1, 500),
    "rate_limit_per_minute": (1, 10000),
}

DEFAULT_MODELS = [
    {
        "name": "jev-latest",
        "display_name": "Jev 1.4",
        "protocol": "both",
        "description": "Fast, calibrated decisions for routing, screening and evaluation. Text-first, with structured state support.",
        "context_window": 65536,
        "sort_order": 10,
    },
    {
        "name": "gemini-decision-1",
        "display_name": "Gemini Decision 1",
        "protocol": "google",
        "description": "Multimodal closed-set decisions over text, images and documents. Up to 1,000 questions per request.",
        "context_window": 262144,
        "sort_order": 20,
    },
]


def get_all_settings(db: Database) -> dict[str, Any]:
    values = dict(DEFAULT_SETTINGS)
    rows = db.fetch_all("SELECT key, value FROM settings")
    for row in rows:
        key = row["key"]
        if key not in DEFAULT_SETTINGS:
            continue
        try:
            values[key] = json.loads(row["value"])
        except json.JSONDecodeError:
            continue
    return values


def validate_setting_updates(updates: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    clean: dict[str, Any] = {}
    errors: list[str] = []
    for key, value in updates.items():
        expected = SETTING_TYPES.get(key)
        if expected is None:
            errors.append(f"未知设置项：{key}")
            continue
        if expected is bool:
            if not isinstance(value, bool):
                errors.append(f"{key} 必须是布尔值")
                continue
        elif expected is int:
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"{key} 必须是整数")
                continue
            bounds = SETTING_LIMITS.get(key)
            if bounds and not (bounds[0] <= value <= bounds[1]):
                errors.append(f"{key} 必须在 {bounds[0]} 到 {bounds[1]} 之间")
                continue
        elif expected is str:
            if not isinstance(value, str):
                errors.append(f"{key} 必须是字符串")
                continue
            value = value.strip()
            if len(value) > 2000:
                errors.append(f"{key} 过长")
                continue
        clean[key] = value
    return clean, errors


def save_settings(db: Database, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        db.set_setting(key, value)


def seed_defaults(db: Database, admin_receive_all: bool = True) -> None:
    existing = db.fetch_one("SELECT COUNT(*) AS n FROM models")
    if existing is None or existing["n"] == 0:
        for spec in DEFAULT_MODELS:
            db.execute(
                "INSERT OR IGNORE INTO models(id, name, display_name, protocol, description, context_window, enabled, sort_order, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    new_id("mdl"),
                    spec["name"],
                    spec["display_name"],
                    spec["protocol"],
                    spec["description"],
                    spec["context_window"],
                    spec["sort_order"],
                    now_ms(),
                ),
            )
    for key, value in DEFAULT_SETTINGS.items():
        if db.get_setting(key) is None:
            db.set_setting(key, value)


def public_model(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "display_name": row["display_name"],
        "protocol": row["protocol"],
        "description": row["description"],
        "context_window": row["context_window"],
        "enabled": bool(row["enabled"]),
        "sort_order": row["sort_order"],
    }


def validate_model_name(name: str) -> str | None:
    if not MODEL_NAME_RE.match(name):
        return "模型名只能包含字母、数字、点、下划线、斜杠和短横线"
    return None
