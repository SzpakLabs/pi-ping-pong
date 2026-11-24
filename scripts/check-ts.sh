#!/bin/sh
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
run() {
  "$@" || status=1
}
run bun run lint
run bun run typecheck
run node scripts/test_pi_receiver.mjs
run node scripts/test_ralph_usage.mjs
exit "$status"
