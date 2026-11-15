#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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
    --output-dir="$ROOT/build/nuitka" \
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

DIST_DIR="dist/FakeDecision-linux-x86_64"
mkdir -p "$DIST_DIR"
cp -a build/nuitka/main.dist/. "$DIST_DIR/"
cp README.md LICENSE "$DIST_DIR/"
mkdir -p "$DIST_DIR/data"
printf '%s\n' \
  "FakeDecision standalone build" \
  "" \
  "Run:" \
  "  ./fakedecision --host 0.0.0.0 --port 8790 --data-dir ./data" \
  "" \
  "First start prints the generated admin password." \
  > "$DIST_DIR/RUN.txt"

tar -C dist -czf dist/FakeDecision-linux-x86_64.tar.gz FakeDecision-linux-x86_64
(cd dist && sha256sum FakeDecision-linux-x86_64.tar.gz > FakeDecision-linux-x86_64.tar.gz.sha256)
echo "==> Artifact: dist/FakeDecision-linux-x86_64.tar.gz"
ls -lh dist/FakeDecision-linux-x86_64.tar.gz
