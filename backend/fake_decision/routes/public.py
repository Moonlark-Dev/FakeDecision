from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from .. import __version__
from ..branding import logo_content_type, logo_file, logo_headers, logo_url
from ..settings import get_all_settings, public_model

router = APIRouter(prefix="/api", tags=["site"])


@router.get("/site")
async def site_config(request: Request) -> dict[str, Any]:
    settings = get_all_settings(request.app.state.db)
    return {
        "site_name": settings["site_name"],
        "logo_url": logo_url(request.app.state.db, request.app.state.config),
        "tagline": settings["site_tagline"],
        "description": settings["site_description"],
        "announcement": settings["announcement"],
        "registration_enabled": bool(settings["registration_enabled"]),
        "support_email": settings["support_email"],
        "sound_default": bool(settings["sound_default"]),
        "show_register_cta": bool(settings["show_register_cta"]),
        "version": __version__,
    }


@router.get("/branding/logo")
async def branding_logo(request: Request) -> FileResponse:
    path = logo_file(request.app.state.config)
    if path is None:
        raise HTTPException(status_code=404, detail="No custom logo configured")
    return FileResponse(path, media_type=logo_content_type(path), headers=logo_headers(path))


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
        "service": f"{get_all_settings(db)['site_name']} Decisions",
        "version": __version__,
        "models": models["n"] if models else 0,
    }
