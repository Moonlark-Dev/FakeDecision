#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
python3 -m pytest -q
(cd frontend && pnpm exec vue-tsc --noEmit && pnpm exec vite build)
echo "smoke: ok"
