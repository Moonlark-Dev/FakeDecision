#!/usr/bin/env bash
# Build the FakeDecision standalone executable and pack the per-OS release archive.
#
#   Linux  -> dist/FakeDecision-linux-x86_64.tar.gz   (+ .sha256), binary fakedecision
#   Windows-> dist/FakeDecision-windows-x86_64.zip    (+ .sha256), binary fakedecision.exe
#
# Runs on Linux as well as under Git Bash (MINGW/MSYS/CYGWIN) on windows-latest.
# Every path handed to native tools (python.exe, Nuitka) stays relative to the
# current directory, because MSYS may rewrite absolute POSIX paths (/c/...) when
# converting arguments for native Windows programs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*) IS_WINDOWS=1 ;;
  *) IS_WINDOWS=0 ;;
esac

if [[ "$IS_WINDOWS" == "1" ]]; then
  OS_TAG="windows"
  BINARY_NAME="fakedecision.exe"
  ARCHIVE_EXT="zip"
else
  OS_TAG="linux"
  BINARY_NAME="fakedecision"
  ARCHIVE_EXT="tar.gz"
fi

# x86_64 is fixed by the published artifact contract; both CI runners are x64.
DIST_NAME="FakeDecision-${OS_TAG}-x86_64"
DIST_DIR="dist/${DIST_NAME}"
ARCHIVE="dist/${DIST_NAME}.${ARCHIVE_EXT}"
NUITKA_OUT="build/nuitka/main.dist"

if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  if [[ ! -d frontend/node_modules ]]; then
    (cd frontend && pnpm install --frozen-lockfile)
  fi
  (cd frontend && pnpm build)
fi

rm -rf build/nuitka dist
mkdir -p build dist

echo "==> Building standalone executable with Nuitka"
(
  cd backend
  python -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --output-dir=../build/nuitka \
    --output-filename=fakedecision \
    --include-package=fake_decision \
    --include-package=uvicorn \
    --include-package=websockets \
    --include-package=fastapi \
    --include-package=starlette \
    --include-package=pydantic \
    --include-package=anyio \
    --include-data-dir=fake_decision/web/dist=fake_decision/web/dist \
    --nofollow-import-to=pytest \
    --nofollow-import-to=tkinter \
    --nofollow-import-to=distutils \
    main.py
)

if [[ ! -f "$NUITKA_OUT/$BINARY_NAME" ]]; then
  echo "ERROR: Nuitka did not produce $NUITKA_OUT/$BINARY_NAME" >&2
  ls -la "$NUITKA_OUT" >&2 || true
  exit 1
fi

echo "==> Packaging $DIST_NAME"
mkdir -p "$DIST_DIR/data"
cp -a "$NUITKA_OUT/." "$DIST_DIR/"
cp README.md LICENSE "$DIST_DIR/"

if [[ "$IS_WINDOWS" == "1" ]]; then
  # CRLF so the file opens cleanly in Notepad/PowerShell users' editors.
  printf '%s\r\n' \
    "FakeDecision standalone build" \
    "" \
    "Run (from this folder, in Command Prompt or PowerShell):" \
    "  .\\fakedecision.exe --host 0.0.0.0 --port 8790 --data-dir .\\data" \
    "" \
    "First start prints the generated admin password." \
    > "$DIST_DIR/RUN.txt"
else
  printf '%s\n' \
    "FakeDecision standalone build" \
    "" \
    "Run:" \
    "  ./fakedecision --host 0.0.0.0 --port 8790 --data-dir ./data" \
    "" \
    "First start prints the generated admin password." \
    > "$DIST_DIR/RUN.txt"
fi

if [[ "$IS_WINDOWS" == "1" ]]; then
  # Zip with the stdlib (portable, no PowerShell path quoting): a single
  # top-level FakeDecision-windows-x86_64/ folder, with explicit directory
  # entries so empty dirs such as data/ survive extraction.
  python - "$DIST_DIR" "$ARCHIVE" <<'PY'
import os
import sys
import zipfile

src_dir, archive = sys.argv[1], sys.argv[2]
base_dir = os.path.dirname(src_dir)

with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for root, dirnames, filenames in os.walk(src_dir):
        dirnames.sort()
        filenames.sort()
        arc_root = os.path.relpath(root, base_dir).replace(os.sep, "/")
        zf.write(root, arc_root + "/")
        for filename in filenames:
            full_path = os.path.join(root, filename)
            zf.write(full_path, os.path.relpath(full_path, base_dir).replace(os.sep, "/"))
print(f"==> wrote {archive}")
PY

  # checksum via hashlib, same "hash  filename\n" format sha256sum -c expects;
  # newline="\n" keeps the file LF-only so coreutils parses it under Git Bash.
  python - "$ARCHIVE" <<'PY'
import hashlib
import os
import sys

archive = sys.argv[1]
digest = hashlib.sha256()
with open(archive, "rb") as fh:
    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
        digest.update(chunk)
line = f"{digest.hexdigest()}  {os.path.basename(archive)}\n"
with open(archive + ".sha256", "w", encoding="ascii", newline="\n") as fh:
    fh.write(line)
print(line, end="")
PY
else
  tar -C dist -czf "$ARCHIVE" "$DIST_NAME"
  (cd dist && sha256sum "${DIST_NAME}.tar.gz" > "${DIST_NAME}.tar.gz.sha256")
fi

echo "==> Artifact: $ARCHIVE"
ls -lh "$ARCHIVE" "$ARCHIVE.sha256"
