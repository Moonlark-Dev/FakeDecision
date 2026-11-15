from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from .. import __version__
from ..settings import get_all_settings, public_model

router = APIRouter(prefix="/api", tags=["site"])


@router.get("/site")
async def site_config(request: Request) -> dict[str, Any]:
    settings = get_all_settings(request.app.state.db)
    return {
        "site_name": settings["site_name"],
        "tagline": settings["site_tagline"],
        "description": settings["site_description"],
        "announcement": settings["announcement"],
        "registration_enabled": bool(settings["registration_enabled"]),
        "support_email": settings["support_email"],
        "sound_default": bool(settings["sound_default"]),
        "show_register_cta": bool(settings["show_register_cta"]),
        "version": __version__,
    }


@router.get("/models")
async def public_models(request: Request) -> dict[str, Any]:
    rows = request.app.state.db.fetch_all(
        "SELECT * FROM models WHERE enabled = 1 ORDER BY sort_order, name"
    )
    models = []
    for row in rows:
        item = public_model(row)
        item["protocols"] = ["systemone", "google"] if item["protocol"] == "both" else [item["protocol"]]
        models.append(item)
    return {"models": models, "object": "list"}


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    db = request.app.state.db
    models = db.fetch_one("SELECT COUNT(*) AS n FROM models WHERE enabled = 1")
    return {
        "ok": True,
        "service": "Noema Decisions",
        "version": __version__,
        "models": models["n"] if models else 0,
    }
