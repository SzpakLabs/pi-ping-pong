# Protocol 2: F3/F4 hardening evidence

Scope: nonterminal observation correction and cancellation boundaries only. HEAD at start: `6f3adc224495c083207f684ebe56e86783066007`. The worktree already contained the uncommitted [F1/F2 changes](protocol-2-f1-f2-hardening.md); these were inspected and preserved. No architecture expansion, real models, external effects, runtime installation, dependency adoption, commit or merge.

Sources: [audit](action-scoped-independent-audit.md), [protocol and correction contract](action-scoped-protocol.md), [integration order](autonomous-run-integration-plan.md).

## Root causes

- **F3:** reviewer API allowed only endorse/halt/stop, and the prompt required stop for incorrect evaluator judgments. No durable verification-specific disposition distinguished repairable observations, temporary checking failures, required-reviewer unavailability and genuine safety failures. Malformed evaluator JSON also reached the generic terminal ValueError handler.
- **F4:** blocking evaluator subprocess had no control polling or owned group supervision. Controls were not consumed after evaluation or at dispatch/application boundaries. A synchronous review file skipped the wait loop entirely. Reviewer recording did not ingest pending cancellation. Generic error handling could overwrite cancellation with halt.

## RED before implementation

Added eight negative regression methods to `scripts/test_action_bridge.py` before modifying production code. Ran those exact methods with `PYTHONPATH=scripts python3 -B -m unittest test_action_bridge.Bridge2Tests.<method> ...`:

| Test method | Pre-fix observation |
| --- | --- |
| `test_observation_correction_rechecks_without_repeating_worker` | New correction command unavailable; run did not complete through corrected verification. |
| `test_repeated_or_contract_correction_blocks_nonterminal_without_work` | No durable verification disposition (`KeyError: verification`, both subtests). |
| `test_transient_or_repeated_malformed_evaluator_observation` | Transient malformed output did not recover; repeated malformed output terminally halted. |
| `test_reviewer_unavailable_is_not_observation_or_safety_failure` | No classified durable reviewer-unavailable disposition (`KeyError: verification`). |
| `test_cancel_during_eval_kills_owned_descendants_without_review` | Cancellation took 2.79 seconds in the delayed fixture, exceeding the asserted 1.5-second bound. |
| `test_cancel_at_eval_completion_prevents_dispatch` | Review dispatch marker existed after durable cancellation at evaluator completion. |
| `test_synchronous_review_callback_cannot_apply_after_cancel` | Reviewer result applied (`last_review` set) before queued cancellation was consumed. |
| `test_cancel_during_review_rejects_late_callback` | Late callback applied before queued halt was consumed. |

Result: **8 methods, 7 failures + 3 errors, exit 1**; subtests account for the higher failure count. Private diagnostic log: `/tmp/ppp-f3-f4-red.log` (not a repository artifact or durable release bundle). F3's legacy stop-only semantic path was additionally source-confirmed, not represented as a live-model reproduction.

## Minimal correction contract

