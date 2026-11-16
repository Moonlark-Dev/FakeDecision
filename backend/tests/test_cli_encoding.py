from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import fake_decision.app as app_module
import fake_decision.cli as cli

ROOT = Path(__file__).resolve().parents[2]


def test_legal_warning_survives_legacy_code_page(monkeypatch):
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(app_module, "_WARNING_EMITTED", False)

    # Must not raise UnicodeEncodeError on a code page without box drawing.
    app_module.emit_legal_warning()
    stream.flush()

    output = buffer.getvalue()
    assert output
    assert b"?" in output


def test_ensure_utf8_stdio_reconfigures_streams(monkeypatch):
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    cli._ensure_utf8_stdio()
    assert stdout.encoding.lower().replace("-", "") == "utf8"
    stdout.write("box drawing: ┌──┐\n")
    stdout.flush()
    assert "┌──┐".encode("utf-8") in buffer.getvalue()


def test_init_only_runs_with_cp1252_stdio(tmp_path: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fake_decision",
            "--init-only",
            "--data-dir",
            str(tmp_path / "data"),
            "--admin-password",
            "TestOnly!Password123",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Bootstrap admin" in result.stdout
