#!/bin/sh
set -eu

message=${1-}
if [ -z "$message" ]; then
  echo 'Usage: make test-commit MSG="commit message"' >&2
  exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

require_tested_tree() {
  if git diff --cached --quiet; then
    echo 'test-commit: refusing: index is empty' >&2
    return 1
  fi
  if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo 'test-commit: refusing: unstaged or untracked changes exist' >&2
    return 1
  fi
}

require_tested_tree
bun run check
require_tested_tree

if [ "${COMMIT_DRY_RUN:-0}" = 1 ]; then
  echo "test-commit: checks passed; dry run, would commit: $message"
  exit 0
fi
exec git commit -m "$message"