Full normative contract: [reviewer correction extension 1](action-scoped-protocol.md#reviewer-correction-extension-1-f3).

- Additive request capability `review_extension_version: 1` and reviewer decision `correct`. Its exact versioned JSON object contains `version`, `kind: observation|technical|contract`, retained `evidence_refs`, and a specific `next_check`; feedback supplies the diagnosis.
- No corrected acceptance assertions, executable commands, worker instructions, grants or contract edits are accepted through this channel.
- Core records optional `verification` metadata with failure type, evidence/finding fingerprint, repetition flag, retry accounting, boundary artifact hashes and state identity. It invalidates acceptance and blocks workers/effects/finish. Rejected reports do not apply any action, grant, criterion or human-resolution judgment; pending inputs stay pending.
- Core permits one fresh corrective verification experiment at the same unresolved boundary. The existing `ActionBridge.run()` drives it; no second orchestration loop. Retry retains the same worker cycle, checkpoint, cumulative accounting and F1 assessment obligation; it invokes only the unchanged independent evaluator/reviewer.
- Only a fresh valid independently endorsed report, passing all Core gates, completes correction. Repeated failure/finding/evidence cannot silently renew verification allowance. A second failure blocks nonterminally; `resume` retains that block and does not spend another verification call.
- `contract` means a protected evaluator/criteria change would be necessary: block with diagnosis, do not edit. Required-reviewer delivery failure/ambiguity/deadline is separately `reviewer_unavailable`, blocked without blind redispatch. Actual unsafe reports, pin/hash/identity violations and authorization failures remain safety halts.
- Malformed evaluator/reviewer JSON, evaluator startup failure/timeout and report-size violations are technical failures eligible for the single experiment. Existing mandatory report validation is not weakened: an invalid endorsed report still fails closed, preserving F1/F2 regressions.

There is deliberately no general amendment/unblock API for exhausted correction or ambiguous reviewer delivery in this slice. Investigation is required; manual state mutation or resetting retry metadata is not recovery.

## Cancellation implementation

- Evaluator runs in a fresh owned POSIX process group, with 50 ms durable-control polling and configured evaluation deadline. Cleanup sends TERM, waits 50 ms, sends KILL and reaps the leader, including after normal evaluator exit to prevent lingering owned children.
- `waitid(WNOWAIT)` keeps the leader unreaped through group cleanup, preventing PID reuse from redirecting signals. Darwin's zombie-only group EPERM is handled; a live-leader permission failure is not ignored. No saved/discovered PID is used to kill processes.
- Check controls after evaluation, immediately before inherited queue dispatch, after synchronous queue return, before reading/applying results, and under a final terminal-state check at application. Worker entry/pre-spawn also check controls.
- `review-v2` consumes pending cancel/halt and performs a final locked state/hash/terminal check before recording. Late/duplicate/stale callbacks cannot resume execution. Error handling does not replace an existing terminal state.
- Remote queueing cannot be atomically committed with local cancellation. A request already in flight before cancellation cannot be recalled/refunded; its result cannot authorize further work after cancellation. Pi suppresses pending terminal-run deliveries. The inherited Codex queue call remains finitely blocking; no unrelated queue is purged.

## Additional targeted coverage

The final suite adds **13 methods** relative to F1/F2's 20 bridge tests. Besides the initial eight, coverage includes:

- Unsupported/bool correction version, absent advertisement, missing/unretained evidence, invalid kind/empty next check; old schema-1 endorse remains valid without extension advertisement.
- Correction callbacks reject stale state and duplicate recording through the actual CLI recording implementation.
- Evaluator timeout kills its owned group and blocks after two failed checks without reviewer dispatch or worker consumption.
- Reviewer deadline blocks after one dispatch, with no blind repeat.
- Malformed reviewer response triggers fresh verification without worker replay.
- Cancellation during asynchronous Pi review wait exits without another boundary and refuses a callback submitted after controller exit.

The repair test injects a genuinely unsupported observation: the first checkpoint report falsely claims all actions/criteria pass. Reviewer rejects it; fresh measurement recovers and the two required workers still execute exactly once each. Repeated correction checks semantic finding/evidence fingerprints, not changing review IDs. Cancellation fixture includes a TERM-ignoring owned child and an unrelated session; the child cannot create its delayed effect marker, while the unrelated process remains alive. All outputs are synthetic local fixture files.

## Final verification

Using existing dependencies only:

| Command | Result |
| --- | --- |
| `python3 -B scripts/test_action_protocol.py` | 56 passed; F1/F2 retained |
| `python3 -B scripts/test_action_bridge.py` | 33 passed |
| `python3 -B scripts/test_bridge.py` | 15 passed |
| `node scripts/test_pi_receiver.mjs` | PASS |
| `.venv/bin/ruff check .` | PASS |
| `UV_OFFLINE=1 npm run check` | PASS: lint, typecheck, locked Ruff, all Python suites and receiver |
| `python3 -B scripts/test_install.py --fixture-root <new temporary directory>/fixture` | PASS; synthetic installer only |
| `git diff --check` | PASS |

**104 Python tests**; receiver suite reports PASS without a numeric count. Changed documentation links, exact source diff and final worktree status checked. Source-only evidence, not live acceptance.

## Compatibility and remaining boundaries

Protocol 1 runtime/evaluator/decision contracts unchanged; only the separate `review-v2` parser gains options. Protocol-2 evaluator/config/checkpoint schema remains 1; the new reviewer capability is independently versioned and advertised. Existing endorse/halt/stop submissions, receiver entries, run identities and ledgers remain valid. No frozen config/evaluator or historical run is migrated. Pre-extension requests reject `correct`; an old Core never advertises it. Pending verification metadata is additive and persists through new-Core recovery, not compatible with downgrading an actively correcting run to old Core.

Failure recovery is intentionally stricter: blocked correction and ambiguous reviewer delivery cannot be cleared by plain resume. Existing runs without these failures keep normal behavior. Closure remains unlimited; the verification experiment bound does not grant/consume work authority. The cooperative local-host threat model remains: no OS sandbox, detached/privilege-changing child containment or controller-crash evaluator cleanup guarantee. Live Goal/Ralph/provider reliability and broader crash/fault matrix remain unverified.

KB read: project `README.md`, `_SYSTEM/Knowledge_Read_Rules.md`, `_SYSTEM/Source_Of_Truth.md`, `07_PROMPTS_AGENTS/Global_Agent_Instructions.md`; KB project Architecture/Tech_Decisions/Next_Actions files are absent. Older KB status does not supersede current task/repository requirements. KB not modified; writes outside this worktree were not in scope.

Stop boundary: F3/F4 targeted hardening complete locally. The separate broader regression/fault-injection stage and any live E2E remain next work, not silently started. No Headless Reviewer, Observer, cross-chat, pi-tick, runtime sync or commit/merge.
