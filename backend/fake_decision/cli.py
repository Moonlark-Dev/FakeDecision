from __future__ import annotations

import argparse
import logging
import os
import secrets
from pathlib import Path

from . import __version__
from .app import _bootstrap_admin, create_app, emit_legal_warning
from .config import AppConfig
from .db import Database
from .security import hash_password, new_id
from .settings import seed_defaults


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fakedecision",
        description="Human-in-the-loop System One / Gemini Decisions compatible API.",
    )
    parser.add_argument("--host", default=os.environ.get("FAKE_DECISION_HOST", "127.0.0.1"), help="Bind address (env: FAKE_DECISION_HOST)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FAKE_DECISION_PORT", "8790")), help="Bind port (env: FAKE_DECISION_PORT)")
    parser.add_argument("--data-dir", default=os.environ.get("FAKE_DECISION_DATA_DIR"), help="Data directory for SQLite and generated secrets")
    parser.add_argument("--database", default=os.environ.get("FAKE_DECISION_DATABASE"), help="Explicit SQLite database path")
    parser.add_argument("--admin-email", default=os.environ.get("FAKE_DECISION_ADMIN_EMAIL", "admin@fakedecision.local"))
    parser.add_argument("--admin-password", default=os.environ.get("FAKE_DECISION_ADMIN_PASSWORD"))
    parser.add_argument("--public-url", default=os.environ.get("FAKE_DECISION_PUBLIC_URL", ""), help="Public origin used for generated links and Origin checks")
    parser.add_argument("--secret", default=os.environ.get("FAKE_DECISION_SECRET"), help="Optional server secret (generated and stored by default)")
    parser.add_argument("--cors-origin", action="append", default=None, help="Allow an extra browser origin for the API (repeatable)")
    parser.add_argument("--log-level", default=os.environ.get("FAKE_DECISION_LOG_LEVEL", "info"))
    parser.add_argument("--dev", action="store_true", help="Development mode")
    parser.add_argument("--no-frontend", action="store_true", help="Do not serve the built SPA")
    parser.add_argument("--init-only", action="store_true", help="Initialize the database and print bootstrap credentials, then exit")
    parser.add_argument("--version", action="version", version=f"FakeDecision {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    emit_legal_warning()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else Path.home() / ".local" / "share" / "fakedecision"
    origins = tuple(args.cors_origin or ())
    config = AppConfig(
        host=args.host,
        port=args.port,
        data_dir=data_dir,
        database=Path(args.database).expanduser() if args.database else None,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
        public_url=args.public_url.rstrip("/"),
        secret=args.secret,
        cors_origins=origins,
        log_level=args.log_level,
        dev=args.dev,
        serve_frontend=not args.no_frontend,
    )
    if config.port < 1 or config.port > 65535:
        raise SystemExit("port must be between 1 and 65535")

    if args.init_only:
        db = Database(config.db_path)
        db.initialize()
        seed_defaults(db)
        created, password = _bootstrap_admin(db, config)
        if created:
            print(f"Bootstrap admin: {config.admin_email} / {password}")
        else:
            print("Admin already exists; no credentials changed.")
        print(f"Database: {config.db_path}")
        return

    app = create_app(config)
    import uvicorn

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level,
        proxy_headers=os.environ.get("FAKE_DECISION_TRUST_PROXY", "").lower() in {"1", "true", "yes"},
        forwarded_allow_ips=os.environ.get("FAKE_DECISION_FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
