#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
(cd frontend && pnpm build)
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m fake_decision --host 0.0.0.0 --port "${FAKE_DECISION_PORT:-8790}" "$@"
