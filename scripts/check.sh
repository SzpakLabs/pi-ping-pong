#!/bin/sh
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
run() {
  "$@" || status=1
}
run npm run lint
run npm run typecheck
run uv run --locked ruff check .
run python3 -B scripts/test_bridge.py
run node scripts/test_pi_receiver.mjs
exit "$status"
