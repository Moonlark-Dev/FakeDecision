#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m fake_decision --dev --host 127.0.0.1 --port "${FAKE_DECISION_PORT:-8790}" "$@"
