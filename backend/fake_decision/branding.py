from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Any

from .db import Database

#: Uploaded logos are kept small: they are served on every public page.
LOGO_MAX_BYTES = 512 * 1024

_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

_EXTENSION_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


class LogoError(ValueError):
    """Raised when an uploaded brand logo is not acceptable."""


def branding_dir(config: Any) -> Path:
    """Directory that stores runtime branding assets next to the database."""
    return Path(config.data_dir) / "branding"


def logo_file(config: Any) -> Path | None:
    folder = branding_dir(config)
    if not folder.is_dir():
        return None
    for candidate in sorted(folder.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in _EXTENSION_MIME:
            return candidate
    return None


def logo_content_type(path: Path) -> str:
    return _EXTENSION_MIME.get(path.suffix.lower(), "application/octet-stream")


def logo_version(db: Database) -> int:
    raw = db.get_setting("brand_logo_version")
    if not raw:
        return 0
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    return value if isinstance(value, int) and value > 0 else 0


def logo_url(db: Database, config: Any) -> str:
    """Public URL of the custom logo, or an empty string for the built-in mark."""
    if logo_file(config) is None:
        return ""
    return f"/api/branding/logo?v={logo_version(db)}"


def _sniff_mime(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    head = payload[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").decode("utf-8", "ignore").lower()
    if "<svg" in head:
        return "image/svg+xml"
    return None


def parse_logo_upload(filename: str, data: str) -> tuple[bytes, str]:
    """Decode and validate a logo upload; returns (bytes, file suffix).

    Accepts either a base64 data URL (what the admin UI sends) or bare base64.
    The declared type and the sniffed type must agree, so a mislabelled file
    cannot be served under a type the server never validated.
    """
    raw = (data or "").strip()
    if not raw:
        raise LogoError("Logo payload is empty.")
    declared_mime = ""
    if raw.startswith("data:"):
        header, _, payload = raw.partition(",")
        if ";base64" not in header:
            raise LogoError("Logo data URL must be base64 encoded.")
        declared_mime = header[5:].split(";")[0].strip().lower()
        raw = payload
    try:
        payload = base64.b64decode("".join(raw.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise LogoError("Logo payload is not valid base64.") from exc
    if not payload:
        raise LogoError("Logo file is empty.")
    if len(payload) > LOGO_MAX_BYTES:
        raise LogoError(f"Logo must be {LOGO_MAX_BYTES // 1024} KB or smaller.")

    detected = _sniff_mime(payload)
    if detected is None:
        raise LogoError("Logo must be a PNG, JPEG, WebP or SVG image.")

    suffix = _MIME_EXTENSIONS.get(declared_mime)
    if suffix is None:
        suffix = Path(filename or "").suffix.lower()
        if suffix == ".jpeg":
            suffix = ".jpg"
    if suffix not in _EXTENSION_MIME:
        suffix = _MIME_EXTENSIONS[detected]
    if _EXTENSION_MIME[suffix] != detected:
        raise LogoError("Logo file type does not match its content.")

    if detected == "image/svg+xml":
        lowered = payload.decode("utf-8", "ignore").lower()
        if "<script" in lowered or "javascript:" in lowered:
            raise LogoError("SVG logos must not contain scripts.")
    return payload, suffix


def store_logo(config: Any, payload: bytes, suffix: str) -> Path:
    folder = branding_dir(config)
    folder.mkdir(parents=True, exist_ok=True)
    for existing in folder.glob("logo.*"):
        if existing.is_file():
            existing.unlink()
    path = folder / f"logo{suffix}"
    path.write_bytes(payload)
    return path


def remove_logo(config: Any) -> bool:
    folder = branding_dir(config)
    if not folder.is_dir():
        return False
    removed = False
    for existing in folder.glob("logo.*"):
        if existing.is_file():
            existing.unlink()
            removed = True
    return removed


def logo_headers(path: Path) -> dict[str, str]:
    """Headers for serving an uploaded logo from a versioned URL."""
    return {
        "Cache-Control": "public, max-age=31536000, immutable",
        # An uploaded SVG is displayed as an image, but if someone opens the
        # URL directly the sandbox keeps it from running scripts same-origin.
        "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
        "Content-Disposition": f'inline; filename="logo{path.suffix.lower()}"',
    }
