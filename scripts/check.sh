#!/bin/sh
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
status=0
run() {
  "$@" || status=1
}
run bun run check:python
run bun run check:ts
exit "$status"
