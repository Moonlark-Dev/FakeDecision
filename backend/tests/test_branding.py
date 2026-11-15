from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import login_admin

# 1x1 transparent PNG.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode("ascii")
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
SVG_DATA_URL = "data:image/svg+xml;base64," + base64.b64encode(SVG).decode("ascii")


def test_brand_logo_upload_serve_replace_delete(client: TestClient, tmp_path: Path):
    login_admin(client)

    site = client.get("/api/site").json()
    assert site["logo_url"] == ""
    assert client.get("/api/branding/logo").status_code == 404

    uploaded = client.post(
        "/api/admin/branding/logo",
        json={"filename": "logo.png", "data": PNG_DATA_URL},
    )
    assert uploaded.status_code == 200, uploaded.text
    url = uploaded.json()["logo_url"]
    assert url.startswith("/api/branding/logo?v=")

    served = client.get(url)
    assert served.status_code == 200
    assert served.content == PNG_1X1
    assert served.headers["content-type"].startswith("image/png")
    assert "sandbox" in served.headers["content-security-policy"]
    assert client.get("/api/site").json()["logo_url"] == url
    # The custom logo also becomes the favicon served to browsers.
    assert client.get("/favicon.svg").content == PNG_1X1

    files = list((tmp_path / "branding").glob("logo.*"))
    assert len(files) == 1

    replaced = client.post(
        "/api/admin/branding/logo",
        json={"filename": "logo.svg", "data": SVG_DATA_URL},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["logo_url"] != url
    assert len(list((tmp_path / "branding").glob("logo.*"))) == 1
    assert client.get(replaced.json()["logo_url"]).headers["content-type"].startswith("image/svg+xml")
    assert client.get("/favicon.svg").content == SVG

    deleted = client.delete("/api/admin/branding/logo")
    assert deleted.status_code == 200
    assert deleted.json()["logo_url"] == ""
    assert client.get("/api/site").json()["logo_url"] == ""
    assert client.get("/api/branding/logo").status_code == 404
    assert not list((tmp_path / "branding").glob("logo.*"))

    audit = client.get("/api/admin/audit").json()
    actions = {item["action"] for item in audit["logs"]}
    assert "branding.logo.update" in actions
    assert "branding.logo.remove" in actions


def test_brand_logo_rejects_invalid_uploads(client: TestClient):
    login_admin(client)

    def upload(body: dict[str, str]):
        return client.post("/api/admin/branding/logo", json=body)

    assert upload({"filename": "logo.png", "data": "data:image/png;base64,bm90LWFuLWltYWdl"}).status_code == 422
    # Declared type must match the actual bytes (PNG bytes labelled as JPEG).
    assert upload({"filename": "logo.jpg", "data": "data:image/jpeg;base64," + base64.b64encode(PNG_1X1).decode()}).status_code == 422
    # Oversized payloads are rejected before they hit the data directory.
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (512 * 1024)
    assert (
        upload({"filename": "big.png", "data": "data:image/png;base64," + base64.b64encode(oversized).decode()}).status_code
        == 422
    )
    # SVG logos may not carry scripts.
    evil = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert (
        upload({"filename": "evil.svg", "data": "data:image/svg+xml;base64," + base64.b64encode(evil).decode()}).status_code
        == 422
    )
    assert client.get("/api/site").json()["logo_url"] == ""


def test_brand_logo_requires_admin(client: TestClient):
    assert client.post("/api/admin/branding/logo", json={"filename": "logo.png", "data": PNG_DATA_URL}).status_code in {401, 403}
    assert client.delete("/api/admin/branding/logo").status_code in {401, 403}
