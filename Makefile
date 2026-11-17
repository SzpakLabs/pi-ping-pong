SHELL := /bin/sh

.PHONY: check-python check-ts check-bridge check-faults check-integration test commit test-commit

check-python:
	bun run check:python

check-ts:
	bun run check:ts

check-bridge:
	bun run check:bridge

check-faults:
	bun run check:faults

check-integration:
	bun run check:integration

test:
	bun run check

commit:
	@test -n "$(MSG)" || { echo 'Usage: make commit MSG="commit message"' >&2; exit 2; }
	git commit -m "$(MSG)"

test-commit:
	@test -n "$(MSG)" || { echo 'Usage: make test-commit MSG="commit message"' >&2; exit 2; }
	@sh scripts/test-commit.sh "$(MSG)"
