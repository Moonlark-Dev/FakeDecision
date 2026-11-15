from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import set_session_cookie
from .config import AppConfig
from .db import Database, now_ms
from .manager import RequestService
from .realtime import RealtimeHub
from .security import RateLimiter, hash_password, new_id
from .settings import get_all_settings, seed_defaults

LOGGER = logging.getLogger("fakedecision")
_WARNING_EMITTED = False

BANNER = r"""
  ______         _        ______            _     _
 |  ____|       | |      |  ____|          | |   (_)
 | |__ __ _  ___| | __   | |__ ___  ___  ___| |__  _  ___  _ __
 |  __/ _` |/ __| |/ /   |  __/ _ \/ __|/ __| '_ \| |/ _ \| '_ \
 | | | (_| | (__|   <    | | |  __/ (__| (__| | | | | (_) | | | |
 |_|  \__,_|\___|_|\_\   |_|  \___|\___|\___|_| |_|_|\___/|_| |_|

  FakeDecision · human-in-the-loop decision API compatibility layer
"""

LEGAL_WARNING = """
┌────────────────────────────  LEGAL WARNING  ────────────────────────────┐
│  FakeDecision is for PRIVATE, LOCAL and RESEARCH use only.              │
│                                                                         │
│  It intentionally imitates decision-model provider APIs while answers   │
│  are produced by humans. Do NOT deploy it as a public or commercial     │
│  service, do NOT advertise it as a real provider, and do NOT use it to  │
│  deceive users, bypass access controls, or commit fraud.                │
│                                                                         │
│  本项目仅供私人部署与研究使用。严禁用于公开或商业服务、冒充真实模型    │
│  提供方、欺骗用户、绕过访问控制或实施欺诈。部署者需自行承担全部法律     │
│  与合规风险。No warranty. Licensed under AGPL-3.0-or-later.             │
└─────────────────────────────────────────────────────────────────────────┘
"""


def emit_legal_warning() -> None:
    global _WARNING_EMITTED
    if _WARNING_EMITTED:
        return
    _WARNING_EMITTED = True
    print(BANNER, flush=True)
    print(LEGAL_WARNING, flush=True)


def _bootstrap_admin(db: Database, config: AppConfig) -> tuple[bool, str | None]:
    row = db.fetch_one("SELECT COUNT(*) AS n FROM backoffice_users WHERE role = 'admin'")
    if row and row["n"]:
        return False, None
    password = config.admin_password or secrets.token_urlsafe(14)
    db.execute(
        "INSERT INTO backoffice_users(id, email, name, password_hash, role, created_at) VALUES(?, ?, ?, ?, 'admin', ?)",
        (new_id("bku"), config.admin_email.strip().lower(), "Administrator", hash_password(password), now_ms()),
    )
    LOGGER.warning("=" * 72)
    LOGGER.warning("BOOTSTRAP ADMIN CREATED")
    LOGGER.warning("  email:    %s", config.admin_email)
    LOGGER.warning("  password: %s", password)
    LOGGER.warning("Change this password after the first login. It is printed only once.")
    LOGGER.warning("=" * 72)
    return True, password


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        emit_legal_warning()
        db = Database(config.db_path)
        db.initialize()
        seed_defaults(db)
        _bootstrap_admin(db, config)
        secret = config.secret or db.get_meta("session_secret")
        if not secret:
            secret = secrets.token_urlsafe(48)
            db.set_meta("session_secret", secret)
        hub = RealtimeHub()
        service = RequestService(db, hub)
        recovered = service.recover_after_restart()
        app.state.config = config
        app.state.db = db
        app.state.hub = hub
        app.state.service = service
        app.state.secret = secret
        app.state.login_limiter = RateLimiter(30, 300)
        app.state.register_limiter = RateLimiter(12, 3600)
        app.state.playground_limiter = RateLimiter(60, 60)
        app.state.api_limiter = RateLimiter(100000, 60)
        from .routes.api import ApiWindows

        app.state.api_windows = ApiWindows()
        app.state.started_at = now_ms()
        LOGGER.info("FakeDecision %s starting with database %s", __version__, config.db_path)
        if recovered:
            LOGGER.warning("Marked %s interrupted requests as timed_out", recovered)
        settings = get_all_settings(db)
        if settings.get("public_base_url"):
            LOGGER.info("Public base URL: %s", settings["public_base_url"])
        try:
            yield
        finally:
            await service.shutdown()
            db.execute("DELETE FROM sessions WHERE expires_at < ?", (now_ms(),))

    app = FastAPI(
        title="FakeDecision",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.config = config

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # Cookie-authenticated mutation APIs are same-origin. Reject a cross-site
        # Origin before it reaches a handler (SameSite=Lax is the second layer).
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and not config.dev:
                public_url = config.public_url
                try:
                    from .settings import get_all_settings

                    public_url = get_all_settings(request.app.state.db).get("public_base_url") or public_url
                except Exception:
                    pass
                allowed = {str(request.base_url).rstrip("/")}
                if public_url:
                    allowed.add(str(public_url).rstrip("/"))
                if origin.rstrip("/") not in allowed:
                    return JSONResponse({"detail": "跨站请求被拒绝"}, status_code=403)
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow, noarchive, nosnippet")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; connect-src 'self' ws: wss:; font-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        if request.url.path.startswith("/api/") or request.url.path.startswith("/v1"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        LOGGER.exception("Unhandled error on %s %s", request.method, request.url.path)
        if request.url.path.startswith("/api/") or request.url.path.startswith("/v1"):
            return JSONResponse({"detail": "服务器内部错误"}, status_code=500)
        return PlainTextResponse("Internal Server Error", status_code=500)

    from .routes import admin, api, auth_routes, public, ws

    app.include_router(public.router)
    app.include_router(auth_routes.router)
    app.include_router(admin.router)
    app.include_router(api.router)
    app.include_router(ws.router)

    # Built SPA assets. In development Vite serves the frontend and proxies /api.
    dist = config.web_dist
    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/robots.txt", include_in_schema=False)
    async def robots() -> PlainTextResponse:
        return PlainTextResponse(
            "User-agent: *\nDisallow: /\n\n# FakeDecision is a private deployment. No crawling.\n",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "service": "fakedecision", "version": __version__, "time": now_ms()}

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon() -> Response:
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0b1220"/><path d="M18 44V20h13c9 0 15 4.8 15 12s-6 12-15 12H18Zm9-7h4c4.2 0 6.8-1.9 6.8-5s-2.6-5-6.8-5h-4v10Z" fill="#fff"/><circle cx="47" cy="18" r="4" fill="#c7f36b"/></svg>"""
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith(("api/", "v1/", "v1beta/")):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if not config.serve_frontend:
            return JSONResponse({"detail": "Frontend disabled"}, status_code=404)
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(
                "<!doctype html><html><body style='font-family:system-ui;padding:3rem;max-width:760px;margin:auto'>"
                "<h1>FakeDecision</h1><p>Frontend is not built yet.</p>"
                "<pre>cd frontend &amp;&amp; pnpm install &amp;&amp; pnpm build</pre>"
                "<p>API is available under <code>/v1</code> and <code>/v1beta</code>.</p></body></html>",
                status_code=200,
            )
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
        except ValueError:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
