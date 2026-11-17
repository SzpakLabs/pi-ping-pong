#!/bin/sh
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
run() {
  "$@" || status=1
}
run uv run --locked ruff check .
run python3 -B scripts/test_bridge.py
run python3 -B scripts/test_action_protocol.py
run python3 -B scripts/test_ppp_checkpoint.py
exit "$status"
