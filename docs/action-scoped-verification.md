# Action-scoped implementation and verification record

> Evaluator-era design/history: current execution is Worker (ordinary tests) → independent Reviewer (remaining judgments) → Core. Separate evaluator/preflight/repair and old-run resume were removed. Current [protocol](action-scoped-protocol.md) and [migration](evaluator-preparation.md) supersede lifecycle/compatibility instructions below; historical results are not live verification of the new cycle.

See [plan](action-scoped-implementation-plan.md) and [protocol design](action-scoped-protocol.md).

## Evidence status

**P1–P4 implemented and locally tested.** Final source gate: **71 Python test executions** (15 legacy bridge, 38 controller including inherited regression cases, 18 fake-process integration), extended receiver suite, ESLint, TypeScript, Ruff and isolated installer fixture **PASS**. Final requirement coverage and limitations: [implementation report](action-scoped-implementation-report.md). No live verification authorized. Runtime installation and KB updates excluded by task boundary.

### P1 result

Implemented `scripts/action_protocol.py` with explicit protocol 2/schema 1, immutable initial action contracts, dependency validation, fsynced private transactional snapshot, retained/deduplicated blockers, additive grants and cumulative consumption, and causal closure authority. Initial focused gate: 6 tests passed; existing bridge: 15 passed.

### P2 result

Implemented fresh verified judgments, partial/invalid resolutions, human-approval distinction, grouped questions, budget pause/extension, action-local attempts/stalls/experiments, concrete wakes and local reminders, terminal precedence and independent finish. Added operation ownership/journaling and uncertain-outcome reconciliation primitives for P4. Expanded focused gate: 25 test executions passed (includes shared registry regression cases); existing bridge: 15 passed. These are controller fixtures, not yet an end-to-end bridge claim.

### P3 result

Implemented `scripts/action_bridge.py`, explicit version dispatch and v2 review/operation/resume/wake commands in shared bridge, native receiver human ingress, safe-boundary validation/continuation, fresh-session context restoration and passive reminders. Existing Goal/Ralph accepted boundaries and transport/receipt implementations reused. No worker runs while human waiting or while independent verification/review executes. Six real-bridge/fake-executable scenarios pass, including both runtimes, invalid resolution then closure after main exhaustion, same-run extension, cancellation/recovery, pin-integrity halt and orphan worker/uncertain effects. Receiver tests cover private addressed ingress, native confirmation, RPC refusal, terminal re-entry refusal and passive model-free reminders across reload. Installer fixture verifies new modules/docs are included, no real runtime installation.

Check failure investigated: receiver expected command count was six; new explicit human command makes seven. Updated assertion to preserve all old aliases and assert the new command; added behavioral coverage (not a bypass). Initial installer invocation lacked required `--fixture-root`; no installer ran in that failed command. Initial lint found one unused test import; removed it. Subsequent full checks passed.

### P4 result and final audit

Implemented and tested exclusive controller ownership, inherited worker lease through controller interruption, current-session effect checks, before-effect journal, uncertain-outcome investigation, pinned private governing files, sealed cumulative state, fresh reconciliation/context restoration, safe terminal precedence and suppression of stale queued work. Added interactive console authority for Codex without a model/pipe flag, arranged resource-event ingress (observation only, no authority), and one-shot bounded recheck identities.

Additional gate failures were investigated rather than bypassed:

- Scheduled recheck deadline elapsed during independent review: absolute valid arrangements now execute once at the next safe boundary instead of being rejected for review latency. Reusing that event reference cannot create repeated paid polling.
- macOS `/var` versus `/private/var` aliases made a synthetic active-review path compare unequal: canonical real paths now identify the same exact request; state/cycle/hash checks retained.
- A test caught an intermediate `wait` state whose wake had already been consumed: the controller now transitions to active replan/selection as it consumes that event. Test fixture leaves a concrete observable waiting interval; no wake-less durable wait accepted.

Final audit tightened evaluator cycle/review/state binding, refused external effects from retired session tokens or absent live leases, made halt dominate cancellation in either arrival order, made v2 delivery-attempt markers fsynced, retained completed evidence bytes in a private content-addressed archive with request/review integrity checks, and verified Codex grouped notifications without model-backed recurring reminders. Final callback-delivery failure preserves independently confirmed acceptance and never blindly replays the callback. No numerical closure cap introduced. No source requirement remains knowingly planned-only; operational evidence gaps remain explicit below.

## Commands and results

Repository commands below are run from `.pi/worktrees/permission-friction-research`, unless explicitly noted. Initial read-only inspection: `git status --short`, `ls scripts extensions docs`, `wc -l scripts/* extensions/*`, targeted `rg` in bridge/receiver/installer and reads of the authoritative spec, skill contract and KB project README/global agent instructions. Baseline contains user-owned edits to `docs/README.md` and untracked agreed specification/research; preserve them.

Phase gate commands (in order):

