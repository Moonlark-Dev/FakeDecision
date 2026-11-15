from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(slots=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8790
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "fakedecision")
    database: Path | None = None
    admin_email: str = "admin@fakedecision.local"
    admin_password: str | None = None
    public_url: str = ""
    secret: str | None = None
    cors_origins: tuple[str, ...] = ()
    log_level: str = "info"
    dev: bool = False
    serve_frontend: bool = True
    preview: bool = False

    @property
    def db_path(self) -> Path:
        return self.database or (self.data_dir / "fakedecision.sqlite3")

    @property
    def web_dist(self) -> Path:
        """Locate bundled SPA assets in source checkouts and Nuitka dists."""
        import sys

        candidates = [
            Path(__file__).resolve().parent / "web" / "dist",
            Path(sys.argv[0]).resolve().parent / "fake_decision" / "web" / "dist",
            Path(sys.executable).resolve().parent / "fake_decision" / "web" / "dist",
        ]
        for candidate in candidates:
            if (candidate / "index.html").is_file():
                return candidate
        return candidates[0]

    @classmethod
    def from_env(cls) -> "AppConfig":
        data_dir = Path(os.environ.get("FAKE_DECISION_DATA_DIR", str(Path.home() / ".local" / "share" / "fakedecision"))).expanduser()
        database = os.environ.get("FAKE_DECISION_DATABASE")
        origins_raw = os.environ.get("FAKE_DECISION_CORS_ORIGINS", "")
        origins = tuple(part.strip() for part in origins_raw.split(",") if part.strip())
        return cls(
            host=os.environ.get("FAKE_DECISION_HOST", "127.0.0.1"),
            port=_env_int("FAKE_DECISION_PORT", 8790),
            data_dir=data_dir,
            database=Path(database).expanduser() if database else None,
            admin_email=os.environ.get("FAKE_DECISION_ADMIN_EMAIL", "admin@fakedecision.local"),
            admin_password=os.environ.get("FAKE_DECISION_ADMIN_PASSWORD") or None,
            public_url=os.environ.get("FAKE_DECISION_PUBLIC_URL", ""),
            secret=os.environ.get("FAKE_DECISION_SECRET") or None,
            cors_origins=origins,
            log_level=os.environ.get("FAKE_DECISION_LOG_LEVEL", "info"),
            dev=_env_bool("FAKE_DECISION_DEV", False),
            serve_frontend=_env_bool("FAKE_DECISION_SERVE_FRONTEND", True),
            preview=_env_bool("FAKE_DECISION_PREVIEW", False),
        )
