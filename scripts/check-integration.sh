#!/bin/sh
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
run() {
  "$@" || status=1
}
run python3 -B scripts/test_action_bridge.py
run python3 -B scripts/test_action_faults.py
exit "$status"