1. `python3 -B scripts/test_action_protocol.py && python3 -B scripts/test_bridge.py` — PASS, 6 + 15 tests.
2. `python3 -B scripts/test_action_protocol.py && python3 -B scripts/test_bridge.py` — PASS, 25 + 15 tests.
3. `python3 -B scripts/test_action_bridge.py` — PASS, 6 subprocess integration scenarios.
4. `python3 -B scripts/test_action_protocol.py && python3 -B scripts/test_bridge.py && node scripts/test_pi_receiver.mjs && python3 -B scripts/test_install.py` — 25 + 15 Python tests passed; receiver failed on outdated command-count assertion; chain stopped before installer.
5. `node scripts/test_pi_receiver.mjs && python3 -B scripts/test_install.py && npm run check` — receiver PASS; installer argument parser rejected missing fixture-root; check not run by that chain.
6. `UV_PROJECT_ENVIRONMENT=/Users/macos/codex-context/skills/pi-ping-pong/.venv UV_NO_SYNC=1 npm run check` — first run FAIL (one unused Python test import); ESLint, TypeScript, 15 legacy + 25 controller + 6 integration tests and receiver passed. Second run PASS all gates after removing import. Existing development environment reused with sync disabled: no dependency installation.
7. `fixture=$(mktemp -d /tmp/ppp-install-test.XXXXXX) && python3 -B scripts/test_install.py --fixture-root "$fixture/fixture"; result=$?; if [ -n "${fixture:-}" ]; then rm -rf "$fixture"; fi; exit "$result"` — PASS; only disposable synthetic destinations changed and removed.
8. `python3 -B scripts/test_action_protocol.py && python3 -B scripts/test_action_bridge.py` — controller 34 PASS; expanded integration initially FAIL (2/11: elapsed recheck, canonical path); both diagnosed above.
9. `python3 -B scripts/test_action_bridge.py && UV_PROJECT_ENVIRONMENT=/Users/macos/codex-context/skills/pi-ping-pong/.venv UV_NO_SYNC=1 npm run check` — integration initially FAIL (1/11: consumed-wake intermediate state); chained check did not run. Fixed state transition rather than disabling assertion.
10. `UV_PROJECT_ENVIRONMENT=/Users/macos/codex-context/skills/pi-ping-pong/.venv UV_NO_SYNC=1 npm run check` — expanded gates PASS (15 legacy + 34 controller + 13 integration + receiver/static); subsequent expansion PASS (15 + 34 + 15 + receiver/static).
11. `python3 -B scripts/test_action_protocol.py && python3 -B scripts/test_action_bridge.py` — PASS (34 + 15) after evaluator context binding changes.
12. **Final code gate:** `UV_PROJECT_ENVIRONMENT=/Users/macos/codex-context/skills/pi-ping-pong/.venv UV_NO_SYNC=1 npm run check` — **PASS**: ESLint, `tsc --project tsconfig.json`, `uv run --locked ruff check .`, 15 legacy bridge, 38 controller, 18 real-bridge/fake-provider integration tests, receiver real-loader/API regressions. This command was repeated after evidence-retention hardening (15 + 38 + 17 PASS) and final notification-failure coverage (15 + 38 + 18 PASS). Existing environment only; sync disabled.
13. **Final installer gate:** exact disposable-fixture command in item 7 repeated — **PASS**, including new controller/bridge/protocol docs, executable modes and privacy exclusions. No actual installed runtime changed.
14. `git diff --check && git status --short && git diff -- scripts/bridge.py scripts/check.sh scripts/test_install.py extensions/pi-reviewed.ts README.md SKILL.md references/reviewed-runs.md docs/README.md scripts/test_pi_receiver.mjs` — whitespace PASS; exact tracked diff/status inspected. New controller/bridge source read completely and subsequent targeted changes inspected; source spec/research remain user-owned input artifacts. Final documentation/link/status check recorded below.

15. Final disposable installer command from item 7 repeated after all source/doc changes — **PASS**. Final `git diff --check`, `git diff --stat`, `git status --short` — **PASS** / inspected; changes are uncommitted in the requested worktree, and original agreed spec/research inputs remain present.
16. Final local documentation/new-file whitespace command below — **PASS**, **66 local link targets**; no network access. `docs/GUIDE.md` gained only a version-boundary notice, inspected with the final diff.

```sh
python3 -B - <<'PY'
from pathlib import Path
import re
paths = [Path(p) for p in ('README.md', 'SKILL.md', 'references/reviewed-runs.md', 'docs/README.md', 'docs/GUIDE.md')]
paths += sorted(Path('docs').glob('action-scoped-*.md'))
checked = 0
for file in paths:
    for href in re.findall(r'\]\(([^)]+)\)', file.read_text()):
        if href.startswith(('http:', 'https:', 'mailto:', '#')):
            continue
        target = href.split('#', 1)[0]
        if target:
            assert (file.parent / target).exists(), (str(file), href)
            checked += 1
new_files = list(Path('scripts').glob('*action*.py')) + list(Path('docs').glob('action-scoped-*.md'))
for file in new_files:
    for number, line in enumerate(file.read_text().splitlines(), 1):
        assert line == line.rstrip(), (str(file), number, 'trailing whitespace')
print(f'Document links: {checked} local targets PASS; new-file whitespace PASS')
PY
```

## Known evidence limitations

Unit/fake RPC tests cannot prove production readiness, real credential validation, real provider side-effect reconciliation, live Goal/Ralph restoration, human channel operational reliability, or visual TUI behavior. No model or external target is exercised by local regressions.
